import path from "node:path"
import fs from "node:fs/promises"

// All paths resolved at request time so they pick up env vars set by docker-compose.
export function getDownloadDir(): string {
  return process.env.DOWNLOAD_DIR || "/app/downloads"
}

export function getCookiesPath(): string {
  return process.env.COOKIES_PATH || "/app/cookies.txt"
}

export async function ensureDownloadDir(): Promise<string> {
  const dir = getDownloadDir()
  await fs.mkdir(dir, { recursive: true })
  return dir
}

export async function detectCookies(): Promise<string | null> {
  const p = getCookiesPath()
  try {
    const stat = await fs.stat(p)
    if (stat.isFile() && stat.size > 0) return p
  } catch {
    /* not present */
  }
  return null
}

/**
 * Copies the read-only cookies file to /tmp so yt-dlp can safely
 * "write" (update) it if it wants to, without crashing.
 */
export async function getWritableCookiesPath(): Promise<string | null> {
  const p = await detectCookies()
  if (!p) return null
  try {
    const writablePath = path.join(
      "/tmp",
      `cookies_${Date.now()}_${Math.random().toString(36).slice(2, 8)}.txt`,
    )
    await fs.copyFile(p, writablePath)
    return writablePath
  } catch {
    return p // Fallback to original if copy fails
  }
}

export function formatDuration(seconds: number): string {
  if (!seconds || !isFinite(seconds)) return "--:--"
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  const pad = (n: number) => n.toString().padStart(2, "0")
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`
}

export function formatUploadDate(raw: string | undefined): string {
  if (!raw || raw.length !== 8) return raw ?? ""
  return `${raw.slice(0, 4)}-${raw.slice(4, 6)}-${raw.slice(6, 8)}`
}

export function buildLabel(f: any): {
  kind: "Video+Audio" | "Video Only" | "Audio Only"
  label: string
} {
  const hasVideo = f.vcodec && f.vcodec !== "none"
  const hasAudio = f.acodec && f.acodec !== "none"
  const kind = hasVideo && hasAudio ? "Video+Audio" : hasVideo ? "Video Only" : "Audio Only"
  const ext = f.ext ?? "?"
  const res = f.resolution ?? (f.height ? `${f.height}p` : "audio")
  const note = f.format_note ?? ""
  const fps = f.fps ? `${f.fps}fps` : ""
  const parts = [`[${ext}]`, res, `(${kind})`]
  if (note) parts.push(`- ${note}`)
  if (fps) parts.push(`- ${fps}`)
  return { kind, label: parts.join(" ") }
}

// Sanitise to a safe basename so the file route can't be tricked into ../ traversal.
export function safeBasename(name: string): string {
  return path.basename(name).replace(/[\\/]/g, "")
}
