import * as math from 'mathjs'

// ─────────────────────────────────────────────────────────────────────────────
// 1. TYPES – khớp chính xác với JSON backend Python trả về
// ─────────────────────────────────────────────────────────────────────────────

/** Backend: TaoPhuongTrinh */
export interface PhuongTrinhObject {
  id: string
  label: string          // "y=x**3"
  type: 'phuongtrinh'
  equation: string       // "x**3"  (sympy syntax, chỉ vế phải)
  color: string
}

/** Backend: TaoTiepTuyen → phần điểm */
export interface PointObject {
  id: string
  label: string          // "P_(1, 3)"
  type: 'point'
  coordinates: [number, number]
  color: string
}

/** Backend: TaoTiepTuyen → phần đường thẳng */
export interface LineObject {
  id: string
  label: string          // "y = 2.0*x + 1.0"  (dùng để hiển thị)
  type: 'line'
  paramater: {           // ax + by + c = 0  (backend typo: "paramater")
    a: number
    b: number
    c: number
  }
  color: string
}

/** Backend: TaoDiem */
export interface DiemObject {
  id: string
  label: string          // "P_[1, 3]"
  type: 'diem_2d' | 'diem_3d'
  coordinates: number[]
  color: string
}

/** Union của tất cả object backend có thể gửi */
export type GraphObject = PhuongTrinhObject | PointObject | LineObject | DiemObject

// ─────────────────────────────────────────────────────────────────────────────
// 2. PARSE EQUATION – sympy string → hàm f(x)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Chuyển chuỗi phương trình sympy (vd: "x**2 + 2*x + 1") thành hàm f(x).
 * Hỗ trợ: x**n, sin/cos/tan/log/sqrt, pi, E
 */
export function parseEquation(eq: string): (x: number) => number {
  const normalized = eq
    .replace(/\*\*/g, '^')            // x**2 → x^2
    .replace(/\b(\d+)(x)/g, '$1*$2') // 2x   → 2*x
    .replace(/\bE\b/g, 'e')           // E    → e  (hằng Euler)
    .replace(/\bI\b/g, 'i')           // I    → i  (số phức – mathjs hiểu)
    .replace(/\bpi\b/gi, 'pi')        // Pi/PI → pi

  let compiled: math.EvalFunction
  try {
    compiled = math.compile(normalized)
  } catch {
    return () => NaN
  }

  return (x: number) => {
    try {
      const result = compiled.evaluate({ x })
      if (typeof result !== 'number' || !isFinite(result)) return NaN
      return result
    } catch {
      return NaN
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// 3. PARSE LINE – từ {a, b, c} của backend → hàm f(x)
//    Dạng: ax + by + c = 0  →  y = (-a*x - c) / b
//    Trường hợp đặc biệt: b = 0 → đường thẳng đứng x = -c/a
// ─────────────────────────────────────────────────────────────────────────────

export interface LineParams {
  a: number   // hệ số x
  b: number   // hệ số y  (backend luôn để -1)
  c: number   // hằng số
}

/**
 * Chuyển {a, b, c} của backend thành hàm y = f(x).
 * Công thức: ax + by + c = 0  →  y = -(a*x + c) / b
 */
export function parseLineParams(params: LineParams): (x: number) => number {
  const { a, b, c } = params

  if (Math.abs(b) < 1e-12) {
    // Đường thẳng đứng: không biểu diễn được dạng y=f(x)
    return () => NaN
  }

  return (x: number) => -(a * x + c) / b
}

/**
 * Kiểm tra đường thẳng đứng (b ≈ 0).
 * Nếu đúng, trả về x0; ngược lại trả về null.
 */
export function getVerticalX(params: LineParams): number | null {
  if (Math.abs(params.b) < 1e-12 && Math.abs(params.a) > 1e-12) {
    return -params.c / params.a
  }
  return null
}

// ─────────────────────────────────────────────────────────────────────────────
// 4. SAMPLE POINTS – lấy mảng điểm để vẽ đường cong/thẳng
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Lấy mảng {x, y} cho hàm số trong đoạn [xMin, xMax].
 * Tự động ngắt đoạn khi hàm không liên tục (NaN).
 */
export function sampleFunction(
  fn: (x: number) => number,
  xMin: number,
  xMax: number,
  steps = 400,
): Array<{ x: number; y: number }> {
  const points: Array<{ x: number; y: number }> = []
  const step = (xMax - xMin) / steps

  for (let i = 0; i <= steps; i++) {
    const x = xMin + i * step
    const y = fn(x)
    if (isFinite(y) && Math.abs(y) < 1e6) {
      points.push({ x, y })
    }
  }
  return points
}

// ─────────────────────────────────────────────────────────────────────────────
// 5. LABEL POINT – tính vị trí đặt label trên đồ thị
// ─────────────────────────────────────────────────────────────────────────────

export interface LabelPoint {
  x: number
  y: number
  /** 'start' = label bên phải điểm, 'end' = label bên trái điểm */
  anchor: 'start' | 'end'
  text: string   // ← nội dung label lấy từ backend
}

/**
 * Tìm điểm đặt label cho đường cong / đường thẳng.
 * Ưu tiên điểm cuối bên phải, fallback sang bên trái.
 */
export function getLabelPoint(
  fn: (x: number) => number,
  xMin: number,
  xMax: number,
  labelText: string,
  samples = 300,
): LabelPoint | null {
  const step = (xMax - xMin) / samples

  const candidates: Array<{ x: number; anchor: 'start' | 'end' }> = [
    { x: xMax, anchor: 'end' },
    { x: xMin, anchor: 'start' },
  ]

  for (const { x, anchor } of candidates) {
    const dir = anchor === 'end' ? -1 : 1
    for (let i = 0; i <= 10; i++) {
      const cx = x + dir * i * step
      const y = fn(cx)
      if (isFinite(y)) return { x: cx, y, anchor, text: labelText }
    }
  }

  return null
}

/**
 * Lấy LabelPoint cho điểm (PointObject / DiemObject).
 * Đặt label lệch một chút so với tọa độ thực để không đè lên dấu chấm.
 */
export function getLabelPointForDot(
  obj: PointObject | DiemObject,
  offsetX = 0.15,
  offsetY = 0.15,
): LabelPoint {
  const [x, y] = obj.coordinates as [number, number]
  return {
    x: x + offsetX,
    y: y + offsetY,
    anchor: 'start',
    text: obj.label,  // "P_(1, 3)" hoặc "P_[1.0, 2.0]"
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// 6. FACTORY – chuyển GraphObject → render-ready data
//    Đây là hàm trung tâm: frontend chỉ cần gọi hàm này
// ─────────────────────────────────────────────────────────────────────────────

export interface RenderCurve {
  kind: 'curve'
  id: string
  color: string
  points: Array<{ x: number; y: number }>
  label: LabelPoint | null
}

export interface RenderLine {
  kind: 'line'
  id: string
  color: string
  points: Array<{ x: number; y: number }>
  label: LabelPoint | null
  /** Nếu là đường thẳng đứng, chỉ cần vẽ x = verticalX */
  verticalX: number | null
}

export interface RenderDot {
  kind: 'dot'
  id: string
  color: string
  x: number
  y: number
  label: LabelPoint
}

export type RenderItem = RenderCurve | RenderLine | RenderDot

/**
 * Chuyển một GraphObject từ backend thành dữ liệu sẵn sàng để vẽ.
 *
 * @param obj    - Object JSON từ backend
 * @param xMin   - Giới hạn trái của trục Ox
 * @param xMax   - Giới hạn phải của trục Ox
 */
export function toRenderItem(
  obj: GraphObject,
  xMin = -10,
  xMax = 10,
): RenderItem {

  // ── Đường cong (hàm số) ──────────────────────────────────────────────────
  if (obj.type === 'phuongtrinh') {
    const fn = parseEquation(obj.equation)
    const pts = sampleFunction(fn, xMin, xMax)
    const label = getLabelPoint(fn, xMin, xMax, obj.label)
    return { kind: 'curve', id: obj.id, color: obj.color, points: pts, label }
  }

  // ── Đường thẳng (tiếp tuyến / line) ─────────────────────────────────────
  if (obj.type === 'line') {
    const params = obj.paramater   // {a, b, c}
    const verticalX = getVerticalX(params)

    if (verticalX !== null) {
      // Đường thẳng đứng: không sample được, chỉ lưu x0
      return {
        kind: 'line',
        id: obj.id,
        color: obj.color,
        points: [],
        verticalX,
        label: {
          x: verticalX,
          y: (xMin + xMax) / 2,   // đặt label ở giữa màn hình
          anchor: 'start',
          text: obj.label,
        },
      }
    }

    const fn = parseLineParams(params)
    const pts = sampleFunction(fn, xMin, xMax)
    const label = getLabelPoint(fn, xMin, xMax, obj.label)
    return { kind: 'line', id: obj.id, color: obj.color, points: pts, verticalX: null, label }
  }

  // ── Điểm đơn (tiếp điểm / điểm bất kỳ) ─────────────────────────────────
  if (obj.type === 'point' || obj.type === 'diem_2d' || obj.type === 'diem_3d') {
    const [x, y] = obj.coordinates as [number, number]
    const label = getLabelPointForDot(obj as PointObject | DiemObject)
    return { kind: 'dot', id: obj.id, color: obj.color, x, y, label }
  }

  // Fallback (TypeScript exhaustive check)
  throw new Error(`Unknown graph object type: ${(obj as GraphObject).type}`)
}

/**
 * Chuyển mảng GraphObject → mảng RenderItem (gọi khi nhận response từ backend)
 *
 * @example
 * const items = toRenderItems(backendResponse, -10, 10)
 * items.forEach(item => drawItem(ctx, item))
 */
export function toRenderItems(
  objects: GraphObject[],
  xMin = -10,
  xMax = 10,
): RenderItem[] {
  return objects.map(obj => toRenderItem(obj, xMin, xMax))
}