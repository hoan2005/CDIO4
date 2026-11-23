import { useEffect, useState } from 'react'

export default function AttachmentPreview({ blob, kind }: { blob: Blob; kind: 'image' | 'audio' }) {
  const [url, setUrl] = useState('')
  useEffect(() => {
    const previewUrl = URL.createObjectURL(blob)
    setUrl(previewUrl)
    return () => URL.revokeObjectURL(previewUrl)
  }, [blob])

  if (!url) return null
  return kind === 'image'
    ? <img src={url} alt="Ảnh đính kèm" style={{ display: 'block', maxWidth: '100%', maxHeight: 180 }} />
    : <audio src={url} aria-label="Bản ghi câu hỏi" controls preload="metadata" style={{ width: 220, maxWidth: '100%' }} />
}
