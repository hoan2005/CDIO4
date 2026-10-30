import React, { useState, useCallback, useRef, useEffect } from 'react'

export interface Viewport {
  x:     number   // offset pixel
  y:     number
  scale: number   // px per math unit
}

const DEFAULT_VIEWPORT: Viewport = { x: 0, y: 0, scale: 60 }

/**
 * Hook quản lý viewport của canvas toán học.
 */
export function useCanvasViewport(containerRef: React.RefObject<HTMLDivElement | null>) {
  const [viewport, setViewport] = useState<Viewport>(DEFAULT_VIEWPORT)
  const isPanning = useRef(false)
  const lastMouse = useRef({ x: 0, y: 0 })

  // Chuyển tọa độ toán học -> pixel
  const mathToPixel = useCallback(
    (mx: number, my: number, width: number, height: number) => ({
      px: width  / 2 + mx * viewport.scale + viewport.x,
      py: height / 2 - my * viewport.scale + viewport.y,
    }),
    [viewport]
  )

  // Chuyển pixel -> tọa độ toán học
  const pixelToMath = useCallback(
    (px: number, py: number, width: number, height: number) => ({
      mx: (px - width  / 2 - viewport.x) / viewport.scale,
      my: (height / 2 - py + viewport.y) / viewport.scale,
    }),
    [viewport]
  )

  // ĐÃ SỬA: Dùng containerRef ở đây giúp hết gạch vàng + chặn scroll trang chuẩn bài
  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const targetWheel = (e: WheelEvent) => {
      e.preventDefault() // Chặn scroll trang hoàn toàn hợp lệ khi bind trực tiếp
      const factor = e.deltaY < 0 ? 1.1 : 0.9
      setViewport(v => ({
        ...v,
        scale: Math.min(Math.max(v.scale * factor, 10), 500),
      }))
    }

    // Lắng nghe sự kiện wheel trực tiếp từ phần tử DOM với passive: false
    container.addEventListener('wheel', targetWheel, { passive: false })
    
    return () => {
      container.removeEventListener('wheel', targetWheel)
    }
  }, [containerRef])

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button === 1 || (e.button === 0 && e.altKey)) {
      isPanning.current = true
      lastMouse.current = { x: e.clientX, y: e.clientY }
    }
  }, [])

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isPanning.current) return
    const dx = e.clientX - lastMouse.current.x
    const dy = e.clientY - lastMouse.current.y
    lastMouse.current = { x: e.clientX, y: e.clientY }
    setViewport(v => ({ ...v, x: v.x + dx, y: v.y + dy }))
  }, [])

  const handleMouseUp = useCallback(() => {
    isPanning.current = false
  }, [])

  const resetViewport = useCallback(() => setViewport(DEFAULT_VIEWPORT), [])

  return {
    viewport,
    mathToPixel,
    pixelToMath,
    // Không cần return handleWheel nữa vì useEffect ở trên đã tự xử lý rồi
    handleMouseDown,
    handleMouseMove,
    handleMouseUp,
    resetViewport,
  }
}