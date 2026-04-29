import { randomUUID } from "node:crypto"
import path from "node:path"
import fs from "node:fs/promises"

// In-memory session store. Maps sessionId -> per-session metadata.
// Survives the lifetime of the worker process.
type Session = {
  cookiesPath?: string
  createdAt: number
}

const sessions = new Map<string, Session>()

const WORK_DIR = process.env.WORK_DIR || "/tmp/ytdl-term"

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

export async function getWorkDir(): Promise<string> {
  await fs.mkdir(WORK_DIR, { recursive: true })
  return WORK_DIR
}

export async function getDownloadsDir(): Promise<string> {
  const dir = path.join(await getWorkDir(), "downloads")
  await fs.mkdir(dir, { recursive: true })
  return dir
}

export async function getCookiesDir(): Promise<string> {
  const dir = path.join(await getWorkDir(), "cookies")
  await fs.mkdir(dir, { recursive: true })
  return dir
}

/**
 * Auto-detect a `cookies.txt` placed alongside the worker (handy for power users).
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
