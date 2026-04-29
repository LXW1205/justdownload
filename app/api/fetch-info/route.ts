import { NextRequest, NextResponse } from "next/server"
import { spawn } from "node:child_process"
import { getSession, autoDetectCookies } from "@/lib/yt-session"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"

export type FormatEntry = {
  format_id: string
  ext: string
  resolution: string
  fps: number | null
  vcodec: string
  acodec: string
  filesize: number | null
  note: string
  kind: "Video+Audio" | "Video Only" | "Audio Only"
  label: string
}

export type VideoInfo = {
  id: string
  title: string
  channel: string
  duration: number
  durationString: string
  uploadDate: string
  thumbnail: string
  webpageUrl: string
  formats: FormatEntry[]
}

function formatDuration(seconds: number): string {
  if (!seconds || !isFinite(seconds)) return "--:--"
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  const pad = (n: number) => n.toString().padStart(2, "0")
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`
}

function formatUploadDate(raw: string | undefined): string {
  if (!raw || raw.length !== 8) return raw ?? ""
  return `${raw.slice(0, 4)}-${raw.slice(4, 6)}-${raw.slice(6, 8)}`
}

function buildLabel(f: any): { kind: FormatEntry["kind"]; label: string } {
  const hasVideo = f.vcodec && f.vcodec !== "none"
  const hasAudio = f.acodec && f.acodec !== "none"
  const kind: FormatEntry["kind"] = hasVideo && hasAudio ? "Video+Audio" : hasVideo ? "Video Only" : "Audio Only"
  const ext = f.ext ?? "?"
  const res = f.resolution ?? (f.height ? `${f.height}p` : "audio")
  const note = f.format_note ?? ""
  const fps = f.fps ? `${f.fps}fps` : ""
  const parts = [`[${ext}]`, res, `(${kind})`]
  if (note) parts.push(`- ${note}`)
  if (fps) parts.push(`- ${fps}`)
  return { kind, label: parts.join(" ") }
}

function runYtDlpJson(url: string, cookiesPath?: string | null): Promise<{ stdout: string; stderr: string }> {
  return new Promise((resolve, reject) => {
    const args = ["--dump-json", "--no-playlist"]
    if (cookiesPath) args.push("--cookies", cookiesPath)
    args.push(url)

    const proc = spawn("yt-dlp", args, { stdio: ["ignore", "pipe", "pipe"] })

    let stdout = ""
    let stderr = ""
    proc.stdout.on("data", (chunk) => (stdout += chunk.toString()))
    proc.stderr.on("data", (chunk) => (stderr += chunk.toString()))
    proc.on("error", (err) => reject(err))
    proc.on("close", (code) => {
      if (code === 0) resolve({ stdout, stderr })
      else reject(new Error(stderr.trim() || `yt-dlp exited with code ${code}`))
    })
  })
}

export async function POST(req: NextRequest) {
  let body: { url?: string; sessionId?: string }
  try {
    body = await req.json()
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 })
  }
  const url = body.url?.trim()
  if (!url) {
    return NextResponse.json({ error: "Missing url" }, { status: 400 })
  }

  const session = getSession(body.sessionId)
  const cookies = session?.cookiesPath ?? (await autoDetectCookies())

  try {
    const { stdout } = await runYtDlpJson(url, cookies)
    // yt-dlp may emit multiple JSON lines for a playlist; we pass --no-playlist so just take the first
    const firstLine = stdout.split(/\r?\n/).find((l) => l.trim().startsWith("{"))
    if (!firstLine) {
      return NextResponse.json({ error: "Empty response from yt-dlp" }, { status: 502 })
    }
    const raw = JSON.parse(firstLine)

    const formats: FormatEntry[] = (raw.formats ?? [])
      .filter((f: any) => !(f.vcodec === "none" && f.acodec === "none"))
      .map((f: any) => {
        const { kind, label } = buildLabel(f)
        return {
          format_id: String(f.format_id),
          ext: f.ext ?? "",
          resolution: f.resolution ?? (f.height ? `${f.height}p` : "audio"),
          fps: f.fps ?? null,
          vcodec: f.vcodec ?? "none",
          acodec: f.acodec ?? "none",
          filesize: f.filesize ?? f.filesize_approx ?? null,
          note: f.format_note ?? "",
          kind,
          label,
        }
      })

    const info: VideoInfo = {
      id: String(raw.id ?? ""),
      title: String(raw.title ?? "Untitled"),
      channel: String(raw.channel ?? raw.uploader ?? "Unknown"),
      duration: Number(raw.duration ?? 0),
      durationString: formatDuration(Number(raw.duration ?? 0)),
      uploadDate: formatUploadDate(raw.upload_date),
      thumbnail: String(raw.thumbnail ?? ""),
      webpageUrl: String(raw.webpage_url ?? url),
      formats,
    }

    return NextResponse.json({ info, cookiesUsed: Boolean(cookies) })
  } catch (err: any) {
    const message = err?.message ?? String(err)
    if (message.includes("ENOENT") || message.toLowerCase().includes("not found")) {
      return NextResponse.json(
        { error: "yt-dlp not found. Run: pip install yt-dlp", missingBinary: true },
        { status: 500 },
      )
    }
    return NextResponse.json({ error: message }, { status: 500 })
  }
}
