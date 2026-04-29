import { NextRequest, NextResponse } from "next/server"
import path from "node:path"
import fs from "node:fs/promises"
import { createSessionId, getCookiesDir, getSession, setCookies, clearCookies, autoDetectCookies } from "@/lib/yt-session"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"

// GET — initialise a session, report whether a cookies.txt was auto-detected
export async function GET(req: NextRequest) {
  const url = new URL(req.url)
  let sessionId = url.searchParams.get("sessionId") ?? undefined
  let session = getSession(sessionId)
  if (!sessionId || !session) {
    sessionId = createSessionId()
    session = getSession(sessionId)
  }

  // Auto-detect cookies.txt in cwd, mirror Python behaviour
  if (!session?.cookiesPath) {
    const auto = await autoDetectCookies()
    if (auto) setCookies(sessionId!, auto)
  }

  const updated = getSession(sessionId!)
  return NextResponse.json({
    sessionId,
    cookiesLoaded: Boolean(updated?.cookiesPath),
    autoDetected: Boolean(updated?.cookiesPath && (await autoDetectCookies()) === updated.cookiesPath),
  })
}

// POST — upload cookies.txt as multipart/form-data
export async function POST(req: NextRequest) {
  const form = await req.formData()
  const file = form.get("cookies")
  let sessionId = (form.get("sessionId") as string | null) ?? undefined

  if (!sessionId || !getSession(sessionId)) {
    sessionId = createSessionId()
  }

  if (!(file instanceof File)) {
    return NextResponse.json({ error: "No file uploaded" }, { status: 400 })
  }

  const dir = await getCookiesDir()
  const dest = path.join(dir, `${sessionId}.txt`)
  const buf = Buffer.from(await file.arrayBuffer())
  await fs.writeFile(dest, buf)
  setCookies(sessionId!, dest)

  return NextResponse.json({ sessionId, cookiesLoaded: true, filename: file.name })
}

// DELETE — clear cookies for the session
export async function DELETE(req: NextRequest) {
  const url = new URL(req.url)
  const sessionId = url.searchParams.get("sessionId")
  if (!sessionId) return NextResponse.json({ error: "Missing sessionId" }, { status: 400 })
  const session = getSession(sessionId)
  if (session?.cookiesPath) {
    try {
      await fs.unlink(session.cookiesPath)
    } catch {
      // ignore
    }
    clearCookies(sessionId)
  }
  return NextResponse.json({ sessionId, cookiesLoaded: false })
}
