import { randomUUID } from "node:crypto"
import { tmpdir } from "node:os"
import path from "node:path"
import fs from "node:fs/promises"

// In-memory session store. Persists for the lifetime of the Node process.
// Maps sessionId -> absolute path of cookies.txt on disk.
type Session = {
  cookiesPath?: string
  createdAt: number
}

declare global {
  // eslint-disable-next-line no-var
  var __ytSessions: Map<string, Session> | undefined
}

const sessions: Map<string, Session> = globalThis.__ytSessions ?? new Map()
if (!globalThis.__ytSessions) {
  globalThis.__ytSessions = sessions
}

export function createSessionId(): string {
  const id = randomUUID()
  sessions.set(id, { createdAt: Date.now() })
  return id
}

export function getSession(id: string | null | undefined): Session | undefined {
  if (!id) return undefined
  return sessions.get(id)
}

export function setCookies(id: string, cookiesPath: string) {
  const existing = sessions.get(id) ?? { createdAt: Date.now() }
  sessions.set(id, { ...existing, cookiesPath })
}

export function clearCookies(id: string) {
  const existing = sessions.get(id)
  if (!existing) return
  sessions.set(id, { ...existing, cookiesPath: undefined })
}

export async function getYtdlWorkDir(): Promise<string> {
  const dir = path.join(tmpdir(), "ytdl-term")
  await fs.mkdir(dir, { recursive: true })
  return dir
}

export async function getDownloadsDir(): Promise<string> {
  const dir = path.join(await getYtdlWorkDir(), "downloads")
  await fs.mkdir(dir, { recursive: true })
  return dir
}

export async function getCookiesDir(): Promise<string> {
  const dir = path.join(await getYtdlWorkDir(), "cookies")
  await fs.mkdir(dir, { recursive: true })
  return dir
}

/**
 * Search the process working directory for a `cookies.txt` file (matches the
 * original Python behaviour). Returns absolute path or null.
 */
export async function autoDetectCookies(): Promise<string | null> {
  const candidate = path.join(process.cwd(), "cookies.txt")
  try {
    await fs.access(candidate)
    return candidate
  } catch {
    return null
  }
}
