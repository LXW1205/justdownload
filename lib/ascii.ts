export function asciiBar(percent: number, width = 24): string {
  const p = Math.max(0, Math.min(100, percent))
  const filled = Math.round((p / 100) * width)
  const empty = width - filled
  return `[${"█".repeat(filled)}${"░".repeat(empty)}] ${p.toFixed(0).padStart(3, " ")}%`
}

export function formatBytes(bytes: number | null | undefined): string {
  if (bytes == null) return ""
  const units = ["B", "KB", "MB", "GB", "TB"]
  let n = bytes
  let i = 0
  while (n >= 1024 && i < units.length - 1) {
    n /= 1024
    i++
  }
  return `${n.toFixed(n >= 10 || i === 0 ? 0 : 1)} ${units[i]}`
}
