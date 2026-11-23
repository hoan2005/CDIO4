import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'

// Exercise the canvas handlers with the browser's down -> click ordering.
// Any unconsumed click is delivered to the background, as in the UI.
function canvasHarness(dimension) {
  const source = readFileSync(new URL(`../src/components/canvas/Canvas${dimension}.tsx`, import.meta.url), 'utf8')
  const handler = dimension === '2D' ? 'handlePointTargetClick' : 'handlePointClick'
  const end = dimension === '2D' ? '  const handleMouseUp' : '  const view ='
  const body = source.slice(source.indexOf(`  const ${handler} =`), source.indexOf(end))
  const connections = []
  const state = {
    selectedStartPoint: null,
    lastPointPress: { current: null },
    setSelectedStartPoint(point) { state.selectedStartPoint = point },
    setLocalSelection() {},
    setHoverTarget() {},
    onConnectPoints(a, b) { connections.push([a, b]) },
  }
  const context = vm.createContext(state)
  const js = ts.transpile(body + `\nglobalThis.click = ${handler}`, { target: ts.ScriptTarget.ES2020 })
  vm.runInContext(js, context)
  return {
    state, connections, source,
    click(name) {
      const event = { cancelBubble: false, stopPropagation() { this.cancelBubble = true } }
      context.click(event, { name, position: [0, 0] })
      if (!event.cancelBubble) state.selectedStartPoint = null
    },
  }
}

for (const dimension of ['2D', '3D']) {
  test(`${dimension}: double click retains start; next point connects exactly once`, () => {
    const canvas = canvasHarness(dimension)
    canvas.click('A')
    assert.equal(canvas.state.selectedStartPoint, null)
    canvas.click('A')
    assert.equal(canvas.state.selectedStartPoint?.name, 'A')
    canvas.click('A')
    assert.equal(canvas.state.selectedStartPoint?.name, 'A')
    assert.equal(canvas.connections.length, 0)
    canvas.click('B')
    assert.deepEqual(canvas.connections, [['A', 'B']])
    assert.equal(canvas.state.selectedStartPoint, null)
    assert.equal(canvas.state.lastPointPress.current, null)
  })
}
