import { NextRequest, NextResponse } from "next/server"
import path from "node:path"
import fs from "node:fs/promises"
import { createReadStream } from "node:fs"
import { Readable } from "node:stream"
import { getDownloadsDir } from "@/lib/yt-session"

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

export async function GET(_req: NextRequest, ctx: { params: Promise<{ filename: string }> }) {
  const { filename } = await ctx.params
  const safeName = path.basename(filename) // prevent traversal
  const dir = await getDownloadsDir()
  const fullPath = path.join(dir, safeName)

  try {
    const stat = await fs.stat(fullPath)
    if (!stat.isFile()) {
      return NextResponse.json({ error: "Not a file" }, { status: 400 })
    }

    const ext = path.extname(safeName).slice(1).toLowerCase()
    const mime = MIME[ext] ?? "application/octet-stream"

    const nodeStream = createReadStream(fullPath)
    // Convert Node Readable -> Web ReadableStream
    const webStream = Readable.toWeb(nodeStream) as unknown as ReadableStream

    // Schedule deletion after the response is fully consumed
    nodeStream.on("close", async () => {
      try {
        await fs.unlink(fullPath)
      } catch {
        /* ignore */
      }
    })

    return new Response(webStream, {
      headers: {
        "Content-Type": mime,
        "Content-Length": String(stat.size),
        "Content-Disposition": `attachment; filename="${safeName}"`,
        "Cache-Control": "no-store",
      },
    })
  } catch (err: any) {
    if (err?.code === "ENOENT") {
      return NextResponse.json({ error: "File not found or already downloaded." }, { status: 404 })
    }
    return NextResponse.json({ error: err?.message ?? String(err) }, { status: 500 })
  }
}
