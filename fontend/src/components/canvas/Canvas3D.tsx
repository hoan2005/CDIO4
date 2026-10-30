import React, { useMemo, useState } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls, Html, Line } from '@react-three/drei'
import type { CanvasObjectWithMeta } from '@/types'

interface Canvas3DProps {
  objects: CanvasObjectWithMeta[]
  onObjectSelect?: (id: string | null, x?: number, y?: number) => void
  selectedObjectId?: string | null
  // Parent should forward the supplied natural-language message to sendMessage().
  onRemoveObject?: (id: string, message?: string) => void
  onSendMessage?: (message: string) => void
}

type P3 = [number, number, number]
type AnyObject = Record<string, any>
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
  }
  return pairs.map(([a,b]) => [point3(vertices[a]), point3(vertices[b])])
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

function RenderObject({ item, selected, onSelect, onRemove }: {
  item: CanvasObjectWithMeta; selected: boolean; onSelect: () => void; onRemove: () => void
}) {
  const obj = item.object as unknown as AnyObject
  const color = colorOf(obj, selected, obj.kind === 'point' ? '#DC2626' : '#334155')
  const stop = (e: any) => { e.stopPropagation(); onSelect() }
  const vertices = obj.vertices as Record<string, P3> | undefined
  const edges = useMemo(() => edgePairs(obj), [obj])
  const anchor: P3 = vertices && Object.keys(vertices).length
    ? point3(vertices[obj.apex_name] ?? Object.values(vertices)[0])
    : obj.kind === 'point' ? point3(obj.position) :
      obj.kind === 'sphere' ? point3(obj.center) :
      obj.kind === 'cone' ? point3(obj.coordinates?.apex) :
      obj.kind === 'plane' ? point3(obj.coordinates?.origin ?? obj.origin) : [0,0,0]

  if (obj.kind === 'point') {
    const p = point3(obj.position ?? obj.coordinates?.position)
    return <group onClick={stop}>
      <mesh position={p}><sphereGeometry args={[selected ? .14 : .09, 16, 16]}/><meshStandardMaterial color={color}/></mesh>
      <Html position={p} center occlude={false} style={{pointerEvents:'none', whiteSpace:'nowrap'}}>
        <span style={{color, fontWeight:700, fontSize:15}}>{obj.label}</span>
      </Html>
      {selected && <DeleteMenu position={p} onDelete={onRemove}/>}
    </group>
  }

  if (obj.kind === 'line') {
    const ps = obj.points
    if (!Array.isArray(ps) || ps.length < 2) return null
    const a = point3(ps[0]), b = point3(ps[1])
    return <group onClick={stop}>
      <Line points={[a,b]} color={color} lineWidth={selected ? 5 : 3} />
      {obj.label && <Html position={a} center occlude={false} style={{pointerEvents:'none'}}><span style={{color,fontWeight:700}}>{obj.label}</span></Html>}
      {selected && <DeleteMenu position={a} onDelete={onRemove}/>}
    </group>
  }

  if (obj.kind === 'cube' || obj.kind === 'pyramid' || obj.kind === 'prism') {
    if (!vertices) return null
    return <group onClick={stop}>
      {edges.map((edge, i) => <Line key={i} points={edge} color={color} lineWidth={selected ? 5 : 2.5} />)}
      {Object.entries(vertices).map(([name, raw]) => {
        const p = point3(raw)
        return <group key={name}>
          <mesh position={p}><sphereGeometry args={[selected ? .105 : .07, 12, 12]}/><meshStandardMaterial color={color}/></mesh>
          <Html position={p} center occlude={false} style={{pointerEvents:'none', whiteSpace:'nowrap'}}>
            <span style={{color:'#111827',fontSize:13,fontWeight:700}}>{name}</span>
          </Html>
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

export default function Canvas3D({ objects, onObjectSelect, selectedObjectId, onRemoveObject, onSendMessage }: Canvas3DProps) {
  const [localSelection, setLocalSelection] = useState<string | null>(null)
  const activeSelectedId = selectedObjectId !== undefined ? selectedObjectId : localSelection
  const objects3D = useMemo(() => objects.filter(item => item.visible && item.object.dimension === '3d'), [objects])

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
    <Canvas camera={{position:[8,8,8], fov:50}} onPointerMissed={clearSelection}>
      <color attach="background" args={['#F8FAFC']}/>
      <ambientLight intensity={0.8}/>
      <directionalLight position={[5,8,5]} intensity={1}/>
      <gridHelper args={[20,20,'#CBD5E1','#E2E8F0']} onClick={(e: any) => { e.stopPropagation(); clearSelection() }}/>
      {objects3D.map(item => <RenderObject key={item.id} item={item}
        selected={activeSelectedId === item.id}
        onSelect={() => select(item.id)} onRemove={() => remove(item.id)}/>)}
      <OrbitControls makeDefault/>
    </Canvas>
    {objects3D.length === 0 && <div style={{position:'absolute',left:0,right:0,top:'50%',textAlign:'center',color:'#94A3B8',pointerEvents:'none'}}>Chưa có đối tượng 3D</div>}
  </div>
}
