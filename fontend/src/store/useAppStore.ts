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

function mergeCanvasObjectUpdate(
  currentObject: CanvasObject,
  updatedObject: CanvasObject,
): CanvasObject {
  const current = currentObject as unknown as Record<string, unknown>
  const update = updatedObject as unknown as Record<string, unknown>
  const merged = { ...current, ...update }

  // 3D update payloads may contain vertex names plus a separate coordinates map,
  // while the renderers consume vertices as { name: [x, y, z] }.
  if (
    update.dimension === '3d'
    && Array.isArray(update.vertices)
    && update.vertices.every(name => typeof name === 'string')
    && update.coordinates !== null
    && typeof update.coordinates === 'object'
    && !Array.isArray(update.coordinates)
    && ['cube', 'pyramid', 'prism', 'polygon'].includes(String(update.kind))
  ) {
    const coordinates = update.coordinates as Record<string, unknown>
    const currentVertices =
      current.vertices !== null
      && typeof current.vertices === 'object'
      && !Array.isArray(current.vertices)
        ? current.vertices as Record<string, unknown>
        : {}
    const vertices = { ...currentVertices }

    for (const name of update.vertices) {
      const position = coordinates[name] ?? coordinates[`point_${name}`]
      if (Array.isArray(position) && position.length === 3) {
        vertices[name] = position
      }
    }

    merged.vertices = vertices
  }

  return merged as unknown as CanvasObject
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

    selectedObject: {
      id: null,
      x: null,
      y: null,
    },

    setSelectedObject: (selection) => {
      set({ selectedObject: selection })
    },


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

    connectCanvasPoints: async (startPoint: string, endPoint: string) => {
      const conversationId = get().conversationId
      if (!conversationId) {
        set(state => ({
          messages: [
            ...state.messages,
            {
              id: makeId(),
              role: 'assistant',
              content: 'Hãy bắt đầu cuộc trò chuyện trước khi nối các điểm trên canvas.',
              timestamp: Date.now(),
            },
          ],
        }))
        return
      }

      try {
        const line = await chatService.connectPoints(
          conversationId,
          startPoint,
          endPoint,
        )
        get().addCanvasObjects([line])
      } catch (error) {
        console.error('Canvas point connection error:', error)
        const detail = error instanceof Error ? error.message : String(error)
        set(state => ({
          messages: [
            ...state.messages,
            {
              id: makeId(),
              role: 'assistant',
              content: `Không thể nối hai điểm ${startPoint} và ${endPoint}: ${detail}`,
              timestamp: Date.now(),
            },
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

        canvasMode: objects.some(object => object.dimension === '3d')
          ? '3d'
          : state.canvasMode,

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

            object: mergeCanvasObjectUpdate(
              canvasObject.object,
              updatedObject,
            ),
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

    removeObject: async (id: string, message?: string) => {
      await get().sendMessage(
        message ?? `hãy xóa đối tượng "${id}" khỏi canvas`,
      )
    },


    // ========================================================
    // CLEAR CANVAS
    // ========================================================

    clearCanvas: async () => {
      if (get().isLoading) {
        return
      }

      set({ isLoading: true })

      try {
        const response = await chatService.clearCanvas(
          get().conversationId ?? '',
        )

        set({ conversationId: response.conversation_id })
        get().applyCanvasDelta(response.canvas)
        set({
          selectedObject: {
            id: null,
            x: null,
            y: null,
          },
        })

        const aiMessage: Message = {
          ...response.message,
          id: response.message.id || makeId(),
          role: 'assistant',
          timestamp: response.message.timestamp || Date.now(),
        }

        set(state => ({
          isLoading: false,
          messages: [...state.messages, aiMessage],
        }))
      } catch (error) {
        console.error('Canvas clear error:', error)
        const detail = error instanceof Error ? error.message : String(error)
        set(state => ({
          isLoading: false,
          messages: [
            ...state.messages,
            {
              id: makeId(),
              role: 'assistant',
              content: `⚠️ Không thể xóa các đối tượng trên canvas: ${detail}`,
              timestamp: Date.now(),
            },
          ],
        }))
      }
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