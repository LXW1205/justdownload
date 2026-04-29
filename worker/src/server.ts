import express, { type Request, type Response } from "express"
import cors from "cors"
import { spawn } from "node:child_process"
import path from "node:path"
import fs from "node:fs/promises"
import { createReadStream } from "node:fs"
import {
  autoDetectCookies,
  clearCookies,
  createSessionId,
  getCookiesDir,
  getDownloadsDir,
  getSession,
  setCookies,
} from "./yt-session.js"

const PORT = Number(process.env.PORT || 3001)
const ALLOWED_ORIGINS = (process.env.ALLOWED_ORIGINS || "http://localhost:3000")
  .split(",")
  .map((s) => s.trim())
  .filter(Boolean)

const app = express()

app.use(
  cors({
    origin(origin, cb) {
      // allow same-origin / curl (no origin header)
      if (!origin) return cb(null, true)
      if (ALLOWED_ORIGINS.includes("*") || ALLOWED_ORIGINS.includes(origin)) {
        return cb(null, true)
      }
      cb(new Error(`origin ${origin} not allowed`))
    },
    credentials: false,
  }),
)
app.use(express.json({ limit: "5mb" }))

// ---------- helpers ----------
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

function buildLabel(f: any): { kind: "Video+Audio" | "Video Only" | "Audio Only"; label: string } {
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

function runYtDlpJson(url: string, cookiesPath?: string | null): Promise<string> {
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

// ---------- routes ----------
app.get("/health", (_req, res) => {
  res.json({ ok: true })
})

// Session bootstrap: create a session, auto-detect cookies.txt
app.get("/session", async (req: Request, res: Response) => {
  let sessionId = (req.query.sessionId as string | undefined) ?? undefined
  let session = getSession(sessionId)
  if (!sessionId || !session) {
    sessionId = createSessionId()
    session = getSession(sessionId)
  }
  if (!session?.cookiesPath) {
    const auto = await autoDetectCookies()
    if (auto) setCookies(sessionId!, auto)
  }
  const updated = getSession(sessionId!)
  const auto = await autoDetectCookies()
  res.json({
    sessionId,
    cookiesLoaded: Boolean(updated?.cookiesPath),
    autoDetected: Boolean(updated?.cookiesPath && auto === updated.cookiesPath),
  })
})

// Upload cookies as JSON: { sessionId?, filename, cookieText }
app.post("/cookies", async (req: Request, res: Response) => {
  let { sessionId, filename, cookieText } = req.body ?? {}
  if (typeof cookieText !== "string" || !cookieText.length) {
    return res.status(400).json({ error: "cookieText required" })
  }
  if (!sessionId || !getSession(sessionId)) {
    sessionId = createSessionId()
  }
  const dir = await getCookiesDir()
  const dest = path.join(dir, `${sessionId}.txt`)
  await fs.writeFile(dest, cookieText, "utf8")
  setCookies(sessionId, dest)
  res.json({ sessionId, cookiesLoaded: true, filename: filename || "cookies.txt" })
})

// Clear cookies for a session
app.delete("/cookies", async (req: Request, res: Response) => {
  const sessionId = req.query.sessionId as string | undefined
  if (!sessionId) return res.status(400).json({ error: "Missing sessionId" })
  const session = getSession(sessionId)
  if (session?.cookiesPath) {
    try {
      await fs.unlink(session.cookiesPath)
    } catch {
      /* ignore */
    }
    clearCookies(sessionId)
  }
  res.json({ sessionId, cookiesLoaded: false })
})

// Probe a video: returns metadata + format list as JSON
app.post("/fetch-info", async (req: Request, res: Response) => {
  const url: string | undefined = req.body?.url?.trim()
  const sessionId: string | undefined = req.body?.sessionId
  if (!url) return res.status(400).json({ error: "Missing url" })

  const session = getSession(sessionId)
  const cookies = session?.cookiesPath ?? (await autoDetectCookies())

  try {
    const stdout = await runYtDlpJson(url, cookies)
    const firstLine = stdout.split(/\r?\n/).find((l) => l.trim().startsWith("{"))
    if (!firstLine) return res.status(502).json({ error: "Empty response from yt-dlp" })
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

    res.json({
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
      return res.status(500).json({ error: "yt-dlp not found. Install with: pip install -U yt-dlp" })
    }
    res.status(500).json({ error: message })
  }
})

// Stream the actual download as Server-Sent Events.
app.post("/download", async (req: Request, res: Response) => {
  const url: string | undefined = req.body?.url
  const formatId: string | undefined = req.body?.formatId
  const sessionId: string | undefined = req.body?.sessionId
  if (!url) return res.status(400).json({ error: "Missing url" })

  const session = getSession(sessionId)
  const cookies = session?.cookiesPath ?? (await autoDetectCookies())
  const downloadsDir = await getDownloadsDir()
  const ownerSession = sessionId && getSession(sessionId) ? sessionId : createSessionId()

  const stem = `dl_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
  const sessionDir = path.join(downloadsDir, ownerSession)
  await fs.mkdir(sessionDir, { recursive: true })
  const outputTemplate = path.join(sessionDir, `${stem}.%(ext)s`)

  const args: string[] = ["--no-playlist", "--newline", "--progress", "--no-colors", "-o", outputTemplate]
  if (formatId && formatId !== "best") args.push("--format", formatId)
  if (cookies) args.push("--cookies", cookies)
  args.push(url)

  res.writeHead(200, {
    "Content-Type": "text/event-stream; charset=utf-8",
    "Cache-Control": "no-cache, no-transform",
    Connection: "keep-alive",
    "X-Accel-Buffering": "no",
  })

  const send = (event: string, data: unknown) => {
    res.write(`event: ${event}\ndata: ${typeof data === "string" ? data : JSON.stringify(data)}\n\n`)
  }

  send("status", { line: `$ yt-dlp ${args.map((a) => (a.includes(" ") ? `"${a}"` : a)).join(" ")}` })

  let proc: ReturnType<typeof spawn>
  try {
    proc = spawn("yt-dlp", args, { stdio: ["ignore", "pipe", "pipe"] })
  } catch {
    send("error", { message: "yt-dlp not found. Install with: pip install -U yt-dlp" })
    send("done", { ok: false })
    return res.end()
  }

  const handleData = (chunk: Buffer, kind: "stdout" | "stderr") => {
    const text = chunk.toString()
    for (const rawLine of text.split(/\r?\n|\r/)) {
      const line = rawLine.trimEnd()
      if (!line) continue
      const percentMatch = line.match(/(\d{1,3}(?:\.\d+)?)%/)
      if (percentMatch && /\[download\]/.test(line)) {
        const percent = Math.min(100, Math.max(0, parseFloat(percentMatch[1])))
        send("progress", { percent, line })
        continue
      }
      send(kind === "stderr" ? "stderr" : "stdout", { line })
    }
  }

  proc.stdout?.on("data", (c: Buffer) => handleData(c, "stdout"))
  proc.stderr?.on("data", (c: Buffer) => handleData(c, "stderr"))

  proc.on("error", (err) => {
    const msg =
      (err as NodeJS.ErrnoException).code === "ENOENT"
        ? "yt-dlp not found. Install with: pip install -U yt-dlp"
        : err.message
    send("error", { message: msg })
    send("done", { ok: false })
    res.end()
  })

  proc.on("close", async (code) => {
    if (code !== 0) {
      send("error", { message: `yt-dlp exited with code ${code}` })
      send("done", { ok: false })
      return res.end()
    }
    try {
      const entries = await fs.readdir(sessionDir)
      const match = entries.find((name) => name.startsWith(stem))
      if (!match) {
        send("error", { message: "Download finished but output file not found." })
        send("done", { ok: false })
      } else {
        send("file", { filename: match, sessionId: ownerSession })
        send("done", { ok: true, filename: match })
      }
    } catch (e: any) {
      send("error", { message: e?.message ?? String(e) })
      send("done", { ok: false })
    }
    res.end()
  })

  // Kill yt-dlp if the client disconnects mid-stream
  req.on("close", () => {
    try {
      proc.kill("SIGTERM")
    } catch {}
  })
})

// Serve a finished file once, then delete it from disk.
app.get("/file/:sessionId/:filename", async (req: Request, res: Response) => {
  const sessionId = path.basename(req.params.sessionId)
  const filename = path.basename(req.params.filename)
  const downloadsDir = await getDownloadsDir()
  const fullPath = path.join(downloadsDir, sessionId, filename)

  try {
    const stat = await fs.stat(fullPath)
    if (!stat.isFile()) return res.status(400).json({ error: "Not a file" })

    const MIME: Record<string, string> = {
      mp4: "video/mp4",
      webm: "video/webm",
      mkv: "video/x-matroska",
      mov: "video/quicktime",
      m4a: "audio/mp4",
      mp3: "audio/mpeg",
      opus: "audio/ogg",
      ogg: "audio/ogg",
      wav: "audio/wav",
    }
    const ext = path.extname(filename).slice(1).toLowerCase()
    const mime = MIME[ext] ?? "application/octet-stream"

    res.writeHead(200, {
      "Content-Type": mime,
      "Content-Length": String(stat.size),
      "Content-Disposition": `attachment; filename="${filename}"`,
      "Cache-Control": "no-store",
    })

    const stream = createReadStream(fullPath)
    stream.pipe(res)
    stream.on("close", async () => {
      try {
        await fs.unlink(fullPath)
      } catch {
        /* ignore */
      }
    })
  } catch (err: any) {
    if (err?.code === "ENOENT") return res.status(404).json({ error: "File not found or already downloaded." })
    res.status(500).json({ error: err?.message ?? String(err) })
  }
})

app.listen(PORT, () => {
  console.log(`[ytdl-term-worker] listening on :${PORT}`)
  console.log(`[ytdl-term-worker] allowed origins: ${ALLOWED_ORIGINS.join(", ") || "(none)"}`)
})
