import React, { useMemo, useState } from 'react'

import {
  Stage,
  Layer,
  Line,
  Circle,
  Text,
  Rect,
} from 'react-konva'

import type {
  CanvasObjectWithMeta,
  FunctionObject,
} from '@/types'

// ============================================================
// STYLE: màu và kiểu nét do backend trả về
// ============================================================

const HEX_COLOR_PATTERN = /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/

function resolveColor(
  color: string | undefined,
  fallback: string
): string {
  return typeof color === 'string' &&
    HEX_COLOR_PATTERN.test(color.trim())
    ? color.trim()
    : fallback
}

function getDash(
  lineStyle: string | undefined,
  strokeWidth: number
): number[] | undefined {
  if (lineStyle === 'dashed') {
    return [strokeWidth * 4, strokeWidth * 3]
  }

  if (lineStyle === 'dotted') {
    return [0.1, strokeWidth * 3]
  }

  return undefined
}

// ============================================================
// PROPS
// ============================================================

interface Canvas2DProps {
  objects: CanvasObjectWithMeta[]
  width?: number
  height?: number
  // Props truyền từ state global (Zustand)
  onObjectSelect?: (id: string | null, x: number, y: number) => void
  selectedObjectId?: string | null
  onRemoveObject?: (id: string, message?: string) => void
  onSendMessage?: (message: string) => void
}

// ============================================================
// OBJECT INTERFACES
// ============================================================

interface LineObject {
  id: string
  kind: 'line'
  dimension: '2d'
  points: [number, number][]
  label?: string
  color?: string
  line_style?: 'solid' | 'dashed' | 'dotted'
}

interface PolygonObject {
  id: string
  kind: 'polygon'
  dimension: '2d'
  label?: string
  vertices: string[]
  coordinates: Record<string, [number, number] | number[]>
  edges?: { start: string; end: string }[]
  role?: string
  style?: {
    color?: string
    line_style?: 'solid' | 'dashed' | 'dotted'
    fill?: string
    fill_color?: string
    stroke_width?: number
  }
  constraints?: unknown[]
}

// ============================================================
// CANVAS 2D
// ============================================================

export default function Canvas2D({
  objects,
  width = 800,
  height = 600,
  onObjectSelect,
  selectedObjectId,
  onRemoveObject,
  onSendMessage
}: Canvas2DProps) {

  // Local state dự phòng (nếu không dùng Zustand cho việc selection UI point)
  const [localSelection, setLocalSelection] = useState<{id: string, x: number, y: number} | null>(null)
  
  const activeSelectedId = selectedObjectId !== undefined ? selectedObjectId : localSelection?.id
  const menuPosition = localSelection

  const [scale, setScale] = useState(40)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [isDragging, setIsDragging] = useState(false)
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 })

  const objects2D = useMemo(() => {
    return objects.filter(
      item =>
        item.visible &&
        item.object.dimension === '2d'
    )
  }, [objects])

  const originX = width / 2 + pan.x
  const originY = height / 2 + pan.y

  const toCanvasPoint = (x: number, y: number): [number, number] => {
    return [originX + x * scale, originY - y * scale]
  }

  const toMathPoint = (canvasX: number, canvasY: number): [number, number] => {
    return [(canvasX - originX) / scale, (originY - canvasY) / scale]
  }

  // ==========================================================
  // XỬ LÝ CHỌN ĐỐI TƯỢNG (CLICK VÀO SHAPE)
  // ==========================================================
  const handleObjectClick = (e: any, id: string) => {
    e.cancelBubble = true; // Ngăn chặn sự kiện click lan ra nền (stage)
    const stage = e.target.getStage();
    const pointer = stage.getPointerPosition();
    
    if (pointer) {
      if (onObjectSelect) {
        onObjectSelect(id, pointer.x, pointer.y);
      }
      setLocalSelection({ id, x: pointer.x, y: pointer.y });
    }
  }

  // Bấm vào nền -> Bỏ chọn
  const handleStageClick = (_e: any) => {
    // Mọi click không bị shape chặn đều được xem là click vùng trống.
    if (onObjectSelect) onObjectSelect(null, 0, 0)
    setLocalSelection(null)
  }

  // Grid
  const gridLines = useMemo(() => {
    const lines: React.ReactNode[] = []
    const left = -1 - originX / scale
    const right = 1 + (width - originX) / scale
    const bottom = -1 - (height - originY) / scale
    const top = 1 + originY / scale

    const startX = Math.floor(left)
    const endX = Math.ceil(right)
    const startY = Math.floor(bottom)
    const endY = Math.ceil(top)

    const step = scale < 12 ? 5 : scale < 22 ? 2 : 1

    for (let x = Math.floor(startX / step) * step; x <= endX; x += step) {
      if (x === 0) continue
      const [canvasX] = toCanvasPoint(x, 0)
      lines.push(
        <Line key={`grid-x-${x}`} points={[canvasX, 0, canvasX, height]} stroke="#E2E8F0" strokeWidth={1} />
      )
    }

    for (let y = Math.floor(startY / step) * step; y <= endY; y += step) {
      if (y === 0) continue
      const [, canvasY] = toCanvasPoint(0, y)
      lines.push(
        <Line key={`grid-y-${y}`} points={[0, canvasY, width, canvasY]} stroke="#E2E8F0" strokeWidth={1} />
      )
    }
    return lines
  }, [width, height, originX, originY, scale])


  const axisLabels = useMemo(() => {
    const labels: React.ReactNode[] = []
    const left = Math.floor((-originX) / scale) - 1
    const right = Math.ceil((width - originX) / scale) + 1
    const bottom = Math.floor(-(height - originY) / scale) - 1
    const top = Math.ceil(originY / scale) + 1
    const step = scale < 12 ? 5 : scale < 22 ? 2 : 1

    for (let x = Math.floor(left / step) * step; x <= right; x += step) {
      if (x === 0) continue
      const [canvasX, axisY] = toCanvasPoint(x, 0)
      if (canvasX < 10 || canvasX > width - 25) continue
      labels.push(<Text key={`label-x-${x}`} x={canvasX + 4} y={axisY + 6} text={String(x)} fontSize={11} fill="#64748B" />)
    }

    for (let y = Math.floor(bottom / step) * step; y <= top; y += step) {
      if (y === 0) continue
      const [axisX, canvasY] = toCanvasPoint(0, y)
      if (canvasY < 15 || canvasY > height - 15) continue
      labels.push(<Text key={`label-y-${y}`} x={axisX + 8} y={canvasY - 7} text={String(y)} fontSize={11} fill="#64748B" />)
    }

    return labels
  }, [width, height, originX, originY, scale])


  const handleWheel = (event: any) => {
    event.evt.preventDefault()
    const stage = event.target.getStage()
    if (!stage) return
    const pointer = stage.getPointerPosition()
    if (!pointer) return

    const oldScale = scale
    const zoomFactor = event.evt.deltaY < 0 ? 1.1 : 1 / 1.1
    const newScale = Math.min(200, Math.max(10, oldScale * zoomFactor))
    const mathX = (pointer.x - originX) / oldScale
    const mathY = (originY - pointer.y) / oldScale
    const newOriginX = pointer.x - mathX * newScale
    const newOriginY = pointer.y + mathY * newScale

    setScale(newScale)
    setPan({ x: newOriginX - width / 2, y: newOriginY - height / 2 })
    
    // Nếu đang chọn menu, cuộn chuột làm mất vị trí => bỏ chọn
    setLocalSelection(null);
  }

  const handleMouseDown = (event: any) => {
    const target = event.target
    const stage = target.getStage()

    if (
      target !== stage &&
      target.getClassName?.() !== 'Line' &&
      target.getClassName?.() !== 'Rect'
    ) {
      return
    }
    const pointer = stage.getPointerPosition()
    if (!pointer) return

    setIsDragging(true)
    setDragStart({ x: pointer.x, y: pointer.y })
  }

  const handleMouseMove = (event: any) => {
    if (!isDragging) return
    const stage = event.target.getStage()
    if (!stage) return
    const pointer = stage.getPointerPosition()
    if (!pointer) return

    const dx = pointer.x - dragStart.x
    const dy = pointer.y - dragStart.y
    setPan(current => ({ x: current.x + dx, y: current.y + dy }))
    setDragStart({ x: pointer.x, y: pointer.y })
    
    setLocalSelection(null); // Kéo di chuyển -> ẩn menu
  }

  const handleMouseUp = () => setIsDragging(false)
  const resetView = () => { setScale(40); setPan({ x: 0, y: 0 }); setLocalSelection(null); }

  const hasObjects = objects2D.length > 0
  
  // Hàm trợ giúp để quyết định màu khi vẽ
  const getRenderColor = (objId: string, originalColor: string, fallback: string) => {
    if (activeSelectedId === objId) {
      return '#9CA3AF' // Trạng thái xám khi được chọn
    }
    return resolveColor(originalColor, fallback)
  }

  return (
    <div
      style={{
        width,
        height,
        position: 'relative',
        overflow: 'hidden',
        background: '#F8FAFC',
        borderRadius: 12,
      }}
    >
      <Stage
        width={width}
        height={height}
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onClick={handleStageClick}
        style={{ cursor: isDragging ? 'grabbing' : 'grab' }}
      >
        <Layer>
          <Rect name="canvas-background" x={0} y={0} width={width} height={height} fill="#F8FAFC" />
          {gridLines}

          {/* TRỤC X & Y */}
          <Line points={[0, originY, width, originY]} stroke="#000000" strokeWidth={1.8} />
          <Line points={[width - 12, originY - 6, width, originY, width - 12, originY + 6]} stroke="#000000" strokeWidth={2} lineCap="round" lineJoin="round" />
          <Line points={[originX, 0, originX, height]} stroke="#000000" strokeWidth={1.8} />
          <Line points={[originX - 6, 12, originX, 0, originX + 6, 12]} stroke="#000000" strokeWidth={2} lineCap="round" lineJoin="round" />

          <Text x={Math.min(width - 25, Math.max(8, originX + 10))} y={8} text="Y" fontSize={16} fontStyle="bold" fill="#475569" />
          <Text x={width - 30} y={Math.min(height - 22, Math.max(8, originY - 24))} text="X" fontSize={16} fontStyle="bold" fill="#475569" />
          {axisLabels}

          {originX >= 0 && originX <= width && originY >= 0 && originY <= height && (
            <Text x={originX + 7} y={originY + 7} text="0" fontSize={11} fill="#475569" />
          )}

          {/* OBJECTS */}
          {objects2D.map(item => {
            const isSelected = activeSelectedId === item.id;
            
            // ---------------- FUNCTION ----------------
            if (item.object.kind === 'function') {
              const functionObject = item.object as FunctionObject
              const linePoints: number[] = []

              functionObject.points.forEach(([x, y]) => {
                if (!Number.isFinite(x) || !Number.isFinite(y)) return
                const [canvasX, canvasY] = toCanvasPoint(x, y)
                linePoints.push(canvasX, canvasY)
              })

              if (linePoints.length < 4) return null
              
              const currentColor = getRenderColor(item.id, functionObject.color || '', '#4F46E5')

              return (
                <React.Fragment key={item.id}>
                  <Line
                    points={linePoints}
                    stroke={currentColor}
                    dash={getDash(functionObject.line_style, 2.5)}
                    strokeWidth={isSelected ? 4 : 2.5} // Nhấn mạnh độ dày khi click
                    tension={0}
                    lineCap="round"
                    lineJoin="round"
                    hitStrokeWidth={10} // Giúp dễ click vào nét vẽ hơn
                    onClick={(e) => handleObjectClick(e, item.id)}
                    onTap={(e) => handleObjectClick(e, item.id)}
                  />
                  <Rect
                    x={16}
                    y={54}
                    width={Math.min(width - 32, Math.max(180, functionObject.label.length * 9 + 24))}
                    height={36}
                    fill="#FFFFFF"
                    opacity={0.92}
                    cornerRadius={8}
                  />
                  <Text
                    x={28}
                    y={64}
                    text={functionObject.label}
                    fontSize={15}
                    fill="#334155"
                    fontStyle="bold"
                  />
                </React.Fragment>
              )
            }

            // ---------------- POLYGON ----------------
            if (item.object.kind === 'polygon') {
              const polygon = item.object as unknown as PolygonObject
              if (!Array.isArray(polygon.vertices) || polygon.vertices.length < 3 || !polygon.coordinates) return null

              const polygonPoints: number[] = []
              const vertexPositions: { name: string; x: number; y: number }[] = []

              for (const vertex of polygon.vertices) {
                const coordinate = polygon.coordinates[vertex]
                if (!Array.isArray(coordinate) || coordinate.length < 2) return null
                const [canvasX, canvasY] = toCanvasPoint(coordinate[0], coordinate[1])
                polygonPoints.push(canvasX, canvasY)
                vertexPositions.push({ name: vertex, x: canvasX, y: canvasY })
              }

              const currentColor = getRenderColor(item.id, polygon.style?.color || '', '#64748B')
              const polygonLineWidth = Math.max(1, polygon.style?.stroke_width ?? 2.5)
              let polygonFill = resolveColor(polygon.style?.fill_color ?? polygon.style?.fill, '#64748B')
              if (isSelected) polygonFill = '#D1D5DB' // Xám nhạt cho nền khối đa giác khi bị chọn
              const hasFill = Boolean(polygon.style?.fill_color || polygon.style?.fill)

              return (
                <React.Fragment key={item.id}>
                  <Line
                    points={polygonPoints}
                    closed
                    stroke={currentColor}
                    strokeWidth={isSelected ? polygonLineWidth + 2 : polygonLineWidth}
                    dash={getDash(polygon.style?.line_style, polygonLineWidth)}
                    lineCap="round"
                    lineJoin="round"
                    fill={hasFill || isSelected ? polygonFill : undefined} // Fill xám mờ để dễ nhìn
                    opacity={isSelected && !hasFill ? 0.3 : 1}
                    hitStrokeWidth={10}
                    onClick={(e) => handleObjectClick(e, item.id)}
                    onTap={(e) => handleObjectClick(e, item.id)}
                  />
                  {vertexPositions.map(vertex => (
                    <React.Fragment key={`${item.id}-${vertex.name}`}>
                      <Circle x={vertex.x} y={vertex.y} radius={4.5} fill={currentColor} onClick={(e) => handleObjectClick(e, item.id)} onTap={(e) => handleObjectClick(e, item.id)} />
                      <Text x={vertex.x + 7} y={vertex.y - 20} text={vertex.name} fontSize={14} fontStyle="bold" fill={currentColor} onClick={(e) => handleObjectClick(e, item.id)} onTap={(e) => handleObjectClick(e, item.id)} />
                    </React.Fragment>
                  ))}
                  {polygon.label && (
                    <Text
                      x={Math.min(...vertexPositions.map(v => v.x)) + 4}
                      y={Math.min(...vertexPositions.map(v => v.y)) + 4}
                      text={polygon.label}
                      fontSize={12}
                      fill={currentColor}
                      opacity={0.85}
                    />
                  )}
                </React.Fragment>
              )
            }

            // ---------------- CIRCLE ----------------
            if (item.object.kind === 'circle') {
              const obj = item.object as any
              const center = obj.center ?? obj.coordinates?.center ?? [0, 0]
              const radius = Number(obj.radius)
              if (!Array.isArray(center) || !Number.isFinite(radius) || radius <= 0) return null
              const [cx, cy] = toCanvasPoint(Number(center[0]), Number(center[1]))
              const color = getRenderColor(item.id, obj.color || obj.style?.color, '#2563EB')
              return <Circle key={item.id} x={cx} y={cy} radius={radius * scale}
                stroke={color} strokeWidth={isSelected ? 4 : 2.5}
                fill={isSelected ? '#9CA3AF22' : undefined} hitStrokeWidth={12}
                onClick={(e) => handleObjectClick(e, item.id)} onTap={(e) => handleObjectClick(e, item.id)} />
            }

            // ---------------- ELLIPSE ----------------
            if (item.object.kind === 'ellipse') {
              const obj = item.object as any
              const center = obj.center ?? obj.coordinates?.center ?? [0, 0]
              const a = Number(obj.a ?? obj.semi_major_axis ?? obj.major_radius ?? obj.radius_x)
              const b = Number(obj.b ?? obj.semi_minor_axis ?? obj.minor_radius ?? obj.radius_y)
              const angle = Number(obj.rotation ?? obj.angle ?? 0) * Math.PI / 180
              if (!Array.isArray(center) || !Number.isFinite(a) || !Number.isFinite(b) || a <= 0 || b <= 0) return null
              const pts: number[] = []
              for (let i = 0; i <= 120; i++) {
                const t = i * Math.PI * 2 / 120
                const x = Number(center[0]) + a * Math.cos(t) * Math.cos(angle) - b * Math.sin(t) * Math.sin(angle)
                const y = Number(center[1]) + a * Math.cos(t) * Math.sin(angle) + b * Math.sin(t) * Math.cos(angle)
                pts.push(...toCanvasPoint(x, y))
              }
              const color = getRenderColor(item.id, obj.color || obj.style?.color, '#2563EB')
              return <Line key={item.id} points={pts} closed stroke={color} strokeWidth={isSelected ? 4 : 2.5}
                hitStrokeWidth={12} onClick={(e) => handleObjectClick(e, item.id)} onTap={(e) => handleObjectClick(e, item.id)} />
            }

            // ---------------- HYPERBOLA ----------------
            if (item.object.kind === 'hyperbola') {
              const obj = item.object as any
              const center = obj.center ?? obj.coordinates?.center ?? [0, 0]
              const a = Number(obj.a), b = Number(obj.b)
              const orientation = obj.orientation ?? 'horizontal'
              if (!Array.isArray(center) || !Number.isFinite(a) || !Number.isFinite(b) || a <= 0 || b <= 0) return null
              const color = getRenderColor(item.id, obj.color || obj.style?.color, '#2563EB')
              return <React.Fragment key={item.id}>
                {[-1, 1].map(sign => {
                  const pts: number[] = []
                  for (let t = -2.5; t <= 2.5001; t += 0.05) {
                    const x = orientation === 'vertical' ? Number(center[0]) + sign * b * Math.sinh(t) : Number(center[0]) + sign * a * Math.cosh(t)
                    const y = orientation === 'vertical' ? Number(center[1]) + a * Math.cosh(t) : Number(center[1]) + b * Math.sinh(t)
                    pts.push(...toCanvasPoint(x, y))
                  }
                  return <Line key={sign} points={pts} stroke={color} strokeWidth={isSelected ? 4 : 2.5}
                    hitStrokeWidth={12} onClick={(e) => handleObjectClick(e, item.id)} onTap={(e) => handleObjectClick(e, item.id)} />
                })}
              </React.Fragment>
            }

            // ---------------- POINT ----------------
            if (item.object.kind === 'point') {
              const obj = item.object as any
              const pos = obj.position ?? obj.coordinates?.position ?? (obj.coordinates && Object.values(obj.coordinates)[0])
              if (!Array.isArray(pos) || pos.length < 2) return null
              const [x, y] = toCanvasPoint(Number(pos[0]), Number(pos[1]))
              const color = getRenderColor(item.id, obj.color || obj.style?.color, '#DC2626')
              return <React.Fragment key={item.id}>
                <Circle x={x} y={y} radius={isSelected ? 7 : 5} fill={color}
                  onClick={(e) => handleObjectClick(e, item.id)} onTap={(e) => handleObjectClick(e, item.id)} />
                <Text x={x + 8} y={y - 20} text={obj.label || ''} fontSize={14} fontStyle="bold" fill={color}
                  onClick={(e) => handleObjectClick(e, item.id)} onTap={(e) => handleObjectClick(e, item.id)} />
              </React.Fragment>
            }

            // ---------------- LINE ----------------
            if (item.object.kind === 'line') {
              const lineObject = item.object as unknown as LineObject
              const [point1, point2] = lineObject.points
              if (!point1 || !point2) return null

              const [canvasX1, canvasY1] = toCanvasPoint(point1[0], point1[1])
              const [canvasX2, canvasY2] = toCanvasPoint(point2[0], point2[1])
              const currentColor = getRenderColor(item.id, lineObject.color || '', '#2563EB')

              return (
                <React.Fragment key={item.id}>
                  <Line
                    points={[canvasX1, canvasY1, canvasX2, canvasY2]}
                    stroke={currentColor}
                    dash={getDash(lineObject.line_style, 3)}
                    strokeWidth={isSelected ? 5 : 3}
                    lineCap="round"
                    hitStrokeWidth={15}
                    onClick={(e) => handleObjectClick(e, item.id)}
                    onTap={(e) => handleObjectClick(e, item.id)}
                  />
                  <Circle x={canvasX1} y={canvasY1} radius={5} fill={currentColor} onClick={(e) => handleObjectClick(e, item.id)} onTap={(e) => handleObjectClick(e, item.id)} />
                  <Circle x={canvasX2} y={canvasY2} radius={5} fill={currentColor} onClick={(e) => handleObjectClick(e, item.id)} onTap={(e) => handleObjectClick(e, item.id)} />
                  {lineObject.label && (
                    <Text x={canvasX1 + 10} y={canvasY1 - 25} text={lineObject.label} fontSize={15} fill={currentColor} fontStyle="bold" />
                  )}
                </React.Fragment>
              )
            }
            return null
          })}

          {/* EMPTY STATE */}
          {!hasObjects && (
            <Text x={width / 2 - 120} y={height / 2 - 10} text="Chưa có đối tượng trên mặt phẳng" fontSize={15} fill="#94A3B8" />
          )}
        </Layer>
      </Stage>

      {/* ======================================================
          CONTEXT MENU - REMOVE
      ====================================================== */}
      {activeSelectedId && menuPosition && (
        <div
          style={{
            position: 'absolute',
            left: menuPosition.x + 10, // Lệch ra một chút để khỏi vướng con trỏ
            top: menuPosition.y + 10,
            background: 'white',
            padding: '4px',
            borderRadius: '6px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
            border: '1px solid #E5E7EB',
            zIndex: 10,
          }}
        >
          <button
            onClick={() => {
               const message = `hãy xóa đối tượng "${activeSelectedId}" khỏi canvas`;
                if (onSendMessage) onSendMessage(message);
                else if (onRemoveObject) onRemoveObject(activeSelectedId, message);
               setLocalSelection(null);
            }}
            style={{
              background: '#EF4444',
              color: 'white',
              border: 'none',
              padding: '6px 12px',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '13px',
              fontWeight: 500,
            }}
          >
            🗑️ Xóa đối tượng
          </button>
        </div>
      )}

      {/* TOOLBAR */}
      <div style={{ position: 'absolute', top: 12, right: 12, display: 'flex', gap: 6, padding: '6px 8px', background: 'rgba(255,255,255,0.94)', borderRadius: 10, boxShadow: '0 2px 8px rgba(15,23,42,0.08)' }}>
        <button onClick={() => setScale(c => Math.min(200, c * 1.15))} style={{ width: 30, height: 28, border: 'none', borderRadius: 6, background: '#F1F5F9', cursor: 'pointer' }}>+</button>
        <span style={{ minWidth: 58, textAlign: 'center', fontSize: 12, color: '#475569', alignSelf: 'center' }}>{Math.round(scale)} px/u</span>
        <button onClick={() => setScale(c => Math.max(10, c / 1.15))} style={{ width: 30, height: 28, border: 'none', borderRadius: 6, background: '#F1F5F9', cursor: 'pointer' }}>−</button>
        <button onClick={resetView} style={{ height: 28, padding: '0 9px', border: 'none', borderRadius: 6, background: '#EEF2FF', color: '#3730A3', cursor: 'pointer', fontSize: 12, fontWeight: 600 }}>Reset</button>
      </div>

      <div style={{ position: 'absolute', left: 14, bottom: 12, padding: '6px 9px', background: 'rgba(255,255,255,0.88)', border: '1px solid #E2E8F0', borderRadius: 8, fontSize: 11, color: '#64748B' }}>
        Kéo để di chuyển • Cuộn chuột để zoom • Nhấn vào hình để xóa
      </div>
    </div>
  )
}