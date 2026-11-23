import type { CanvasObjectWithMeta } from '@/types'
import { getCanvasPointTargets } from './canvasPointTargets'

export function measurementLabels(items: CanvasObjectWithMeta[], dimension: '2d' | '3d') {
  const labels: {key: string; text: string; position: number[]}[] = []
  for (const item of items) {
    const obj = item.object
    if (!item.visible || obj.dimension !== dimension || !obj.measurement_labels?.length) continue
    const targets = new Map(getCanvasPointTargets([item], dimension).map(p => [p.name, p.position]))
    if ('coordinates' in obj && obj.coordinates) {
      for (const [name, point] of Object.entries(obj.coordinates)) {
        if (!targets.has(name) && Array.isArray(point)) targets.set(name, point)
      }
    }
    if ('center_name' in obj && typeof obj.center_name === 'string' && 'center' in obj) {
      targets.set(obj.center_name, obj.center)
    }
    for (const [index, label] of obj.measurement_labels.entries()) {
      const points = label.points.map(name => targets.get(name))
      if (points.some(p => !p)) continue
      const [a, b, c] = points
      let position: number[] | undefined
      if (a && b && c) {
        // Offset inside the angle along its bisector, independent of ray lengths.
        const u = a.map((x, i) => x - b[i])
        const v = c.map((x, i) => x - b[i])
        const lu = Math.hypot(...u), lv = Math.hypot(...v)
        if (lu && lv) position = b.map((x, i) => x + .22 * Math.min(lu, lv) * (u[i]/lu + v[i]/lv))
      } else if (a && b) {
        position = a.map((x, i) => (x + b[i]) / 2)
      } else if (a) {
        position = a
      } else if (label.kind === 'height' && obj.kind === 'cone') {
        position = obj.coordinates.center.map((x, i) => (x + obj.coordinates.apex[i]) / 2)
      } else if ((label.kind === 'radius' || label.kind === 'diameter') &&
                 (obj.kind === 'circle' || obj.kind === 'sphere')) {
        position = [...obj.center]
        if (label.kind === 'radius') position[0] += obj.radius / 2
      }
      if (position) labels.push({key: item.id + ':' + index, text: label.text, position})
    }
  }
  return labels
}
