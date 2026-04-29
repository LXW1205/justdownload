import { createReadStream } from "node:fs"
import fs from "node:fs/promises"
import path from "node:path"
import { Readable } from "node:stream"
import { ensureDownloadDir, safeBasename } from "@/lib/yt-dlp"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"

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

export async function GET(
  _req: Request,
  ctx: { params: Promise<{ filename: string }> },
) {
  const { filename: rawName } = await ctx.params
  const filename = safeBasename(decodeURIComponent(rawName))
  const downloadDir = await ensureDownloadDir()
  const fullPath = path.join(downloadDir, filename)

  // Defence-in-depth: ensure the resolved path stays inside the download dir.
  if (!fullPath.startsWith(downloadDir + path.sep)) {
    return new Response(JSON.stringify({ error: "Invalid path" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    })
  }

  let stat
  try {
    stat = await fs.stat(fullPath)
  } catch {
    return new Response(JSON.stringify({ error: "File not found" }), {
      status: 404,
      headers: { "Content-Type": "application/json" },
    })
  }
  if (!stat.isFile()) {
    return new Response(JSON.stringify({ error: "Not a file" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    })
  }

  const ext = path.extname(filename).slice(1).toLowerCase()
  const mime = MIME[ext] ?? "application/octet-stream"

  // Stream straight from disk; the file stays on the host volume after serve
  // so the user can also grab it from ./downloads.
  const nodeStream = createReadStream(fullPath)
  const webStream = Readable.toWeb(nodeStream) as ReadableStream<Uint8Array>

  return new Response(webStream, {
    status: 200,
    headers: {
      "Content-Type": mime,
      "Content-Length": String(stat.size),
      "Content-Disposition": `attachment; filename="${filename.replace(/"/g, "")}"`,
      "Cache-Control": "no-store",
    },
  })
}
