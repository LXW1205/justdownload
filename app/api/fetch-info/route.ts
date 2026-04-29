import { NextResponse } from "next/server"
import { spawn } from "node:child_process"
import { buildLabel, detectCookies, formatDuration, formatUploadDate } from "@/lib/yt-dlp"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"

function runYtDlpJson(url: string, cookiesPath: string | null): Promise<string> {
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
      if (code === 0) resolve(stdout)
      else reject(new Error(stderr.trim() || `yt-dlp exited with code ${code}`))
    })
  })
}

export async function POST(req: Request) {
  let body: any
  try {
    body = await req.json()
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 })
  }
  const url: string | undefined = body?.url?.trim?.()
  if (!url) return NextResponse.json({ error: "Missing url" }, { status: 400 })

  const cookies = await detectCookies()

  try {
    const stdout = await runYtDlpJson(url, cookies)
    const firstLine = stdout.split(/\r?\n/).find((l) => l.trim().startsWith("{"))
    if (!firstLine) {
      return NextResponse.json({ error: "Empty response from yt-dlp" }, { status: 502 })
    }
    const raw = JSON.parse(firstLine)

    const formats = (raw.formats ?? [])
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

    return NextResponse.json({
      info: {
        id: String(raw.id ?? ""),
        title: String(raw.title ?? "Untitled"),
        channel: String(raw.channel ?? raw.uploader ?? "Unknown"),
        duration: Number(raw.duration ?? 0),
        durationString: formatDuration(Number(raw.duration ?? 0)),
        uploadDate: formatUploadDate(raw.upload_date),
        thumbnail: String(raw.thumbnail ?? ""),
        webpageUrl: String(raw.webpage_url ?? url),
        formats,
      },
      cookiesUsed: Boolean(cookies),
    })
  } catch (err: any) {
    const message = err?.message ?? String(err)
    if (message.includes("ENOENT") || message.toLowerCase().includes("not found")) {
      return NextResponse.json(
        { error: "yt-dlp not found inside the container. Rebuild with: docker compose up --build" },
        { status: 500 },
      )
    }
    return NextResponse.json({ error: message }, { status: 500 })
  }
}
