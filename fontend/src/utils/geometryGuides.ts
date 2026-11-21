// Work in scene coordinates so a separately drawn segment or triangle can
// supply the same boundary, even when its vertices are listed in reverse.
import { getCanvasPointTargets } from './canvasPointTargets'
import type { CanvasObjectWithMeta } from '@/types'

export type ScenePoint = [number, number, number]
export const guideKey = (points: ScenePoint[]) =>
  JSON.stringify(points.map(p => p.join(',')).sort())

function collectGuides(
  vertices: Record<string, ScenePoint>, relations: unknown[],
  drawnEdges: Set<string>, drawnFaces: Set<string>, constructions: Record<string, unknown>,
) {
  const edges: ScenePoint[][] = []
  const faces: ScenePoint[][] = []
  function add(names: unknown, count: number) {
    if (!Array.isArray(names) || names.length !== count ||
        !names.every(n => typeof n === 'string' && Object.hasOwnProperty.call(vertices, n))) return
    const points = names.map(n => vertices[n])
    if (new Set(points.map(p => p.join(','))).size !== count) return
    const key = guideKey(points)
    if (count === 3) {
      if (!drawnFaces.has(key)) faces.push(points)
      drawnFaces.add(key)
      for (let i = 0; i < 3; i++) add([names[i], names[(i + 1) % 3]], 2)
    } else {
      if (!drawnEdges.has(key)) edges.push(points)
      drawnEdges.add(key)
    }
  }
  for (const raw of relations) {
    if (!raw || typeof raw !== 'object') continue
    const r = raw as Record<string, unknown>
    for (const field of ['line', 'line_1', 'line_2', 'segment', 'segment_1', 'segment_2']) add(r[field], 2)
    for (const field of ['plane', 'plane_1', 'plane_2']) add(r[field], 3)
    if (['length', 'distance', 'segment_length', 'height', 'radius', 'diameter'].includes(String(r.type ?? r.kind))) add(r.points, 2)
    if ((r.type ?? r.kind) === 'angle' && Array.isArray(r.points) && r.points.length === 3) {
      add(r.points.slice(0, 2), 2)
      add(r.points.slice(1), 2)
    }
    if (Array.isArray(r.points)) {
      const kind = String(r.type)
      if (['equal_length', 'parallel_lines', 'perpendicular_lines'].includes(kind) && r.points.length === 4) {
        add(r.points.slice(0, 2), 2)
        add(r.points.slice(2), 2)
      }
      if (['midpoint', 'point_on_segment', 'point_on_line'].includes(kind)) add(r.points.slice(1), 2)
      if (['isosceles_triangle', 'equilateral_triangle', 'right_triangle', 'parallelogram'].includes(kind)) {
        const names = r.points
        names.forEach((name, i) => add([name, names[(i + 1) % names.length]], 2))
      }
    }
    if (r.type === 'circle_radius') add([r.center, r.point_on_circle ?? r.point_on_circumference ?? r.point], 2)
  }
  for (const [result, raw] of Object.entries(constructions)) {
    if (!raw || typeof raw !== 'object' || !('depends_on' in raw) || !Array.isArray(raw.depends_on) || !('construct' in raw)) continue
    const [a, b, c, d] = raw.depends_on
    switch (raw.construct) {
      case 'midpoint': case 'point_on_line':
        add([a,b], 2); break
      case 'perpendicular_foot':
        add([a,result], 2); add([b,c], 2); break
      case 'plane_perpendicular_foot':
        add([a,result], 2); add([b,c,d], 3); break
      case 'intersection': case 'line_intersection':
        add([a,b], 2); add([c,d], 2); break
      case 'parallel_point': case 'perpendicular_point':
        add([a,b], 2); add([c,result], 2); break
      case 'angle_bisector':
        add([a,b], 2); add([b,c], 2); add([b,result], 2); break
      case 'tangent_point':
        add([a,result], 2); add([b,result], 2); break
    }
  }
  return {edges, faces}
}

export function geometryGuides(
  items: CanvasObjectWithMeta[], dimension: '2d' | '3d',
  project: (position: number[]) => ScenePoint,
  drawnEdges = new Set<string>(), drawnFaces = new Set<string>(),
) {
  const pointsFor = (items: CanvasObjectWithMeta[]) => Object.fromEntries(
    getCanvasPointTargets(items, dimension).map(p => [p.name, project(p.position)]),
  )
  const global = pointsFor(items)
  const layers = []
  for (const item of items) {
    if (!item.visible || item.object.dimension !== dimension) continue
    const obj = item.object as unknown as Record<string, unknown>
    const vertices = {...global, ...pointsFor([item])}
    if (dimension === '2d' && Array.isArray(obj.vertices)) {
      const names = obj.vertices
      names.forEach((name, i) => {
        const a = vertices[name], b = vertices[names[(i + 1) % names.length]]
        if (a && b) drawnEdges.add(guideKey([a,b]))
      })
    }
    if (obj.kind === 'line' && Array.isArray(obj.points) && obj.points.length === 2) {
      drawnEdges.add(guideKey(obj.points.map(project)))
    }
    const relations = [obj.constraints, obj.sketch_measurements, obj.measurement_labels].filter(Array.isArray).flat()
    if (obj.kind === 'angle') relations.push(obj)
    if (obj.kind === 'equal_segments' && Array.isArray(obj.segments)) {
      obj.segments.forEach(s => relations.push({segment: [s.start, s.end]}))
    }
    layers.push({vertices, relations, constructions: (obj.constructions ?? {}) as Record<string, unknown>})
  }
  // Register every visible boundary before deriving any additional strokes.
  return layers.map(l => collectGuides(l.vertices, l.relations, drawnEdges, drawnFaces, l.constructions))
}
