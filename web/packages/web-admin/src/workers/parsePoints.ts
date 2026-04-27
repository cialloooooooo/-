export interface ParseMessage {
  type: 'progress' | 'result' | 'error'
  progress?: number
  totalLines?: number
  points?: { x: number; y: number; z: number }[]
  is3D?: boolean
  message?: string
}

const PROGRESS_INTERVAL = 20000

self.onmessage = (e: MessageEvent<{ text: string }>) => {
  try {
    const { text } = e.data
    const lines = text.split('\n')
    const total = lines.length
    const points: { x: number; y: number; z: number }[] = []
    let hasZ = false

    for (let i = 0; i < total; i++) {
      const line = lines[i].trim()
      if (!line) continue

      const parts = line.split(/\s+/)
      if (parts.length < 2) continue

      const x = parseFloat(parts[0])
      const y = parseFloat(parts[1])
      const z = parts.length >= 3 ? parseFloat(parts[2]) : 0

      if (isNaN(x) || isNaN(y) || isNaN(z)) continue

      if (z !== 0) hasZ = true
      points.push({ x, y, z })

      if (i > 0 && i % PROGRESS_INTERVAL === 0) {
        self.postMessage({
          type: 'progress',
          progress: Math.round((i / total) * 100),
        } satisfies ParseMessage)
      }
    }

    self.postMessage({
      type: 'result',
      points,
      is3D: hasZ,
      progress: 100,
    } satisfies ParseMessage)
  } catch (err) {
    self.postMessage({
      type: 'error',
      message: err instanceof Error ? err.message : '解析失败',
    } satisfies ParseMessage)
  }
}
