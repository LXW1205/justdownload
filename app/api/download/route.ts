import { NextRequest } from "next/server"
import { spawn } from "node:child_process"
import path from "node:path"
import fs from "node:fs/promises"
import { getDownloadsDir, getSession, autoDetectCookies } from "@/lib/yt-session"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"

type Body = {
  url: string
  formatId?: string // empty/undefined → "Best Quality (Auto)"
  sessionId?: string
}

function sseChunk(event: string, data: unknown) {
  const payload = typeof data === "string" ? data : JSON.stringify(data)
  return `event: ${event}\ndata: ${payload}\n\n`
}

export async function POST(req: NextRequest) {
  let body: Body
  try {
    body = (await req.json()) as Body
  } catch {
    return new Response(JSON.stringify({ error: "Invalid JSON body" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    })
  }
  if (!body.url) {
    return new Response(JSON.stringify({ error: "Missing url" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    })
  }

  const session = getSession(body.sessionId)
  const cookies = session?.cookiesPath ?? (await autoDetectCookies())

  const downloadsDir = await getDownloadsDir()
  // Unique stem so concurrent downloads don't collide
  const stem = `dl_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
  const outputTemplate = path.join(downloadsDir, `${stem}.%(ext)s`)

  const args: string[] = [
    "--no-playlist",
    "--newline",
    "--progress",
    "--no-colors",
    "-o",
    outputTemplate,
  ]
  if (body.formatId && body.formatId !== "best") {
    args.push("--format", body.formatId)
  }
  if (cookies) {
    args.push("--cookies", cookies)
  }
  args.push(body.url)

  const encoder = new TextEncoder()

  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      let closed = false
      const safeEnqueue = (chunk: string) => {
        if (closed) return
        try {
          controller.enqueue(encoder.encode(chunk))
        } catch {
          /* stream already closed */
        }
      }
      const safeClose = () => {
        if (closed) return
        closed = true
        try {
          controller.close()
        } catch {
          /* already closed */
        }
      }

      safeEnqueue(sseChunk("status", { line: `$ yt-dlp ${args.map((a) => (a.includes(" ") ? `"${a}"` : a)).join(" ")}` }))

      let proc: ReturnType<typeof spawn>
      try {
        proc = spawn("yt-dlp", args, { stdio: ["ignore", "pipe", "pipe"] })
      } catch (err: any) {
        safeEnqueue(sseChunk("error", { message: `yt-dlp not found. Run: pip install yt-dlp` }))
        safeEnqueue(sseChunk("done", { ok: false }))
        safeClose()
        return
      }

      const handleData = (chunk: Buffer, kind: "stdout" | "stderr") => {
        const text = chunk.toString()
        for (const rawLine of text.split(/\r?\n|\r/)) {
          const line = rawLine.trimEnd()
          if (!line) continue

          // Try to extract progress percentage
          const percentMatch = line.match(/(\d{1,3}(?:\.\d+)?)%/)
          if (percentMatch && /\[download\]/.test(line)) {
            const percent = Math.min(100, Math.max(0, parseFloat(percentMatch[1])))
            safeEnqueue(sseChunk("progress", { percent, line }))
            continue
          }

          safeEnqueue(
            sseChunk(kind === "stderr" ? "stderr" : "stdout", { line }),
          )
        }
      }

      proc.stdout?.on("data", (c: Buffer) => handleData(c, "stdout"))
      proc.stderr?.on("data", (c: Buffer) => handleData(c, "stderr"))

      proc.on("error", (err) => {
        const msg = (err as NodeJS.ErrnoException).code === "ENOENT"
          ? "yt-dlp not found. Run: pip install yt-dlp"
          : err.message
        safeEnqueue(sseChunk("error", { message: msg }))
        safeEnqueue(sseChunk("done", { ok: false }))
        safeClose()
      })

      proc.on("close", async (code) => {
        if (code !== 0) {
          safeEnqueue(sseChunk("error", { message: `yt-dlp exited with code ${code}` }))
          safeEnqueue(sseChunk("done", { ok: false }))
          safeClose()
          return
        }

        // find produced file matching stem
        try {
          const entries = await fs.readdir(downloadsDir)
          const match = entries.find((name) => name.startsWith(stem))
          if (!match) {
            safeEnqueue(sseChunk("error", { message: "Download finished but output file not found." }))
            safeEnqueue(sseChunk("done", { ok: false }))
          } else {
            safeEnqueue(sseChunk("file", { filename: match }))
            safeEnqueue(sseChunk("done", { ok: true, filename: match }))
          }
        } catch (e: any) {
          safeEnqueue(sseChunk("error", { message: e?.message ?? String(e) }))
          safeEnqueue(sseChunk("done", { ok: false }))
        }
        safeClose()
      })

      // If the client disconnects, kill the process
      req.signal?.addEventListener("abort", () => {
        try {
          proc.kill("SIGTERM")
        } catch {}
        safeClose()
      })
    },
  })

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  })
}
