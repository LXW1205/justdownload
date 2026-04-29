import { NextResponse } from "next/server"
import { detectCookies } from "@/lib/yt-dlp"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"

export async function GET() {
  const cookies = await detectCookies()
  return NextResponse.json({
    cookiesLoaded: Boolean(cookies),
    cookiesPath: cookies ?? null,
  })
}
