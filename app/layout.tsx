import type { Metadata } from "next"
import { JetBrains_Mono } from "next/font/google"
import { Analytics } from "@vercel/analytics/next"
import "./globals.css"

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono-cli",
  display: "swap",
})

export const metadata: Metadata = {
  title: "justdownload — YouTube Downloader",
  description: "A terminal-styled YouTube video downloader powered by yt-dlp.",
}

export const viewport = {
  themeColor: "#524A4E",
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" className={`${jetbrainsMono.variable} bg-background`}>
      <body className="font-mono antialiased min-h-screen">
        {children}
        {process.env.NODE_ENV === "production" && <Analytics />}
      </body>
    </html>
  )
}
