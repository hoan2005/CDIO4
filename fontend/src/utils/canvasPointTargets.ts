import type { CanvasObjectWithMeta } from '@/types'

export interface CanvasPointTarget {
  name: string
  position: number[]
}

export function getCanvasPointTargets(
  objects: CanvasObjectWithMeta[],
  dimension: '2d' | '3d',
): CanvasPointTarget[] {
  const targets = new Map<string, CanvasPointTarget>()
  const add = (name: unknown, position: unknown) => {
    if (
      typeof name !== 'string'
      || !name.trim()
      || !Array.isArray(position)
      || position.length !== (dimension === '2d' ? 2 : 3)
      || position.some(value => typeof value !== 'number' || !Number.isFinite(value))
    ) {
      return
    }

    const pointName = name.trim().replace(/^point_/, '')
    if (!targets.has(pointName)) {
      targets.set(pointName, { name: pointName, position })
    }
  }

  for (const item of objects) {
    if (!item.visible || item.object.dimension !== dimension) continue
    const object = item.object as unknown as Record<string, unknown>

    if (object.kind === 'point') {
      add(object.label, object.position)
    }

    if (
      object.kind === 'line'
      && Array.isArray(object.point_names)
      && Array.isArray(object.points)
    ) {
      const pointNames = object.point_names as unknown[]
      const linePoints = object.points as unknown[]
      pointNames.forEach((name, index) => add(name, linePoints[index]))
    }

    if (
      object.kind === 'polygon'
      && dimension === '2d'
      && Array.isArray(object.vertices)
      && object.coordinates !== null
      && typeof object.coordinates === 'object'
    ) {
      const coordinates = object.coordinates as Record<string, unknown>
      object.vertices.forEach(name => add(name, coordinates[String(name)]))
    }

    if (
      dimension === '3d'
      && object.vertices !== null
      && typeof object.vertices === 'object'
      && !Array.isArray(object.vertices)
    ) {
      const vertices = object.vertices as Record<string, unknown>
      const order = Array.isArray(object.vertex_order)
        ? object.vertex_order
        : Object.keys(vertices)
      order.forEach(name => add(name, vertices[String(name)]))
    }

    if (
      object.coordinates !== null
      && typeof object.coordinates === 'object'
      && !Array.isArray(object.coordinates)
      && ['angle', 'equal_segments'].includes(String(object.kind))
    ) {
      const coordinates = object.coordinates as Record<string, unknown>
      Object.entries(coordinates).forEach(([name, position]) => add(name, position))
    }
  }

  return [...targets.values()]
}
