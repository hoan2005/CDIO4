import { create } from 'zustand'

import { chatService } from '@/services/chatService'

import type {
  AppState,
  CanvasObject,
  CanvasObjectWithMeta,
  Message,
  CanvasDelta,
} from '@/types'


// ============================================================
// HELPER
// ============================================================

/**
 * Tạo ID cho message phía Frontend
 */
function makeId(): string {
  return Math.random()
    .toString(36)
    .slice(2, 9)
}


/**
 * Chuyển CanvasObject thành CanvasObjectWithMeta
 *
 * Backend:
 *
 * {
 *   id,
 *   kind,
 *   ...
 * }
 *
 * Frontend:
 *
 * {
 *   id,
 *   visible,
 *   object
 * }
 */
function wrapObjects(
  objects: CanvasObject[]
): CanvasObjectWithMeta[] {

  return objects.map(object => ({
    id: object.id,
    visible: true,
    object,
  }))
}


// ============================================================
// ZUSTAND STORE
// ============================================================

export const useAppStore = create<AppState>(
  (set, get) => ({

    // ========================================================
    // STATE
    // ========================================================

    conversationId: null,

    messages: [],

    canvasObjects: [],

    isLoading: false,

    sidebarOpen: true,

    canvasMode: '2d',


    // ========================================================
    // SEND MESSAGE
    // ========================================================

    sendMessage: async (text: string) => {

      // ------------------------------------------------------
      // Lấy conversation hiện tại
      // ------------------------------------------------------

      const conversationId = get().conversationId


      // ------------------------------------------------------
      // Tạo message của User
      // ------------------------------------------------------

      const userMessage: Message = {
        id: makeId(),

        role: 'user',

        content: text,

        timestamp: Date.now(),
      }


      // ------------------------------------------------------
      // Tạo loading message
      // ------------------------------------------------------

      const loadingMessage: Message = {
        id: 'loading',

        role: 'assistant',

        content: '',

        timestamp: Date.now(),

        isLoading: true,
      }


      // ------------------------------------------------------
      // Cập nhật UI ngay lập tức
      // ------------------------------------------------------

      set(state => ({

        messages: [
          ...state.messages,

          userMessage,

          loadingMessage,
        ],

        isLoading: true,

      }))


      try {

        // ====================================================
        // GỌI BACKEND
        // ====================================================

        const response = await chatService.send({

          conversation_id:
            conversationId ?? '',

          message: text,

        })


        // ====================================================
        // CẬP NHẬT CONVERSATION
        // ====================================================

        set({
          conversationId:
            response.conversation_id,
        })


        // ====================================================
        // MESSAGE CỦA AI
        // ====================================================

        const aiMessage: Message = {

          ...response.message,

          id:
            response.message.id ||
            makeId(),

          role: 'assistant',

          timestamp:
            response.message.timestamp ||
            Date.now(),

        }


        // ====================================================
        // XÓA LOADING MESSAGE
        // VÀ THÊM MESSAGE AI
        // ====================================================

        set(state => ({

          messages: [

            ...state.messages.filter(
              message =>
                message.id !== 'loading'
            ),

            aiMessage,

          ],

        }))


        // ====================================================
        // XỬ LÝ CANVAS
        // ====================================================

        get().applyCanvasDelta(
          response.canvas
        )


        // ====================================================
        // KẾT THÚC LOADING
        // ====================================================

        set({
          isLoading: false,
        })

      } catch (error) {

        console.error(
          'Chat error:',
          error
        )


        // ====================================================
        // ERROR MESSAGE
        // ====================================================

        const errorMessage: Message = {

          id: makeId(),

          role: 'assistant',

          content:
            '⚠️ Không thể kết nối server. Hãy kiểm tra backend đang chạy.',

          timestamp: Date.now(),

        }


        set(state => ({

          isLoading: false,

          messages: [

            ...state.messages.filter(
              message =>
                message.id !== 'loading'
            ),

            errorMessage,

          ],

        }))

      }

    },


    // ========================================================
    // APPLY CANVAS DELTA
    // ========================================================

    applyCanvasDelta: (
      delta: CanvasDelta
    ) => {

      // ------------------------------------------------------
      // ADD
      // ------------------------------------------------------

      if (delta.add.length > 0) {

        get().addCanvasObjects(
          delta.add
        )

      }


      // ------------------------------------------------------
      // UPDATE
      // ------------------------------------------------------

      if (delta.update.length > 0) {

        get().updateCanvasObjects(
          delta.update
        )

      }


      // ------------------------------------------------------
      // REMOVE
      // ------------------------------------------------------

      if (delta.remove.length > 0) {

        get().removeCanvasObjects(
          delta.remove
        )

      }

    },


    // ========================================================
    // ADD CANVAS OBJECTS
    // ========================================================

    addCanvasObjects: (
      objects: CanvasObject[]
    ) => {

      set(state => ({

        canvasObjects: [

          ...state.canvasObjects,

          ...wrapObjects(objects),

        ],

      }))

    },


    // ========================================================
    // UPDATE CANVAS OBJECTS
    // ========================================================

    updateCanvasObjects: (
      objects: CanvasObject[]
    ) => {
      // Lập bảng tra cứu theo ID để chỉ cập nhật đúng đối tượng.
      // Dùng tuple `as const` để TypeScript suy luận đúng kiểu Map.
      const updateMap = new Map(
        objects.map(object => [object.id, object] as const)
      )

      // Chỉ thay đổi các object đã tồn tại trong store.
      // Nếu ID từ backend không khớp, giữ nguyên object hiện tại;
      // update không tự thêm object mới vào canvas.
      set(state => ({
        canvasObjects: state.canvasObjects.map(canvasObject => {
          const updatedObject = updateMap.get(canvasObject.id)

          if (!updatedObject) {
            return canvasObject
          }

          return {
            // Giữ metadata phía frontend, đặc biệt là visible.
            ...canvasObject,

            // Ghép dữ liệu mới lên object cũ để giữ các trường
            // mà backend không gửi lại trong payload update.
            // Các trường mới sẽ ghi đè trường cũ cùng tên.
            object: {
              ...canvasObject.object,
              ...updatedObject,
            } as CanvasObject,
          }
        }),
      }))
    },


    // ========================================================
    // REMOVE CANVAS OBJECTS
    // ========================================================

    removeCanvasObjects: (
      ids: string[]
    ) => {

      set(state => ({

        canvasObjects:
          state.canvasObjects.filter(
            canvasObject =>
              !ids.includes(
                canvasObject.id
              )
          ),

      }))

    },


    // ========================================================
    // TOGGLE OBJECT
    // ========================================================

    toggleObject: (
      id: string
    ) => {

      set(state => ({

        canvasObjects:
          state.canvasObjects.map(
            canvasObject => {

              if (
                canvasObject.id !== id
              ) {

                return canvasObject

              }


              return {

                ...canvasObject,

                visible:
                  !canvasObject.visible,

              }

            }
          ),

      }))

    },


    // ========================================================
    // REMOVE ONE OBJECT
    // ========================================================

    removeObject: (
      id: string
    ) => {

      set(state => ({

        canvasObjects:
          state.canvasObjects.filter(
            canvasObject =>
              canvasObject.id !== id
          ),

      }))

    },


    // ========================================================
    // CLEAR CANVAS
    // ========================================================

    clearCanvas: () => {

      set({

        canvasObjects: [],

      })

    },


    // ========================================================
    // UPDATE POINT
    // ========================================================

    updatePoint: (
      id: string,
      x: number,
      y: number
    ) => {

      set(state => ({

        canvasObjects:
          state.canvasObjects.map(
            canvasObject => {

              if (
                canvasObject.id !== id
              ) {

                return canvasObject

              }


              /**
               * Hiện tại index.ts chưa có
               * PointObject.
               *
               * Vì vậy chỉ update nếu
               * object có coordinates.
               */

              if (
                'coordinates'
                in canvasObject.object
              ) {

                return {

                  ...canvasObject,

                  object: {

                    ...canvasObject.object,

                    coordinates: [
                      x,
                      y,
                    ],

                  },

                } as CanvasObjectWithMeta

              }


              return canvasObject

            }
          ),

      }))

    },


    // ========================================================
    // TOGGLE SIDEBAR
    // ========================================================

    toggleSidebar: () => {

      set(state => ({

        sidebarOpen:
          !state.sidebarOpen,

      }))

    },


    // ========================================================
    // SET CANVAS MODE
    // ========================================================

    setCanvasMode: (
      mode: '2d' | '3d'
    ) => {

      set({

        canvasMode: mode,

      })

    },

  })
)