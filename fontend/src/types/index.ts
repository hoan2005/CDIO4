// =============================================
// STYLE
// Backend trả về color (hex) và line_style cho mọi object.
// Cả hai đều tùy chọn: thiếu thì frontend dùng màu mặc định.
// =============================================
export type LineStyle = 'solid' | 'dashed' | 'dotted'

export interface ObjectStyle {
  color?: string
  line_style?: LineStyle
}

// Style mở rộng cho hình phẳng: màu viền, nét vẽ và màu tô bên trong.
export interface PolygonStyle extends ObjectStyle {
  fill?: string
  fill_color?: string
  stroke_width?: number
}


// =============================================
// CANVAS OBJECT TYPES
// =============================================
export interface PointObject extends ObjectStyle {
  id: string
  kind: 'point'
  dimension: '2d' | '3d' | '4d'
  label: string
  position: number[]
}

export interface LineObject extends ObjectStyle {
  id: string
  kind: 'line'
  dimension: '2d'

  points: [
    [number, number],
    [number, number]
  ]

  label: string
}
export interface Line3DObject extends ObjectStyle {
  id: string
  kind: 'line'
  dimension: '3d'
  points: [[number, number, number], [number, number, number]]
  label?: string
}

export interface CircleObject extends ObjectStyle {
  id: string
  kind: 'circle'
  dimension: '2d'
  label?: string
  center: [number, number]
  radius: number
}
export interface EllipseObject extends ObjectStyle {
  id: string
  kind: 'ellipse'
  dimension: '2d'
  label?: string
  center: [number, number]
  a: number
  b: number
  rotation?: number
}
export interface HyperbolaObject extends ObjectStyle {
  id: string
  kind: 'hyperbola'
  dimension: '2d'
  label?: string
  center: [number, number]
  a: number
  b: number
  orientation?: 'horizontal' | 'vertical'
}
export interface SphereObject extends ObjectStyle {
  id: string
  kind: 'sphere'
  dimension: '3d'
  label?: string
  center: [number, number, number]
  radius: number
}
export interface ConeObject extends ObjectStyle {
  id: string
  kind: 'cone'
  dimension: '3d'
  label?: string
  coordinates: { apex: [number, number, number]; center: [number, number, number] }
  radius: number
  height: number
}
export interface PlaneObject extends ObjectStyle {
  id: string
  kind: 'plane'
  dimension: '2d' | '3d'
  label?: string
  coordinates?: { origin?: number[]; normal?: number[] }
  origin?: number[]
}
export interface FunctionObject extends ObjectStyle {
  id: string
  kind: 'function'
  label: string
  dimension: '2d'
  points: [number, number][]
}

// Đa giác 2D do backend draw_polygon_2d trả về.
// Dùng chung cho tam giác, hình vuông, chữ nhật, thoi, thang...
export interface PolygonObject {
  id: string
  kind: 'polygon'
  label: string
  dimension: '2d'
  vertices: string[]
  coordinates: Record<string, [number, number]>
  edges?: Array<{
    start: string
    end: string
  }>
  role?: string
  style?: PolygonStyle
  constraints?: unknown[]
}

export interface PyramidObject extends ObjectStyle {
  id: string
  kind: 'pyramid'
  label: string
  dimension: '3d'
  vertices: Record<string, [number, number, number]>

  // Thứ tự các đỉnh quanh mặt đáy và tên đỉnh chóp.
  base_order?: string[]
  apex_name?: string

  // Topology do backend trả về; frontend dùng để render cạnh/mặt.
  edges?: Array<{
    from: string
    to: string
    type: 'base' | 'lateral'
  }>
  faces?: string[][]
}

export interface PrismObject extends ObjectStyle {
  id: string
  kind: 'prism'
  label: string
  dimension: '3d'

  vertices: Record<string, [number, number, number]>

  base_order: string[]
  top_order: string[]
}

export interface CubeObject extends ObjectStyle {
  id: string
  kind: 'cube'
  label: string
  dimension: '3d'
  vertices: { A: [number, number, number] 
    B: [number, number, number] 
    C: [number, number, number] 
    D: [number, number, number] 
    "A'": [number, number, number] 
    "B'": [number, number, number] 
    "C'": [number, number, number] 
    "D'": [number, number, number] }
}


// =============================================
// CANVAS OBJECT
// =============================================

export type CanvasObject =
  | FunctionObject
  | CircleObject
  | EllipseObject
  | HyperbolaObject
  | SphereObject
  | ConeObject
  | PlaneObject
  | PolygonObject
  | CubeObject
  | PyramidObject
  | PrismObject
  | LineObject
  | Line3DObject
  | PointObject



// =============================================
// CANVAS DELTA
// =============================================

export interface CanvasDelta {
  add: CanvasObject[]
  update: CanvasObject[]
  remove: string[]
}


// =============================================
// CHAT MESSAGE
// =============================================

export type MessageRole = 'user' | 'assistant'

export interface Message {
  id: string
  role: MessageRole
  content: string
  timestamp: number

  knowledge?: string[]
  isLoading?: boolean
}


// =============================================
// API REQUEST & RESPONSE
// =============================================

export interface ChatRequest {
  conversation_id: string
  message: string
}

export interface ChatResponse {
  conversation_id: string
  message: Message
  canvas: CanvasDelta
}


// =============================================
// CONVERSATION
// =============================================

export interface Conversation {
  id: string
  title: string
  messages: Message[]
  canvas_objects: CanvasObject[]
  created_at: string
  updated_at: string
}


// =============================================
// CANVAS OBJECT + UI METADATA
// =============================================

export interface CanvasObjectWithMeta {
  id: string
  visible: boolean
  object: CanvasObject
}

// Interface mới để quản lý đối tượng đang được chọn
export interface CanvasObjectSelection {
  id: string | null
  x: number | null // Tọa độ X để hiển thị context menu / nút remove
  y: number | null // Tọa độ Y
}


// =============================================
// APP STATE - ZUSTAND
// =============================================

export interface AppState {
  conversationId: string | null
  messages: Message[]
  canvasObjects: CanvasObjectWithMeta[]
  isLoading: boolean
  sidebarOpen: boolean
  canvasMode: '2d' | '3d'
  
  // Trạng thái chọn đối tượng
  selectedObject: CanvasObjectSelection
  setSelectedObject: (selection: CanvasObjectSelection) => void

  sendMessage: (text: string) => Promise<void>
  applyCanvasDelta: (delta: CanvasDelta) => void
  addCanvasObjects: (objects: CanvasObject[]) => void
  updateCanvasObjects: (objects: CanvasObject[]) => void
  removeCanvasObjects: (ids: string[]) => void
  toggleObject: (id: string) => void

  // Gửi request xóa lên Backend
  removeObject: (id: string, message?: string) => Promise<void>
  
  clearCanvas: () => void
  updatePoint: (id: string, x: number, y: number) => void
  toggleSidebar: () => void
  setCanvasMode: (mode: '2d' | '3d') => void
}