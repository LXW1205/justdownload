// Shared types between the Next.js client and the home-server worker.
// These mirror the JSON contract returned by the worker's HTTP endpoints.

export type FormatEntry = {
  format_id: string
  ext: string
  resolution: string
  fps: number | null
  vcodec: string
  acodec: string
  filesize: number | null
  note: string
  kind: "Video+Audio" | "Video Only" | "Audio Only"
  label: string
}

export type VideoInfo = {
  id: string
  title: string
  channel: string
  duration: number
  durationString: string
  uploadDate: string
  thumbnail: string
  webpageUrl: string
  formats: FormatEntry[]
}
