import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Canvas, useThree } from '@react-three/fiber'
import { OrbitControls, Html, Line } from '@react-three/drei'
import {
  BufferGeometry,
  Float32BufferAttribute,
  Plane,
  Raycaster,
  ShapeUtils,
  Vector2,
  Vector3,
} from 'three'
import type { CanvasObjectWithMeta } from '@/types'
import {
  getCanvasPointTargets,
  type CanvasPointTarget,
} from '@/utils/canvasPointTargets'

interface Canvas3DProps {
  objects: CanvasObjectWithMeta[]
  onObjectSelect?: (id: string | null, x?: number, y?: number) => void
  selectedObjectId?: string | null
  // Parent should forward the supplied natural-language message to sendMessage().
  onRemoveObject?: (id: string, message?: string) => void
  onSendMessage?: (message: string) => void
  onConnectPoints?: (start: string, end: string) => void
}

type P3 = [number, number, number]
type AnyObject = Record<string, any>
interface PointConnection {
  start: CanvasPointTarget
  pointer: [number, number]
  preview: P3
  dragging: boolean
  targetName?: string
}
const SELECTED = '#9CA3AF'
const DEFAULT = '#334155'

function point3(value: any, fallback: P3 = [0, 0, 0]): P3 {
  if (!Array.isArray(value) || value.length < 3) return fallback
  return [Number(value[0]) || 0, Number(value[2]) || 0, Number(value[1]) || 0]
}
function colorOf(obj: AnyObject, selected: boolean, fallback = DEFAULT) {
  if (selected) return SELECTED
  const value = obj.style?.color ?? obj.color
  return typeof value === 'string' && /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.test(value) ? value : fallback
}
function edgePairs(obj: AnyObject): Array<[P3, P3]> {
  const vertices = obj.vertices as Record<string, P3> | undefined
  if (!vertices) return []
  const pairs: Array<[string, string]> = []
  if (obj.kind === 'cube') {
    const names = Object.keys(vertices)
    const sets: Array<[string, string]> = [
      ['A','B'],['B','C'],['C','D'],['D','A'],
      ['A1','B1'],['B1','C1'],['C1','D1'],['D1','A1'],
      ['A','A1'],['B','B1'],['C','C1'],['D','D1'],
      ["A'","B'"],["B'","C'"],["C'","D'"],["D'","A'"],
      ['A',"A'"],['B',"B'"],['C',"C'"],['D',"D'"],
    ]
    for (const [a,b] of sets) if (vertices[a] && vertices[b]) pairs.push([a,b])
    // Fallback for any 8-vertex naming convention.
    if (!pairs.length && names.length >= 8) {
      const v = names
      for (let i=0;i<4;i++) pairs.push([v[i],v[(i+1)%4]], [v[i+4],v[((i+1)%4)+4]], [v[i],v[i+4]])
    }
  } else if (obj.kind === 'pyramid') {
    const supplied = Array.isArray(obj.edges) ? obj.edges : []
    for (const e of supplied) {
      const a = e?.start ?? e?.from, b = e?.end ?? e?.to
      if (vertices[a] && vertices[b]) pairs.push([a,b])
    }
    if (!pairs.length) {
      const base = (obj.base_order ?? Object.keys(vertices).filter(k => k !== obj.apex_name))
      const apex = obj.apex_name ?? Object.keys(vertices).find(k => !base.includes(k))
      for (let i=0;i<base.length;i++) {
        pairs.push([base[i], base[(i+1)%base.length]])
        if (apex && vertices[apex]) pairs.push([apex,base[i]])
      }
    }
  } else if (obj.kind === 'prism') {
    const base = obj.base_order ?? []
    const top = obj.top_order ?? []
    for (let i=0;i<Math.min(base.length, top.length);i++) {
      const j=(i+1)%base.length
      if (vertices[base[i]] && vertices[base[j]]) pairs.push([base[i],base[j]])
      if (vertices[top[i]] && vertices[top[j]]) pairs.push([top[i],top[j]])
      if (vertices[base[i]] && vertices[top[i]]) pairs.push([base[i],top[i]])
    }
  } else if (obj.kind === 'polygon') {
    const order = obj.vertex_order ?? Object.keys(vertices)
    for (let i = 0; i < order.length; i++) {
      const current = order[i]
      const next = order[(i + 1) % order.length]
      if (vertices[current] && vertices[next]) pairs.push([current, next])
    }
  }
  return pairs.map(([a,b]) => [point3(vertices[a]), point3(vertices[b])])
}

function add3(a: P3, b: P3): P3 {
  return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]
}
function scale3(point: P3, scale: number): P3 {
  return [point[0] * scale, point[1] * scale, point[2] * scale]
}
function subtract3(a: P3, b: P3): P3 {
  return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]
}
function length3(point: P3): number {
  return Math.hypot(point[0], point[1], point[2])
}
function normalize3(point: P3): P3 {
  const length = length3(point)
  return length ? scale3(point, 1 / length) : [0, 0, 0]
}
function vertexLabelPosition(point: P3, center: P3): P3 {
  const direction = normalize3(subtract3(point, center))
  const offset: P3 = length3(direction) ? direction : [1, 1, 1]
  return add3(point, scale3(offset, .24))
}
function cross3(a: P3, b: P3): P3 {
  return [
    a[1] * b[2] - a[2] * b[1],
    a[2] * b[0] - a[0] * b[2],
    a[0] * b[1] - a[1] * b[0],
  ]
}

function VertexLabel({ name, point, center, color }: {
  name: string
  point: P3
  center?: P3
  color: string
}) {
  return <Html
    position={center ? vertexLabelPosition(point, center) : add3(point, [.2, .2, .2])}
    center
    occlude={false}
    style={{ pointerEvents: 'none', whiteSpace: 'nowrap' }}
  >
    <span style={{
      display: 'inline-block',
      padding: '3px 8px',
      border: '1px solid #CBD5E1',
      borderRadius: 7,
      background: 'rgba(255,255,255,.96)',
      boxShadow: '0 2px 6px rgba(15,23,42,.16)',
      color,
      fontSize: 12,
      fontWeight: 700,
      lineHeight: 1.2,
    }}>
      {name}
    </span>
  </Html>
}

function DeleteMenu({ position, onDelete }: { position: P3; onDelete: (e: any) => void }) {
  return <Html position={position} center occlude={false} zIndexRange={[100,0]}>
    <button onPointerDown={e => e.stopPropagation()} onClick={onDelete} style={{
      background:'#EF4444', color:'#fff', border:0, borderRadius:6, padding:'6px 10px',
      cursor:'pointer', fontSize:12, fontWeight:600, whiteSpace:'nowrap',
      boxShadow:'0 4px 12px rgba(0,0,0,.2)', pointerEvents:'auto'
    }}>🗑️ Xóa đối tượng</button>
  </Html>
}

function FitCamera({ center, distance }: { center: P3; distance: number }) {
  const { camera } = useThree()
  useEffect(() => {
    camera.position.set(
      center[0] + distance,
      center[1] + distance,
      center[2] + distance,
    )
    camera.lookAt(...center)
    camera.updateProjectionMatrix()
  }, [camera, center, distance])
  return null
}

function PointConnectionEvents({
  connection,
  targets,
  onMove,
  onFinish,
}: {
  connection: PointConnection | null
  targets: CanvasPointTarget[]
  onMove: (pointer: [number, number], preview: P3, targetName?: string) => void
  onFinish: (targetName?: string) => void
}) {
  const { camera, gl } = useThree()
  const start = connection?.start

  useEffect(() => {
    if (!start || !connection?.dragging) return

    const raycaster = new Raycaster()
    const plane = new Plane()
    const normal = new Vector3()
    const rect = gl.domElement.getBoundingClientRect()
    const startPosition = new Vector3(...point3(start.position))

    const getTarget = (clientX: number, clientY: number) => {
      let nearest: CanvasPointTarget | undefined
      let nearestDistance = 22
      for (const point of targets) {
        if (point.name === start.name) continue
        const projected = new Vector3(...point3(point.position)).project(camera)
        const x = rect.left + (projected.x + 1) * rect.width / 2
        const y = rect.top + (1 - projected.y) * rect.height / 2
        const distance = Math.hypot(x - clientX, y - clientY)
        if (distance <= nearestDistance) {
          nearest = point
          nearestDistance = distance
        }
      }
      return nearest
    }

    const getPreview = (clientX: number, clientY: number): P3 => {
      const pointer = new Vector2(
        ((clientX - rect.left) / rect.width) * 2 - 1,
        -((clientY - rect.top) / rect.height) * 2 + 1,
      )
      raycaster.setFromCamera(pointer, camera)
      camera.getWorldDirection(normal)
      plane.setFromNormalAndCoplanarPoint(normal, startPosition)
      const intersection = raycaster.ray.intersectPlane(plane, new Vector3())
      return intersection
        ? [intersection.x, intersection.y, intersection.z]
        : point3(start.position)
    }

    const handlePointerMove = (event: PointerEvent) => {
      const target = getTarget(event.clientX, event.clientY)
      onMove(
        [event.clientX, event.clientY],
        target ? point3(target.position) : getPreview(event.clientX, event.clientY),
        target?.name,
      )
    }
    const handlePointerUp = (event: PointerEvent) => {
      const target = getTarget(event.clientX, event.clientY)
      onFinish(target?.name)
    }

    window.addEventListener('pointermove', handlePointerMove)
    window.addEventListener('pointerup', handlePointerUp)
    return () => {
      window.removeEventListener('pointermove', handlePointerMove)
      window.removeEventListener('pointerup', handlePointerUp)
    }
  }, [camera, connection?.dragging, gl, onFinish, onMove, start, targets])

  return null
}

function RenderObject({ item, selected, onSelect, onRemove, lineExtensionLength }: {
  item: CanvasObjectWithMeta; selected: boolean; onSelect: () => void; onRemove: () => void
  lineExtensionLength: number
}) {
  const obj = item.object as unknown as AnyObject
  const color = colorOf(obj, selected, obj.kind === 'point' ? '#DC2626' : '#334155')
  const stop = (e: any) => { e.stopPropagation(); onSelect() }
  const vertices = obj.vertices as Record<string, P3> | undefined
  const edges = useMemo(() => edgePairs(obj), [obj])
  const polygonGeometry = useMemo(() => {
    if (obj.kind !== 'polygon' || obj.dimension !== '3d' || !vertices) return null
    const order: string[] = obj.vertex_order ?? Object.keys(vertices)
    if (order.length < 3 || order.some(name => !vertices[name])) return null
    const positions = order.map(name => point3(vertices[name]))
    const origin = positions[0]
    const axisU = normalize3(subtract3(positions[1], origin))
    const normal = normalize3(cross3(axisU, subtract3(positions[2], origin)))
    const axisV = normalize3(cross3(normal, axisU))
    const contour = positions.map(position => {
      const offset = subtract3(position, origin)
      return new Vector2(
        offset[0] * axisU[0] + offset[1] * axisU[1] + offset[2] * axisU[2],
        offset[0] * axisV[0] + offset[1] * axisV[1] + offset[2] * axisV[2],
      )
    })
    const geometry = new BufferGeometry()
    geometry.setAttribute(
      'position',
      new Float32BufferAttribute(positions.flat(), 3),
    )
    geometry.setIndex(ShapeUtils.triangulateShape(contour, []).flat())
    geometry.computeVertexNormals()
    return geometry
  }, [obj, vertices])
  useEffect(() => () => polygonGeometry?.dispose(), [polygonGeometry])
  const anchor: P3 = vertices && Object.keys(vertices).length
    ? point3(vertices[obj.apex_name] ?? Object.values(vertices)[0])
    : obj.kind === 'point' ? point3(obj.position) :
      obj.kind === 'sphere' ? point3(obj.center) :
      obj.kind === 'cone' ? point3(obj.coordinates?.apex) :
      obj.kind === 'plane' ? point3(obj.coordinates?.origin ?? obj.origin) : [0,0,0]

  if (obj.kind === 'point') {
    const p = point3(obj.position ?? obj.coordinates?.position)
    const pointName = String(obj.label ?? '')
    return <group onClick={stop}>
      <mesh position={p}><sphereGeometry args={[selected ? .14 : .09, 16, 16]}/><meshStandardMaterial color={color}/></mesh>
      {pointName && <VertexLabel name={pointName} point={p} color={color}/>}
      {selected && <DeleteMenu position={p} onDelete={onRemove}/>}
    </group>
  }

  if (obj.kind === 'line') {
    const ps = obj.points
    if (!Array.isArray(ps) || ps.length < 2) return null
    const a = point3(ps[0]), b = point3(ps[1])
    const direction = normalize3(subtract3(b, a))
    const linePoints: [P3, P3] = obj.extent === 'infinite'
      ? [
          subtract3(a, scale3(direction, lineExtensionLength)),
          add3(b, scale3(direction, lineExtensionLength)),
        ]
      : [a, b]
    return <group onClick={stop}>
      <Line points={linePoints} color={color} lineWidth={selected ? 5 : 3} />
      {selected && <DeleteMenu position={a} onDelete={onRemove}/>}
    </group>
  }

  if (obj.kind === 'polygon' && vertices) {
    const fill = typeof obj.fill_color === 'string' ? obj.fill_color : color
    const vertexPositions = Object.entries(vertices).map(([name, raw]) => [name, point3(raw)] as const)
    const center = vertexPositions.reduce(
      (sum, [, position]) => add3(sum, scale3(position, 1 / vertexPositions.length)),
      [0, 0, 0] as P3,
    )
    return <group onClick={stop}>
      {polygonGeometry && <mesh geometry={polygonGeometry}>
        <meshBasicMaterial color={fill} side={2} transparent opacity={selected ? .32 : .18}/>
      </mesh>}
      {edges.map((edge, index) => <Line key={index} points={edge} color={color} lineWidth={selected ? 5 : 2.5}/>)}
      {vertexPositions.map(([name, position]) => (
        <VertexLabel key={name} name={name} point={position} center={center} color="#111827"/>
      ))}
      {selected && <DeleteMenu position={anchor} onDelete={onRemove}/>}
    </group>
  }

  if (obj.kind === 'angle') {
    const [firstName, vertexName, lastName] = obj.points ?? []
    const coordinates = obj.coordinates ?? {}
    if (!coordinates[firstName] || !coordinates[vertexName] || !coordinates[lastName]) return null
    const first = point3(coordinates[firstName])
    const vertex = point3(coordinates[vertexName])
    const last = point3(coordinates[lastName])
    const u = normalize3(subtract3(first, vertex))
    const v = normalize3(subtract3(last, vertex))
    const dot = Math.max(-1, Math.min(1, u[0] * v[0] + u[1] * v[1] + u[2] * v[2]))
    const radians = Math.acos(dot)
    if (!radians || Math.abs(Math.PI - radians) < 1e-6) return null
    const inPlane = normalize3(subtract3(v, scale3(u, dot)))
    const radius = Number(obj.marker_size) || .35
    const markerPoints: P3[] = []
    if (obj.right_angle) {
      markerPoints.push(
        vertex,
        add3(vertex, scale3(u, radius)),
        add3(vertex, scale3(add3(u, inPlane), radius)),
        add3(vertex, scale3(inPlane, radius)),
      )
    } else {
      for (let step = 0; step <= 24; step++) {
        const theta = radians * step / 24
        markerPoints.push(add3(
          vertex,
          scale3(add3(scale3(u, Math.cos(theta)), scale3(inPlane, Math.sin(theta))), radius),
        ))
      }
    }
    return <group onClick={stop}>
      <Line points={markerPoints} color={color} lineWidth={selected ? 4 : 2.5}/>
      {!obj.right_angle && <Html
        position={add3(vertex, scale3(add3(u, inPlane), radius * .75))}
        center occlude={false} style={{pointerEvents:'none', whiteSpace:'nowrap'}}
      >
        <span style={{color,fontSize:12,fontWeight:600}}>
          {`${obj.label} = ${Math.round(Number(obj.angle_degrees) * 10) / 10}°`}
        </span>
      </Html>}
      {selected && <DeleteMenu position={vertex} onDelete={onRemove}/>}
    </group>
  }

  if (obj.kind === 'equal_segments') {
    const coordinates = obj.coordinates ?? {}
    const count = Math.max(1, Math.min(3, Number(obj.mark_count) || 1))
    const markLines: Array<[P3, P3]> = []
    for (const segment of obj.segments ?? []) {
      const startRaw = coordinates[segment.start]
      const endRaw = coordinates[segment.end]
      if (!startRaw || !endRaw) continue
      const start = point3(startRaw)
      const end = point3(endRaw)
      const direction = normalize3(subtract3(end, start))
      const reference: P3 = Math.abs(direction[1]) < .9 ? [0, 1, 0] : [1, 0, 0]
      const perpendicular = normalize3(cross3(direction, reference))
      for (let index = 0; index < count; index++) {
        const offset = (index - (count - 1) / 2) * .12
        const middle = add3(start, scale3(subtract3(end, start), .5 + offset))
        markLines.push([
          add3(middle, scale3(perpendicular, -.18)),
          add3(middle, scale3(perpendicular, .18)),
        ])
      }
    }
    return <group onClick={stop}>
      {markLines.map((line, index) => <Line key={index} points={line} color={color} lineWidth={selected ? 4 : 2.5}/>)}
      {selected && markLines.length > 0 && <DeleteMenu position={markLines[0][0]} onDelete={onRemove}/>}
    </group>
  }

  if (obj.kind === 'cube' || obj.kind === 'pyramid' || obj.kind === 'prism') {
    if (!vertices) return null
    const vertexPositions = Object.entries(vertices).map(([name, raw]) => [name, point3(raw)] as const)
    const center = vertexPositions.reduce(
      (sum, [, position]) => add3(sum, scale3(position, 1 / vertexPositions.length)),
      [0, 0, 0] as P3,
    )
    return <group onClick={stop}>
      {edges.map((edge, i) => <Line key={i} points={edge} color={color} lineWidth={selected ? 5 : 2.5} />)}
      {vertexPositions.map(([name, p]) => {
        return <group key={name}>
          <mesh position={p}><sphereGeometry args={[selected ? .105 : .07, 12, 12]}/><meshStandardMaterial color={color}/></mesh>
          <VertexLabel name={name} point={p} center={center} color="#111827"/>
        </group>
      })}
      {selected && <DeleteMenu position={anchor} onDelete={onRemove}/>}
    </group>
  }

  if (obj.kind === 'sphere') {
    const center = point3(obj.center ?? obj.coordinates?.center)
    const radius = Number(obj.radius)
    if (!(radius > 0)) return null
    return <group onClick={stop}>
      <mesh position={center}><sphereGeometry args={[radius, 32, 20]}/><meshStandardMaterial color={color} wireframe transparent opacity={selected ? .9 : .65}/></mesh>
      {selected && <DeleteMenu position={center} onDelete={onRemove}/>}
    </group>
  }

  if (obj.kind === 'cone') {
    const apex = point3(obj.coordinates?.apex ?? obj.apex)
    const center = point3(obj.coordinates?.center ?? obj.center)
    const radius = Number(obj.radius), height = Number(obj.height)
    if (!(radius > 0) || !(height > 0)) return null
    // Cone geometry is centered halfway between base center and apex.
    const mid: P3 = [(apex[0]+center[0])/2,(apex[1]+center[1])/2,(apex[2]+center[2])/2]
    return <group onClick={stop}>
      <mesh position={mid} rotation={[0,0,0]}>
        <coneGeometry args={[radius,height,32,1,true]}/>
        <meshStandardMaterial color={color} wireframe transparent opacity={selected ? .95 : .75}/>
      </mesh>
      {selected && <DeleteMenu position={apex} onDelete={onRemove}/>}
    </group>
  }

  if (obj.kind === 'plane') {
    const origin = point3(obj.coordinates?.origin ?? obj.origin)
    return <group onClick={stop}>
      <mesh position={origin} rotation={[-Math.PI/2,0,0]}>
        <planeGeometry args={[10,10]}/>
        <meshBasicMaterial color={color} side={2} transparent opacity={selected ? .35 : .16}/>
      </mesh>
      <gridHelper args={[10,10,color,'#CBD5E1']} position={origin}/>
      {selected && <DeleteMenu position={origin} onDelete={onRemove}/>}
    </group>
  }

  return null
}

export default function Canvas3D({
  objects,
  onObjectSelect,
  selectedObjectId,
  onRemoveObject,
  onSendMessage,
  onConnectPoints,
}: Canvas3DProps) {
  const [localSelection, setLocalSelection] = useState<string | null>(null)
  const [connection, setConnection] = useState<PointConnection | null>(null)
  const connectionRef = useRef<PointConnection | null>(null)
  const lastPointPress = useRef<{ name: string; time: number } | null>(null)
  const activeSelectedId = selectedObjectId !== undefined ? selectedObjectId : localSelection
  const objects3D = useMemo(() => objects.filter(item => item.visible && item.object.dimension === '3d'), [objects])
  const pointTargets = useMemo(
    () => getCanvasPointTargets(objects, '3d'),
    [objects],
  )

  const handlePointPointerDown = (event: any, point: CanvasPointTarget) => {
    const activeConnection = connectionRef.current
    if (activeConnection) {
      if (activeConnection.start.name === point.name && !activeConnection.dragging) {
        event.stopPropagation()
        event.target.setPointerCapture?.(event.pointerId)
        const nextConnection = {
          ...activeConnection,
          dragging: true,
          pointer: [event.nativeEvent.clientX, event.nativeEvent.clientY] as [number, number],
        }
        connectionRef.current = nextConnection
        setConnection(nextConnection)
      }
      return
    }

    const now = Date.now()
    const previous = lastPointPress.current
    if (previous?.name === point.name && now - previous.time <= 600) {
      event.stopPropagation()
      event.target.setPointerCapture?.(event.pointerId)
      const nextConnection: PointConnection = {
        start: point,
        pointer: [event.nativeEvent.clientX, event.nativeEvent.clientY],
        preview: point3(point.position),
        dragging: false,
      }
      connectionRef.current = nextConnection
      setConnection(nextConnection)
      setLocalSelection(null)
      lastPointPress.current = null
      return
    }
    lastPointPress.current = { name: point.name, time: now }
  }

  const handleConnectionMove = useCallback((
    pointer: [number, number],
    preview: P3,
    targetName?: string,
  ) => {
    const current = connectionRef.current
    if (!current) return
    const nextConnection = { ...current, pointer, preview, targetName }
    connectionRef.current = nextConnection
    setConnection(nextConnection)
  }, [])
  const handleConnectionFinish = useCallback((targetName?: string) => {
    const current = connectionRef.current
    if (current && targetName) {
      onConnectPoints?.(current.start.name, targetName)
    }
    connectionRef.current = null
    setConnection(null)
  }, [onConnectPoints])

  const view = useMemo(() => {
    const positions: P3[] = []
    for (const item of objects3D) {
      const object = item.object as unknown as AnyObject
      if (object.vertices && typeof object.vertices === 'object') {
        positions.push(...Object.values(object.vertices).map(value => point3(value)))
      } else if (object.kind === 'point' && object.position) {
        positions.push(point3(object.position))
      } else if (object.kind === 'sphere' && object.center) {
        positions.push(point3(object.center))
      } else if (object.kind === 'line' && Array.isArray(object.points)) {
        positions.push(...object.points.slice(0, 2).map((position: unknown) => point3(position)))
      }
    }
    if (!positions.length) return { center: [0, 0, 0] as P3, distance: 8 }
    const minimum: P3 = [0, 1, 2].map(axis => Math.min(...positions.map(point => point[axis]))) as P3
    const maximum: P3 = [0, 1, 2].map(axis => Math.max(...positions.map(point => point[axis]))) as P3
    const center = scale3(add3(minimum, maximum), .5)
    const extent = Math.max(maximum[0] - minimum[0], maximum[1] - minimum[1], maximum[2] - minimum[2], 1)
    return { center, distance: extent * 1.8 }
  }, [objects3D])

  const select = (id: string) => {
    setLocalSelection(id)
    onObjectSelect?.(id)
  }
  const clearSelection = () => {
    setLocalSelection(null)
    onObjectSelect?.(null)
  }
  const remove = (id: string) => {
    const message = `hãy xóa đối tượng "${id}" khỏi canvas`
    if (onSendMessage) onSendMessage(message)
    else onRemoveObject?.(id, message)
    setLocalSelection(null)
    onObjectSelect?.(null)
  }

  return <div style={{width:'100%', height:'100%', minHeight:400, position:'relative'}}>
    <Canvas camera={{
      position:[
        view.center[0] + view.distance,
        view.center[1] + view.distance,
        view.center[2] + view.distance,
      ],
      fov:50,
      far:10000,
    }} onPointerMissed={clearSelection}>
      <color attach="background" args={['#F8FAFC']}/>
      <ambientLight intensity={0.8}/>
      <directionalLight position={[5,8,5]} intensity={1}/>
      <gridHelper args={[20,20,'#CBD5E1','#E2E8F0']} onClick={(e: any) => { e.stopPropagation(); clearSelection() }}/>
      {objects3D.map(item => <RenderObject key={item.id} item={item}
        selected={activeSelectedId === item.id}
        lineExtensionLength={Math.max(view.distance * 3, 10)}
        onSelect={() => select(item.id)} onRemove={() => remove(item.id)}/>)}
      {connection && (
        <>
          {pointTargets.map(point => {
            const isStart = point.name === connection.start.name
            const isTarget = point.name === connection.targetName
            return (
              <mesh
                key={`connection-target-${point.name}`}
                position={point3(point.position)}
                renderOrder={10}
              >
                <sphereGeometry args={[isTarget ? .2 : .15, 16, 16]} />
                <meshBasicMaterial
                  color={isTarget ? '#22C55E' : isStart ? '#2563EB' : '#F59E0B'}
                  transparent
                  opacity={isTarget ? .9 : .5}
                  depthTest={false}
                  depthWrite={false}
                />
              </mesh>
            )
          })}
          <Line
            points={[point3(connection.start.position), connection.preview]}
            color={connection.targetName ? '#16A34A' : '#2563EB'}
            lineWidth={3}
            dashed={!connection.targetName}
            dashSize={.15}
            gapSize={.1}
          />
          <Html position={connection.preview} center style={{ pointerEvents: 'none' }}>
            <span style={{
              whiteSpace: 'nowrap',
              padding: '4px 8px',
              borderRadius: 6,
              background: 'rgba(255,255,255,.95)',
              color: '#1D4ED8',
              fontSize: 12,
            }}>
              {connection.dragging
                ? 'Kéo đến điểm được tô sáng rồi thả'
                : 'Kéo từ điểm xanh đến điểm khác để vẽ'}
            </span>
          </Html>
        </>
      )}
      {pointTargets.map(point => (
        <mesh
          key={`point-target-${point.name}`}
          position={point3(point.position)}
          onPointerDown={(event) => handlePointPointerDown(event, point)}
        >
          <sphereGeometry args={[.16, 12, 12]} />
          <meshBasicMaterial transparent opacity={0} depthWrite={false} />
        </mesh>
      ))}
      <PointConnectionEvents
        connection={connection}
        targets={pointTargets}
        onMove={handleConnectionMove}
        onFinish={handleConnectionFinish}
      />
      <OrbitControls makeDefault target={view.center}/>
      <FitCamera center={view.center} distance={view.distance}/>
    </Canvas>
    {!connection && pointTargets.length > 0 && (
      <div style={{
        position: 'absolute',
        top: 12,
        left: 12,
        zIndex: 5,
        padding: '5px 8px',
        borderRadius: 6,
        background: 'rgba(255,255,255,.9)',
        color: '#64748B',
        fontSize: 12,
        pointerEvents: 'none',
      }}>
        Nhấp đúp vào một điểm rồi kéo đến điểm khác để nối
      </div>
    )}
    {objects3D.length === 0 && <div style={{position:'absolute',left:0,right:0,top:'50%',textAlign:'center',color:'#94A3B8',pointerEvents:'none'}}>Chưa có đối tượng 3D</div>}
  </div>
}
