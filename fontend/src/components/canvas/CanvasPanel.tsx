
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

export default function CanvasPanel({ onHideCanvas }: { onHideCanvas: () => void }) {

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

  const sendMessage =
    useAppStore(
      state =>
        state.sendMessage
    )

  const connectCanvasPoints =
    useAppStore(
      state =>
        state.connectCanvasPoints
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
          display: canvasMode === '2d' ? 'none' : 'flex',
          height: '64px',
          flexShrink: 0,
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
          position: canvasMode === '2d' ? 'absolute' : 'relative',
          top: canvasMode === '2d' ? '12px' : undefined,
          left: canvasMode === '2d' ? '12px' : undefined,
          right: canvasMode === '2d' ? '12px' : undefined,
          zIndex: canvasMode === '2d' ? 20 : undefined,
          minHeight: '58px',
          flexShrink: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 20px',
          background: canvasMode === '2d' ? 'transparent' : '#ffffff',
          borderBottom: canvasMode === '2d' ? 'none' : '1px solid #e2e8f0',
          pointerEvents: canvasMode === '2d' ? 'none' : undefined,
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
              boxShadow: canvasMode === '2d' ? '0 2px 8px rgba(15, 23, 42, 0.08)' : undefined,
              pointerEvents: 'auto',
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

        {canvasMode === '3d' && <div
          style={{
            fontSize: '12px',
            color: '#64748b',
          }}
        >

          Không gian 3 chiều • Hình khối • Hình học không gian

        </div>}

        <div style={{ display: 'flex', alignItems: 'center', gap: 8, pointerEvents: 'auto' }}>
          {canvasMode === '2d' && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '7px 12px',
                borderRadius: '999px',
                background: 'rgba(255,255,255,0.96)',
                border: '1px solid #e2e8f0',
                boxShadow: '0 2px 8px rgba(15, 23, 42, 0.08)',
                fontSize: '12px',
                color: '#475569',
              }}
            >
              <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#22c55e' }} />
              Sẵn sàng minh họa
            </div>
          )}
          <button
            type="button"
            onClick={onHideCanvas}
            style={{
              padding: '8px 12px',
              borderRadius: 9,
              border: '1px solid #e2e8f0',
              background: '#ffffff',
              color: '#475569',
              boxShadow: '0 2px 8px rgba(15, 23, 42, 0.08)',
              fontSize: 12,
              fontWeight: 600,
              cursor: 'pointer',
              whiteSpace: 'nowrap',
            }}
          >
            Ẩn minh họa
          </button>
        </div>

      </div>


      {/* ====================================================
          CANVAS AREA
      ===================================================== */}

      <div
        style={{
          flex: 1,
          minHeight: 0,
          position: 'relative',
          padding: canvasMode === '2d' ? 0 : '16px',
          background: canvasMode === '2d' ? '#F8FAFC' : '#f1f5f9',
          overflow: 'hidden',
        }}
      >

        <div
          style={{
            width: '100%',
            height: '100%',
            position: 'relative',
            overflow: 'hidden',
            borderRadius: canvasMode === '2d' ? 0 : '14px',
            background: '#ffffff',
            border: canvasMode === '2d' ? 'none' : '1px solid #e2e8f0',
            boxShadow: canvasMode === '2d' ? 'none' : '0 4px 12px rgba(15, 23, 42, 0.06)',
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
              onSendMessage={sendMessage}
              onConnectPoints={connectCanvasPoints}
            />

          ) : (

            <Canvas3D
              objects={
                canvasObjects
              }
              onSendMessage={sendMessage}
              onConnectPoints={connectCanvasPoints}
            />

          )}

          {/* ==================================================
              CANVAS LABEL
          ================================================== */}

          {canvasMode === '3d' && <div
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

            KHÔNG GIAN 3D

          </div>}

        </div>

      </div>


      {/* ====================================================
          FOOTER
      ===================================================== */}

      <div
        style={{
          display: canvasMode === '2d' ? 'none' : 'flex',
          height: '34px',
          flexShrink: 0,
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
