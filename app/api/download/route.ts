import { spawn } from "node:child_process"
import path from "node:path"
import fs from "node:fs/promises"
import { getWritableCookiesPath, ensureDownloadDir } from "@/lib/yt-dlp"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"

export async function POST(req: Request) {
  let body: any
  try {
    body = await req.json()
  } catch {
    return new Response(JSON.stringify({ error: "Invalid JSON body" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    })
  }
  const url: string | undefined = body?.url
  const formatId: string | undefined = body?.formatId
  if (!url) {
    return new Response(JSON.stringify({ error: "Missing url" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    })
  }

  const cookies = await getWritableCookiesPath()
  const downloadDir = await ensureDownloadDir()

  // Stable, unique-but-readable output template.
  // yt-dlp will fill in %(title)s / %(ext)s. We capture the eventual filename
  // by tailing the "[Merger]" / "Destination:" lines and by listing the dir.
  const stem = `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
  const outputTemplate = path.join(downloadDir, `${stem}__%(title).80B.%(ext)s`)

  const args: string[] = [
    "--no-playlist",
    "--newline",
    "--progress",
    "--no-colors",
    "--restrict-filenames",
    "--js-runtimes",
    "node",
    "-o",
    outputTemplate,
  ]
  if (formatId && formatId !== "best") args.push("--format", formatId)
  if (cookies) args.push("--cookies", cookies)
  args.push(url)

  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      const encoder = new TextEncoder()
      const send = (event: string, data: unknown) => {
        const payload = typeof data === "string" ? data : JSON.stringify(data)
        controller.enqueue(encoder.encode(`event: ${event}\ndata: ${payload}\n\n`))
      }

      send("status", {
        line: `$ yt-dlp ${args.map((a) => (a.includes(" ") ? `"${a}"` : a)).join(" ")}`,
      })

      let proc: ReturnType<typeof spawn>
      try {
        proc = spawn("yt-dlp", args, { stdio: ["ignore", "pipe", "pipe"] })
      } catch {
        send("error", {
          message:
            "yt-dlp not found inside the container. Rebuild with: docker compose up --build",
        })
        send("done", { ok: false })
        controller.close()
        return
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
        const code = (err as NodeJS.ErrnoException).code
        const msg =
          code === "ENOENT"
            ? "yt-dlp not found inside the container. Rebuild with: docker compose up --build"
            : err.message
        send("error", { message: msg })
        send("done", { ok: false })
        controller.close()
      })

      proc.on("close", async (code) => {
        if (code !== 0) {
          send("error", { message: `yt-dlp exited with code ${code}` })
          send("done", { ok: false })
          controller.close()
          return
        }
        try {
          const entries = await fs.readdir(downloadDir)
          // Final file name starts with our stem prefix.
          const match = entries.find((name) => name.startsWith(stem + "__"))
          if (!match) {
            send("error", { message: "Download finished but output file not found." })
            send("done", { ok: false })
          } else {
            send("file", { filename: match })
            send("done", { ok: true, filename: match })
          }
        } catch (e: any) {
          send("error", { message: e?.message ?? String(e) })
          send("done", { ok: false })
        } finally {
          controller.close()
        }
      })

      // Cancel yt-dlp if the client disconnects.
      const onAbort = () => {
        try {
          proc.kill("SIGTERM")
        } catch {
          /* ignore */
        }
      }
      req.signal.addEventListener("abort", onAbort, { once: true })
    },
  })

  return new Response(stream, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  })
}
