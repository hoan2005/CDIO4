import React, { useEffect, useMemo, useRef, useState } from 'react'

import {
  Stage,
  Layer,
  Line,
  Circle,
  Text,
  Rect,
} from 'react-konva'

import type {
  AngleObject,
  CanvasObjectWithMeta,
  EqualSegmentsObject,
  FunctionObject,
} from '@/types'
import {
  getCanvasPointTargets,
  type CanvasPointTarget,
} from '@/utils/canvasPointTargets'

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

function clipInfiniteLine(
  first: [number, number],
  second: [number, number],
  width: number,
  height: number,
): [[number, number], [number, number]] | null {
  const [x, y] = first
  const dx = second[0] - x
  const dy = second[1] - y
  const intersections: Array<[number, number]> = []
  const addIfInside = (candidateX: number, candidateY: number) => {
    if (
      candidateX < -1e-6 || candidateX > width + 1e-6
      || candidateY < -1e-6 || candidateY > height + 1e-6
    ) return
    const point: [number, number] = [
      Math.min(width, Math.max(0, candidateX)),
      Math.min(height, Math.max(0, candidateY)),
    ]
    if (!intersections.some(([px, py]) => Math.hypot(px - point[0], py - point[1]) < 1e-6)) {
      intersections.push(point)
    }
  }

  if (dx !== 0) {
    for (const edgeX of [0, width]) {
      const t = (edgeX - x) / dx
      addIfInside(edgeX, y + t * dy)
    }
  }
  if (dy !== 0) {
    for (const edgeY of [0, height]) {
      const t = (edgeY - y) / dy
      addIfInside(x + t * dx, edgeY)
    }
  }

  return intersections.length >= 2
    ? [intersections[0], intersections[1]]
    : null
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
  onConnectPoints?: (start: string, end: string) => void
}

// ============================================================
// OBJECT INTERFACES
// ============================================================

interface LineObject {
  id: string
  kind: 'line'
  dimension: '2d'
  points: [number, number][]
  extent?: 'segment' | 'infinite'
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
  onSendMessage,
  onConnectPoints,
}: Canvas2DProps) {

  const containerRef = useRef<HTMLDivElement>(null)
  const [viewportSize, setViewportSize] = useState({ width, height })

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const observer = new ResizeObserver(([entry]) => {
      const { width: nextWidth, height: nextHeight } = entry.contentRect
      if (nextWidth <= 0 || nextHeight <= 0) return
      setViewportSize(current =>
        current.width === nextWidth && current.height === nextHeight
          ? current
          : { width: nextWidth, height: nextHeight },
      )
    })

    observer.observe(container)
    return () => observer.disconnect()
  }, [])

  const canvasWidth = viewportSize.width
  const canvasHeight = viewportSize.height

  // Local state dự phòng (nếu không dùng Zustand cho việc selection UI point)
  const [localSelection, setLocalSelection] = useState<{id: string, x: number, y: number} | null>(null)
  
  const activeSelectedId = selectedObjectId !== undefined ? selectedObjectId : localSelection?.id
  const menuPosition = localSelection

  const [scale, setScale] = useState(40)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [isDragging, setIsDragging] = useState(false)
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 })
  const [connection, setConnection] = useState<{
    start: CanvasPointTarget
    pointer: [number, number]
    dragging: boolean
  } | null>(null)
  const lastPointPress = useRef<{ name: string; time: number } | null>(null)

  const objects2D = useMemo(() => {
    return objects.filter(
      item =>
        item.visible &&
        item.object.dimension === '2d'
    )
  }, [objects])
  const pointTargets = useMemo(
    () => getCanvasPointTargets(objects, '2d'),
    [objects],
  )

  const originX = canvasWidth / 2 + pan.x
  const originY = canvasHeight / 2 + pan.y

  const toCanvasPoint = (x: number, y: number): [number, number] => {
    return [originX + x * scale, originY - y * scale]
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
    const right = 1 + (canvasWidth - originX) / scale
    const bottom = -1 - (canvasHeight - originY) / scale
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
        <Line key={`grid-x-${x}`} points={[canvasX, 0, canvasX, canvasHeight]} stroke="#E2E8F0" strokeWidth={1} />
      )
    }

    for (let y = Math.floor(startY / step) * step; y <= endY; y += step) {
      if (y === 0) continue
      const [, canvasY] = toCanvasPoint(0, y)
      lines.push(
        <Line key={`grid-y-${y}`} points={[0, canvasY, canvasWidth, canvasY]} stroke="#E2E8F0" strokeWidth={1} />
      )
    }
    return lines
  }, [canvasWidth, canvasHeight, originX, originY, scale])


  const axisLabels = useMemo(() => {
    const labels: React.ReactNode[] = []
    const left = Math.floor((-originX) / scale) - 1
    const right = Math.ceil((canvasWidth - originX) / scale) + 1
    const bottom = Math.floor(-(canvasHeight - originY) / scale) - 1
    const top = Math.ceil(originY / scale) + 1
    const step = scale < 12 ? 5 : scale < 22 ? 2 : 1

    for (let x = Math.floor(left / step) * step; x <= right; x += step) {
      if (x === 0) continue
      const [canvasX, axisY] = toCanvasPoint(x, 0)
      if (canvasX < 10 || canvasX > canvasWidth - 25) continue
      labels.push(<Text key={`label-x-${x}`} x={canvasX + 4} y={axisY + 6} text={String(x)} fontSize={11} fill="#64748B" />)
    }

    for (let y = Math.floor(bottom / step) * step; y <= top; y += step) {
      if (y === 0) continue
      const [axisX, canvasY] = toCanvasPoint(0, y)
      if (canvasY < 15 || canvasY > canvasHeight - 15) continue
      labels.push(<Text key={`label-y-${y}`} x={axisX + 8} y={canvasY - 7} text={String(y)} fontSize={11} fill="#64748B" />)
    }

    return labels
  }, [canvasWidth, canvasHeight, originX, originY, scale])


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
    setPan({ x: newOriginX - canvasWidth / 2, y: newOriginY - canvasHeight / 2 })
    
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
    const stage = event.target.getStage()
    if (!stage) return
    const pointer = stage.getPointerPosition()
    if (!pointer) return

    if (connection?.dragging) {
      setConnection({ ...connection, pointer: [pointer.x, pointer.y] })
      return
    }

    if (connection) return
    if (!isDragging) return
    const dx = pointer.x - dragStart.x
    const dy = pointer.y - dragStart.y
    setPan(current => ({ x: current.x + dx, y: current.y + dy }))
    setDragStart({ x: pointer.x, y: pointer.y })
    
    setLocalSelection(null); // Kéo di chuyển -> ẩn menu
  }

  const handlePointTargetMouseDown = (
    event: any,
    point: CanvasPointTarget,
  ) => {
    if (connection) {
      if (connection.start.name === point.name) {
        event.cancelBubble = true
        setConnection({
          ...connection,
          dragging: true,
          pointer: toCanvasPoint(point.position[0], point.position[1]),
        })
      }
      return
    }

    const now = Date.now()
    const previous = lastPointPress.current
    if (previous?.name === point.name && now - previous.time <= 600) {
      event.cancelBubble = true
      const [x, y] = toCanvasPoint(point.position[0], point.position[1])
      setConnection({ start: point, pointer: [x, y], dragging: false })
      setLocalSelection(null)
      lastPointPress.current = null
      return
    }
    lastPointPress.current = { name: point.name, time: now }
  }

  const handleMouseUp = (event: any) => {
    setIsDragging(false)
    if (!connection?.dragging) return

    const stage = event.target.getStage()
    const pointer = stage?.getPointerPosition()
    const endPoint = pointer
      ? pointTargets.find(point => {
          if (point.name === connection.start.name) return false
          const [x, y] = toCanvasPoint(point.position[0], point.position[1])
          return Math.hypot(x - pointer.x, y - pointer.y) <= 22
        })
      : undefined

    if (endPoint) {
      onConnectPoints?.(connection.start.name, endPoint.name)
    }
    setConnection(null)
  }

  const snappedPoint = connection
    ? pointTargets.find(point => {
        if (point.name === connection.start.name) return false
        const [x, y] = toCanvasPoint(point.position[0], point.position[1])
        return Math.hypot(x - connection.pointer[0], y - connection.pointer[1]) <= 22
      })
    : undefined
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
        width: '100%',
        height: '100%',
        position: 'relative',
        overflow: 'hidden',
        background: '#F8FAFC',
      }}
      ref={containerRef}
    >
      <Stage
        width={canvasWidth}
        height={canvasHeight}
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onClick={handleStageClick}
        style={{ cursor: connection ? 'crosshair' : isDragging ? 'grabbing' : 'grab' }}
      >
        <Layer>
          <Rect name="canvas-background" x={0} y={0} width={canvasWidth} height={canvasHeight} fill="#F8FAFC" />
          {gridLines}

          {/* TRỤC X & Y */}
          <Line points={[0, originY, canvasWidth, originY]} stroke="#000000" strokeWidth={1.8} />
          <Line points={[canvasWidth - 12, originY - 6, canvasWidth, originY, canvasWidth - 12, originY + 6]} stroke="#000000" strokeWidth={2} lineCap="round" lineJoin="round" />
          <Line points={[originX, 0, originX, canvasHeight]} stroke="#000000" strokeWidth={1.8} />
          <Line points={[originX - 6, 12, originX, 0, originX + 6, 12]} stroke="#000000" strokeWidth={2} lineCap="round" lineJoin="round" />

          <Text x={Math.min(canvasWidth - 25, Math.max(8, originX + 10))} y={8} text="Y" fontSize={16} fontStyle="bold" fill="#475569" />
          <Text x={canvasWidth - 30} y={Math.min(canvasHeight - 22, Math.max(8, originY - 24))} text="X" fontSize={16} fontStyle="bold" fill="#475569" />
          {axisLabels}

          {originX >= 0 && originX <= canvasWidth && originY >= 0 && originY <= canvasHeight && (
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
                </React.Fragment>
              )
            }

            // ---------------- POLYGON ----------------
            if (item.object.kind === 'polygon') {
              const polygon = item.object as unknown as PolygonObject
              if (!Array.isArray(polygon.vertices) || polygon.vertices.length < 3 || !polygon.coordinates) return null

              const polygonPoints: number[] = []
              const vertexCoordinates: Array<{ name: string; x: number; y: number }> = []

              for (const vertex of polygon.vertices) {
                const coordinate = polygon.coordinates[vertex]
                if (!Array.isArray(coordinate) || coordinate.length < 2) return null
                const [canvasX, canvasY] = toCanvasPoint(coordinate[0], coordinate[1])
                polygonPoints.push(canvasX, canvasY)
                vertexCoordinates.push({ name: vertex, x: coordinate[0], y: coordinate[1] })
              }
              const centroid = vertexCoordinates.reduce(
                (sum, vertex) => ({
                  x: sum.x + vertex.x / vertexCoordinates.length,
                  y: sum.y + vertex.y / vertexCoordinates.length,
                }),
                { x: 0, y: 0 },
              )

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
                  {vertexCoordinates.map(vertex => {
                    const [pointX, pointY] = toCanvasPoint(vertex.x, vertex.y)
                    const directionX = vertex.x - centroid.x
                    const directionY = vertex.y - centroid.y
                    const directionLength = Math.hypot(directionX, directionY) || 1
                    const labelWidth = Math.max(26, vertex.name.length * 8 + 12)
                    const labelX = pointX + directionX / directionLength * 22 - labelWidth / 2
                    const labelY = pointY - directionY / directionLength * 22 - 11

                    return (
                      <React.Fragment key={`${item.id}-${vertex.name}`}>
                        <Circle
                          x={pointX}
                          y={pointY}
                          radius={5}
                          fill={currentColor}
                          stroke="#FFFFFF"
                          strokeWidth={2}
                          onClick={(e) => handleObjectClick(e, item.id)}
                          onTap={(e) => handleObjectClick(e, item.id)}
                        />
                        <Rect
                          x={labelX}
                          y={labelY}
                          width={labelWidth}
                          height={22}
                          cornerRadius={7}
                          fill="#FFFFFF"
                          stroke="#CBD5E1"
                          strokeWidth={1}
                          shadowColor="#0F172A"
                          shadowBlur={4}
                          shadowOpacity={0.12}
                          onClick={(e) => handleObjectClick(e, item.id)}
                          onTap={(e) => handleObjectClick(e, item.id)}
                        />
                        <Text
                          x={labelX}
                          y={labelY}
                          width={labelWidth}
                          height={22}
                          text={vertex.name}
                          align="center"
                          verticalAlign="middle"
                          fontSize={12}
                          fontStyle="bold"
                          fill={currentColor}
                          onClick={(e) => handleObjectClick(e, item.id)}
                          onTap={(e) => handleObjectClick(e, item.id)}
                        />
                      </React.Fragment>
                    )
                  })}
                </React.Fragment>
              )
            }

            if (item.object.kind === 'angle') {
              const angle = item.object as AngleObject
              const [firstName, vertexName, lastName] = angle.points
              const first = angle.coordinates[firstName]
              const vertex = angle.coordinates[vertexName]
              const last = angle.coordinates[lastName]
              if (!first || !vertex || !last || first.length < 2 || vertex.length < 2 || last.length < 2) return null

              const ax = first[0] - vertex[0]
              const ay = first[1] - vertex[1]
              const cx = last[0] - vertex[0]
              const cy = last[1] - vertex[1]
              const firstLength = Math.hypot(ax, ay)
              const lastLength = Math.hypot(cx, cy)
              if (!firstLength || !lastLength) return null
              const ux = ax / firstLength
              const uy = ay / firstLength
              const vx = cx / lastLength
              const vy = cy / lastLength
              const radius = angle.marker_size ?? 0.35
              const marker: number[] = []

              if (angle.right_angle) {
                const corners = [
                  [vertex[0], vertex[1]],
                  [vertex[0] + ux * radius, vertex[1] + uy * radius],
                  [vertex[0] + (ux + vx) * radius, vertex[1] + (uy + vy) * radius],
                  [vertex[0] + vx * radius, vertex[1] + vy * radius],
                ]
                corners.forEach(([x, y]) => marker.push(...toCanvasPoint(x, y)))
              } else {
                const start = Math.atan2(uy, ux)
                let delta = Math.atan2(vy, vx) - start
                while (delta > Math.PI) delta -= 2 * Math.PI
                while (delta < -Math.PI) delta += 2 * Math.PI
                for (let step = 0; step <= 24; step++) {
                  const theta = start + delta * step / 24
                  marker.push(...toCanvasPoint(
                    vertex[0] + radius * Math.cos(theta),
                    vertex[1] + radius * Math.sin(theta),
                  ))
                }
              }

              const color = getRenderColor(item.id, angle.color || '', '#2563EB')
              const labelPoint = toCanvasPoint(
                vertex[0] + (ux + vx) * radius * 0.75,
                vertex[1] + (uy + vy) * radius * 0.75,
              )
              return <React.Fragment key={item.id}>
                <Line points={marker} stroke={color} strokeWidth={isSelected ? 3.5 : 2}
                  lineCap="round" lineJoin="round" hitStrokeWidth={12}
                  onClick={(e) => handleObjectClick(e, item.id)} onTap={(e) => handleObjectClick(e, item.id)} />
                {!angle.right_angle && <Text x={labelPoint[0] + 4} y={labelPoint[1] - 16}
                  text={`${angle.label} = ${Math.round(angle.angle_degrees * 10) / 10}°`}
                  fontSize={12} fill={color} onClick={(e) => handleObjectClick(e, item.id)} />}
              </React.Fragment>
            }

            if (item.object.kind === 'equal_segments') {
              const marks = item.object as EqualSegmentsObject
              const color = getRenderColor(item.id, marks.color || '', '#2563EB')
              return <React.Fragment key={item.id}>
                {marks.segments.map((segment, segmentIndex) => {
                  const start = marks.coordinates[segment.start]
                  const end = marks.coordinates[segment.end]
                  if (!start || !end || start.length < 2 || end.length < 2) return null
                  const dx = end[0] - start[0]
                  const dy = end[1] - start[1]
                  const length = Math.hypot(dx, dy)
                  if (!length) return null
                  const perpendicular: [number, number] = [-dy / length, dx / length]
                  const ticks: number[] = []
                  const count = Math.max(1, Math.min(3, marks.mark_count || 1))
                  for (let index = 0; index < count; index++) {
                    const along = 0.5 + (index - (count - 1) / 2) * 0.12
                    const middleX = start[0] + dx * along
                    const middleY = start[1] + dy * along
                    const halfTick = 0.16
                    ticks.push(
                      ...toCanvasPoint(middleX - perpendicular[0] * halfTick, middleY - perpendicular[1] * halfTick),
                      ...toCanvasPoint(middleX + perpendicular[0] * halfTick, middleY + perpendicular[1] * halfTick),
                    )
                  }
                  return <Line key={`${segment.start}-${segment.end}-${segmentIndex}`} points={ticks}
                    stroke={color} strokeWidth={isSelected ? 3.5 : 2.25}
                    hitStrokeWidth={12} onClick={(e) => handleObjectClick(e, item.id)}
                    onTap={(e) => handleObjectClick(e, item.id)} />
                })}
              </React.Fragment>
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
                {obj.label && (() => {
                  const labelWidth = Math.max(26, String(obj.label).length * 8 + 12)
                  const labelX = x + 12
                  const labelY = y - 32
                  return <React.Fragment key={item.id}>
                    <Rect x={labelX} y={labelY} width={labelWidth} height={22} cornerRadius={7}
                      fill="#FFFFFF" stroke="#CBD5E1" strokeWidth={1} shadowColor="#0F172A"
                      shadowBlur={4} shadowOpacity={0.12} />
                    <Text x={labelX} y={labelY} width={labelWidth} height={22} text={String(obj.label)}
                      align="center" verticalAlign="middle" fontSize={12} fontStyle="bold" fill={color}
                      onClick={(e) => handleObjectClick(e, item.id)} onTap={(e) => handleObjectClick(e, item.id)} />
                  </React.Fragment>
                })()}
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
              const isInfinite = lineObject.extent === 'infinite'
              const renderedLine = isInfinite
                ? clipInfiniteLine(
                    [canvasX1, canvasY1],
                    [canvasX2, canvasY2],
                    canvasWidth,
                    canvasHeight,
                  )
                : [[canvasX1, canvasY1], [canvasX2, canvasY2]] as [[number, number], [number, number]]
              if (!renderedLine) return null

              return (
                <React.Fragment key={item.id}>
                  <Line
                    points={renderedLine.flat()}
                    stroke={currentColor}
                    dash={getDash(lineObject.line_style, 3)}
                    strokeWidth={isSelected ? 5 : 3}
                    lineCap="round"
                    hitStrokeWidth={15}
                    onClick={(e) => handleObjectClick(e, item.id)}
                    onTap={(e) => handleObjectClick(e, item.id)}
                  />
                  {!isInfinite && <>
                    <Circle x={canvasX1} y={canvasY1} radius={5} fill={currentColor} onClick={(e) => handleObjectClick(e, item.id)} onTap={(e) => handleObjectClick(e, item.id)} />
                    <Circle x={canvasX2} y={canvasY2} radius={5} fill={currentColor} onClick={(e) => handleObjectClick(e, item.id)} onTap={(e) => handleObjectClick(e, item.id)} />
                  </>}
                </React.Fragment>
              )
            }
            return null
          })}

          {/* EMPTY STATE */}
          {!hasObjects && (
            <Text x={canvasWidth / 2 - 120} y={canvasHeight / 2 - 10} text="Chưa có đối tượng trên mặt phẳng" fontSize={15} fill="#94A3B8" />
          )}

          {!connection && pointTargets.length > 0 && (
            <Text
              x={12}
              y={12}
              text="Nhấp đúp vào một điểm rồi kéo đến điểm khác để nối"
              fontSize={13}
              fill="#64748B"
              listening={false}
            />
          )}

          {connection && (
            <>
              {pointTargets.map(point => {
                const [x, y] = toCanvasPoint(point.position[0], point.position[1])
                const isStart = point.name === connection.start.name
                const isSnapTarget = point.name === snappedPoint?.name
                return (
                  <Circle
                    key={`connection-target-${point.name}`}
                    x={x}
                    y={y}
                    radius={isSnapTarget ? 12 : 9}
                    fill={isSnapTarget ? '#22C55E' : isStart ? '#2563EB' : '#F59E0B'}
                    opacity={isSnapTarget ? 0.9 : 0.55}
                    stroke="#FFFFFF"
                    strokeWidth={2}
                    listening={false}
                  />
                )
              })}
              <Line
                points={[
                  ...toCanvasPoint(connection.start.position[0], connection.start.position[1]),
                  ...(snappedPoint
                    ? toCanvasPoint(snappedPoint.position[0], snappedPoint.position[1])
                    : connection.pointer),
                ]}
                stroke={snappedPoint ? '#16A34A' : '#2563EB'}
                strokeWidth={3}
                dash={snappedPoint ? undefined : [8, 5]}
                listening={false}
              />
              <Text
                x={12}
                y={12}
                text={connection.dragging
                  ? 'Kéo đến điểm được tô sáng rồi thả để vẽ đường thẳng'
                  : 'Kéo từ điểm xanh đến điểm khác để vẽ đường thẳng'}
                fontSize={13}
                fill="#1D4ED8"
                listening={false}
              />
            </>
          )}

          {pointTargets.map(point => {
            const [x, y] = toCanvasPoint(point.position[0], point.position[1])
            return (
              <Circle
                key={`point-target-${point.name}`}
                x={x}
                y={y}
                radius={10}
                fill="transparent"
                onMouseDown={(event) => handlePointTargetMouseDown(event, point)}
              />
            )
          })}
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
      <div style={{ position: 'absolute', bottom: 12, right: 12, display: 'flex', gap: 6, padding: '6px 8px', background: 'rgba(255,255,255,0.94)', borderRadius: 10, boxShadow: '0 2px 8px rgba(15,23,42,0.08)' }}>
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