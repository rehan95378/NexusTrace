import { useState } from 'react'
import '../styles/UploadPanel.css'

export default function UploadPanel({ apiBase, token, onSuccess }) {
  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [result, setResult] = useState(null)

  async function handleUpload(e) {
    e.preventDefault()
    if (!file) return

    setUploading(true)
    setProgress(0)
    const formData = new FormData()
    formData.append('file', file)

    try {
      const res = await fetch(`${apiBase}/ingest/upload`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      })

      if (!res.ok) throw new Error('Upload failed')
      const data = await res.json()

      setResult(data)
      setProgress(100)
      setFile(null)

      onSuccess({
        filename: file.name,
        timestamp: new Date(),
        type: file.type,
        size: file.size,
        result: data,
      })

      setTimeout(() => setResult(null), 5000)
    } catch (err) {
      alert('Upload error: ' + err.message)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="upload-panel">
      <form onSubmit={handleUpload}>
        <label className="file-input-label">
          <span className="icon">📄</span>
          <span className="text">{file ? file.name : 'Choose file'}</span>
          <input
            type="file"
            accept=".csv,.json,.pdf"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            disabled={uploading}
            hidden
          />
        </label>
        <button type="submit" className="btn-upload" disabled={!file || uploading}>
          {uploading ? `Uploading ${progress}%` : 'Upload & Extract'}
        </button>
      </form>

      {result && (
        <div className="upload-result success">
          <p>✓ Extracted {result.entities} entities</p>
          <p>✓ Found {result.relationships} relationships</p>
          <p>ℹ {result.review_queue} items in review</p>
        </div>
      )}
    </div>
  )
}
