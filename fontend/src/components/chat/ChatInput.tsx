import { useEffect, useRef, useState } from 'react'
import { useAppStore } from '@/store/useAppStore'
import AttachmentPreview from './AttachmentPreview'

const IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp']
const RECORDING_TYPES = ['audio/webm;codecs=opus', 'audio/ogg;codecs=opus', 'audio/mp4']
const MIB = 1024 * 1024

export default function ChatInput() {

  const [text, setText] = useState('')
  const [image, setImage] = useState<File>()
  const [audio, setAudio] = useState<Blob>()
  const [mediaError, setMediaError] = useState('')
  const [recordingState, setRecordingState] = useState<'idle' | 'starting' | 'recording' | 'stopping'>('idle')
  const recorderRef = useRef<MediaRecorder | null>(null)
  const cancelRecording = useRef<(() => void) | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => () => cancelRecording.current?.(), [])

  const sendMessage =
    useAppStore(state => state.sendMessage)

  const deleteConversation =
    useAppStore(state => state.deleteConversation)

  const isLoading =
    useAppStore(state => state.isLoading)

  const canSend = !isLoading && recordingState === 'idle' && Boolean(text.trim() || image || audio)

  const stopRecording = () => {
    const recorder = recorderRef.current
    if (recorder?.state === 'recording') {
      setRecordingState('stopping')
      recorder.stop()
    }
  }

  const startRecording = async () => {
    setMediaError('')
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setMediaError('Ghi âm cần trình duyệt hỗ trợ microphone trên HTTPS hoặc localhost.')
      return
    }
    const mimeType = RECORDING_TYPES.find(type => MediaRecorder.isTypeSupported(type))
    if (!mimeType) {
      setMediaError('Trình duyệt chưa hỗ trợ định dạng ghi âm tương thích.')
      return
    }

    setRecordingState('starting')
    let stream: MediaStream | undefined
    let timeout: number | undefined
    let cancelled = false
    const release = () => {
      window.clearTimeout(timeout)
      stream?.getTracks().forEach(track => track.stop())
      recorderRef.current = null
      cancelRecording.current = null
    }
    cancelRecording.current = () => {
      cancelled = true
      if (recorderRef.current?.state === 'recording') recorderRef.current.stop()
      release()
    }

    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      if (cancelled) {
        stream.getTracks().forEach(track => track.stop())
        return
      }
      const recorder = new MediaRecorder(stream, { mimeType, audioBitsPerSecond: 64000 })
      const chunks: Blob[] = []
      recorderRef.current = recorder
      recorder.ondataavailable = event => {
        if (event.data.size) chunks.push(event.data)
      }
      recorder.onerror = () => {
        if (cancelled) return
        cancelled = true
        release()
        setRecordingState('idle')
        setMediaError('Ghi âm bị gián đoạn. Hãy thử lại.')
      }
      recorder.onstop = () => {
        if (cancelled) return
        release()
        setRecordingState('idle')
        const recording = new Blob(chunks, { type: recorder.mimeType || mimeType })
        if (!recording.size || recording.size > 2 * MIB) {
          setMediaError('Bản ghi rỗng hoặc vượt quá 2 MiB. Hãy ghi âm lại.')
          return
        }
        setAudio(recording)
      }
      recorder.start()
      setRecordingState('recording')
      timeout = window.setTimeout(stopRecording, 60_000)
    } catch {
      if (cancelled) return
      release()
      setRecordingState('idle')
      setMediaError('Không mở được microphone. Hãy kiểm tra quyền truy cập và thiết bị.')
    }
  }

  const handleSubmit = async () => {

    if (!canSend) return


    // Xóa input ngay khi gửi
    setText('')
    setImage(undefined)
    setAudio(undefined)
    setMediaError('')
    if (textareaRef.current) {
      textareaRef.current.style.height = '88px'
      textareaRef.current.style.overflowY = 'hidden'
    }


    try {

      await sendMessage(text.trim(), image || audio ? { image, audio } : undefined)

    } catch (error) {

      console.error(
        'Không thể gửi message:',
        error
      )

    }
  }


  const handleKeyDown = (
    event: React.KeyboardEvent<HTMLTextAreaElement>
  ) => {
    if (event.nativeEvent.isComposing) return

    // Enter để gửi
    if (
      event.key === 'Enter' &&
      !event.shiftKey
    ) {

      event.preventDefault()

      handleSubmit()

    }
  }


  return (

    <div
      style={{
        width: '100%',
        boxSizing: 'border-box',
      }}
    >

      <div
        style={{
          display: 'flex',
          justifyContent: 'flex-end',
          marginBottom: '8px',
        }}
      >
        <button
          type="button"
          onClick={() => void deleteConversation()}
          disabled={isLoading}
          aria-label="Xóa hội thoại và tất cả đối tượng trên hình"
          style={{
            padding: '7px 11px',
            border: '1px solid #FECACA',
            borderRadius: '9px',
            background: isLoading ? '#F1F5F9' : '#FEF2F2',
            color: isLoading ? '#94A3B8' : '#B91C1C',
            fontSize: '12px',
            fontWeight: 600,
            cursor: isLoading ? 'not-allowed' : 'pointer',
          }}
        >
          🗑️ Xóa hội thoại và hình vẽ
        </button>
      </div>

      {/* Gợi ý nhập câu hỏi */}

      <div
        style={{
          marginBottom: '8px',
          paddingLeft: '4px',
          fontSize: '12px',
          color: '#64748B',
        }}
      >
        💡 Bạn có thể hỏi về bài học, công thức hoặc cách giải
      </div>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
        <label style={{ fontSize: 12 }}>
          Chọn ảnh đề bài
          <input
            type="file"
            accept={IMAGE_TYPES.join(',')}
            disabled={isLoading}
            style={{ display: 'block', maxWidth: 200 }}
            onChange={event => {
              const file = event.currentTarget.files?.[0]
              event.currentTarget.value = ''
              if (!file) return
              if (!IMAGE_TYPES.includes(file.type) || !file.size || file.size > 5 * MIB) {
                setMediaError('Chọn ảnh JPG, PNG hoặc WebP có dung lượng tối đa 5 MiB.')
                return
              }
              setMediaError('')
              setImage(file)
            }}
          />
        </label>
        <button
          type="button"
          disabled={isLoading || recordingState === 'starting' || recordingState === 'stopping'}
          onClick={recordingState === 'recording' ? stopRecording : () => void startRecording()}
          style={{ padding: '5px 9px', border: '1px solid #CBD5E1', borderRadius: 8, fontSize: 12 }}
        >
          {recordingState === 'recording' ? 'Dừng ghi âm' :
            recordingState === 'starting' ? 'Đang mở microphone…' :
            recordingState === 'stopping' ? 'Đang lưu bản ghi…' : 'Ghi âm (tối đa 60 giây)'}
        </button>
      </div>
      {recordingState === 'recording' && <div role="status">Đang ghi âm…</div>}
      {mediaError && <div role="alert" style={{ color: '#B91C1C', fontSize: 12 }}>{mediaError}</div>}
      {image && (
        <div style={{ marginBottom: 8 }}>
          <AttachmentPreview blob={image} kind="image" />
          <button type="button" onClick={() => setImage(undefined)}>Bỏ ảnh</button>
        </div>
      )}
      {audio && (
        <div style={{ marginBottom: 8 }}>
          <AttachmentPreview blob={audio} kind="audio" />
          <button type="button" onClick={() => setAudio(undefined)}>Bỏ bản ghi</button>
        </div>
      )}
      {(image || audio) && (
        <div style={{ marginBottom: 8, color: '#64748B', fontSize: 12 }}>
          Ảnh và bản ghi có thể được gửi tới Groq hoặc Google Gemini khi bạn bấm Gửi.
        </div>
      )}

      {/* Ô nhập + nút gửi */}

      <div
        style={{
          display: 'flex',
          alignItems: 'flex-end',
          gap: '10px',
          padding: '10px',
          background: '#FFFFFF',
          border: '1px solid #CBD5E1',
          borderRadius: '16px',
          boxShadow: '0 2px 8px rgba(15, 23, 42, 0.06)',
        }}
      >

        <textarea
          ref={textareaRef}
          value={text}
          onChange={event => {
            setText(event.target.value)
            const textarea = event.currentTarget
            textarea.style.height = 'auto'
            textarea.style.height = `${Math.min(textarea.scrollHeight, 160)}px`
            textarea.style.overflowY = textarea.scrollHeight > 160 ? 'auto' : 'hidden'
          }}
          onKeyDown={handleKeyDown}
          disabled={isLoading}
          placeholder={
            isLoading
              ? 'AI đang trả lời...'
              : 'Nhập câu hỏi của bạn...'
          }
          rows={3}
          style={{
            flex: 1,
            resize: 'none',
            minHeight: '76px',
            maxHeight: '160px',
            padding: '12px',
            border: 'none',
            outline: 'none',
            background: 'transparent',
            color: '#1E293B',
            fontSize: '15px',
            lineHeight: 1.5,
            fontFamily: 'inherit',
            overflowY: 'hidden',
          }}
        />


        <button
          onClick={handleSubmit}
          disabled={!canSend}
          aria-label="Gửi câu hỏi"
          style={{
            minWidth: '82px',
            height: '44px',
            padding: '0 16px',
            borderRadius: '12px',
            border: 'none',
            background:
              !canSend
                ? '#CBD5E1'
                : '#4F46E5',
            color: '#FFFFFF',
            fontSize: '14px',
            fontWeight: 600,
            cursor:
              !canSend
                ? 'not-allowed'
                : 'pointer',
            transition: 'background 0.2s ease',
          }}
        >
          {isLoading ? 'Đang xử lý...' : 'Gửi'}
        </button>

      </div>


      {/* Hướng dẫn phím */}

      <div
        style={{
          marginTop: '7px',
          textAlign: 'center',
          fontSize: '11px',
          color: '#94A3B8',
        }}
      >
        Enter để gửi • Shift + Enter để xuống dòng
      </div>

    </div>
  )
}
