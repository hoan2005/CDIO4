import {
  useAppStore,
} from '@/store/useAppStore'


export default function ObjectList() {

  const canvasObjects =
    useAppStore(
      state => state.canvasObjects
    )


  const toggleObject =
    useAppStore(
      state => state.toggleObject
    )


  const removeObject =
    useAppStore(
      state => state.removeObject
    )


  const clearCanvas =
    useAppStore(
      state => state.clearCanvas
    )


  return (

    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
      }}
    >

      {/* ====================================================
          HEADER
      ===================================================== */}

      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '12px',
          borderBottom: '1px solid #ddd',
        }}
      >

        <strong>
          Đối tượng
        </strong>


        {canvasObjects.length > 0 && (

          <button
            onClick={clearCanvas}
          >
            Xóa tất cả
          </button>

        )}

      </div>


      {/* ====================================================
          OBJECT LIST
      ===================================================== */}

      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '8px',
        }}
      >

        {canvasObjects.length === 0 ? (

          <div
            style={{
              padding: '12px',
              opacity: 0.6,
              textAlign: 'center',
            }}
          >
            Chưa có đối tượng
          </div>

        ) : (

          canvasObjects.map(item => (

            <div
              key={item.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px',
                marginBottom: '6px',
                borderRadius: '8px',
                border: '1px solid #ddd',
              }}
            >

              {/* ==========================================
                  ẨN / HIỆN
              =========================================== */}

              <input
                type="checkbox"
                checked={item.visible}
                onChange={() =>
                  toggleObject(item.id)
                }
              />


              {/* ==========================================
                  THÔNG TIN OBJECT
              =========================================== */}

              <div
                style={{
                  flex: 1,
                  minWidth: 0,
                }}
              >

                <div
                  style={{
                    fontWeight: 500,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {item.object.label}
                </div>


                <div
                  style={{
                    fontSize: '12px',
                    opacity: 0.6,
                  }}
                >
                  {item.object.kind}
                  {' · '}
                  {item.object.dimension}
                </div>

              </div>


              {/* ==========================================
                  XÓA OBJECT
              =========================================== */}

              <button
                onClick={() =>
                  removeObject(item.id)
                }
                title="Xóa đối tượng"
              >
                ×
              </button>

            </div>

          ))

        )}

      </div>

    </div>
  )
}