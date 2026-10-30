
import React from 'react'

import {
  useAppStore,
} from '@/store/useAppStore'

import Canvas2D from './Canvas2D'
import Canvas3D from './Canvas3D'


// ============================================================
// CANVAS PANEL
// GIAO DIỆN MINH HỌA TOÁN HỌC
// Logic giữ nguyên
// ============================================================

export default function CanvasPanel() {

  // ==========================================================
  // LẤY STATE TỪ ZUSTAND
  // ==========================================================

  const canvasObjects =
    useAppStore(
      state =>
        state.canvasObjects
    )

  const canvasMode =
    useAppStore(
      state =>
        state.canvasMode
    )

  const setCanvasMode =
    useAppStore(
      state =>
        state.setCanvasMode
    )


  // ==========================================================
  // RENDER
  // ==========================================================

  return (

    <div
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        background: '#f8fafc',
        color: '#1e293b',
        overflow: 'hidden',
      }}
    >

      {/* ====================================================
          HEADER
      ===================================================== */}

      <div
        style={{
          height: '64px',
          flexShrink: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 20px',
          background: '#ffffff',
          borderBottom: '1px solid #e2e8f0',
          boxShadow: '0 1px 3px rgba(15, 23, 42, 0.05)',
        }}
      >

        {/* Tiêu đề */}

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
          }}
        >

          <div
            style={{
              width: '38px',
              height: '38px',
              borderRadius: '10px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: '#eff6ff',
              color: '#2563eb',
              fontSize: '20px',
              fontWeight: 700,
            }}
          >
            ∑
          </div>

          <div>

            <div
              style={{
                fontSize: '16px',
                fontWeight: 700,
                lineHeight: 1.2,
                color: '#0f172a',
              }}
            >
              Bảng minh họa Toán học
            </div>

            <div
              style={{
                marginTop: '3px',
                fontSize: '12px',
                color: '#64748b',
              }}
            >
              Không gian trực quan hóa hình học và đồ thị
            </div>

          </div>

        </div>


        {/* Trạng thái */}

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '7px 12px',
            borderRadius: '999px',
            background: '#f8fafc',
            border: '1px solid #e2e8f0',
            fontSize: '12px',
            color: '#475569',
          }}
        >

          <span
            style={{
              width: '7px',
              height: '7px',
              borderRadius: '50%',
              background: '#22c55e',
            }}
          />

          Sẵn sàng minh họa

        </div>

      </div>


      {/* ====================================================
          TOOLBAR
      ===================================================== */}

      <div
        style={{
          minHeight: '58px',
          flexShrink: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 20px',
          background: '#ffffff',
          borderBottom: '1px solid #e2e8f0',
        }}
      >

        {/* Nhãn chế độ */}

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
          }}
        >

          <span
            style={{
              fontSize: '13px',
              fontWeight: 600,
              color: '#475569',
            }}
          >
            Chế độ minh họa
          </span>


          {/* ==================================================
              MODE SWITCH
          ================================================== */}

          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              padding: '4px',
              borderRadius: '10px',
              background: '#f1f5f9',
              border: '1px solid #e2e8f0',
            }}
          >

            {/* 2D */}

            <button
              onClick={() =>
                setCanvasMode('2d')
              }

              style={{
                border: 'none',
                cursor: 'pointer',
                padding: '8px 16px',
                borderRadius: '7px',
                background:
                  canvasMode === '2d'
                    ? '#2563eb'
                    : 'transparent',
                color:
                  canvasMode === '2d'
                    ? '#ffffff'
                    : '#64748b',
                fontSize: '13px',
                fontWeight:
                  canvasMode === '2d'
                    ? 700
                    : 500,
                transition: 'all 0.2s ease',
              }}
            >
              2D
            </button>


            {/* 3D */}

            <button
              onClick={() =>
                setCanvasMode('3d')
              }

              style={{
                border: 'none',
                cursor: 'pointer',
                padding: '8px 16px',
                borderRadius: '7px',
                background:
                  canvasMode === '3d'
                    ? '#2563eb'
                    : 'transparent',
                color:
                  canvasMode === '3d'
                    ? '#ffffff'
                    : '#64748b',
                fontSize: '13px',
                fontWeight:
                  canvasMode === '3d'
                    ? 700
                    : 500,
                transition: 'all 0.2s ease',
              }}
            >
              3D
            </button>

          </div>

        </div>


        {/* Mô tả chế độ hiện tại */}

        <div
          style={{
            fontSize: '12px',
            color: '#64748b',
          }}
        >

          {canvasMode === '2d'
            ? 'Mặt phẳng tọa độ • Đồ thị • Hình học'
            : 'Không gian 3 chiều • Hình khối • Hình học không gian'}

        </div>

      </div>


      {/* ====================================================
          CANVAS AREA
      ===================================================== */}

      <div
        style={{
          flex: 1,
          minHeight: 0,
          padding: '16px',
          background: '#f1f5f9',
          overflow: 'hidden',
        }}
      >

        <div
          style={{
            width: '100%',
            height: '100%',
            position: 'relative',
            overflow: 'hidden',
            borderRadius: '14px',
            background: '#ffffff',
            border: '1px solid #e2e8f0',
            boxShadow:
              '0 4px 12px rgba(15, 23, 42, 0.06)',
          }}
        >

          {/* ==================================================
              CANVAS
          ================================================== */}

          {canvasMode === '2d' ? (

            <Canvas2D
              objects={
                canvasObjects
              }
            />

          ) : (

            <Canvas3D
              objects={
                canvasObjects
              }
            />

          )}

          {/* ==================================================
              CANVAS LABEL
          ================================================== */}

          <div
            style={{
              position: 'absolute',
              top: '12px',
              left: '12px',
              zIndex: 10,
              pointerEvents: 'none',
              padding: '6px 10px',
              borderRadius: '7px',
              background: 'rgba(255,255,255,0.92)',
              border: '1px solid #e2e8f0',
              boxShadow:
                '0 2px 6px rgba(15, 23, 42, 0.08)',
              fontSize: '11px',
              fontWeight: 600,
              color: '#475569',
            }}
          >

            {canvasMode === '2d'
              ? 'MẶT PHẲNG 2D'
              : 'KHÔNG GIAN 3D'}

          </div>

        </div>

      </div>


      {/* ====================================================
          FOOTER
      ===================================================== */}

      <div
        style={{
          height: '34px',
          flexShrink: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 20px',
          background: '#ffffff',
          borderTop: '1px solid #e2e8f0',
          fontSize: '11px',
          color: '#94a3b8',
        }}
      >

        <span>
          Math Visualization
        </span>

        <span>
          {canvasObjects?.length ?? 0} đối tượng
        </span>

      </div>

    </div>

  )
}

