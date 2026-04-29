# ytdl.term — home server worker

Tiny Node + Express service that runs `yt-dlp` and exposes an HTTP + SSE API. Pair it with the Next.js front-end on Vercel.

## Endpoints

| Method | Path                            | Purpose                                |
| ------ | ------------------------------- | -------------------------------------- |
| GET    | `/health`                       | Liveness probe                         |
| GET    | `/session`                      | Bootstrap session, auto-detect cookies |
| POST   | `/cookies`                      | Upload cookies as JSON `{ cookieText }` |
| DELETE | `/cookies?sessionId=...`        | Clear cookies                          |
| POST   | `/fetch-info`                   | Probe a video — returns metadata       |
| POST   | `/download`                     | Run yt-dlp, stream progress as SSE     |
| GET    | `/file/:sessionId/:filename`    | Stream the finished file (one-shot)    |

## Local dev

```bash
cp .env.example .env
pnpm install
pnpm dev
```

## Production (Ubuntu home server)

See the top-level setup guide for detailed steps. Short version:

```bash
sudo apt install -y nodejs npm ffmpeg python3-pip
sudo pip3 install -U yt-dlp
sudo npm install -g pnpm pm2

cd worker
cp .env.example .env       # edit ALLOWED_ORIGINS
pnpm install --prod=false
pm2 start ecosystem.config.cjs
pm2 save && pm2 startup
```

Put Caddy or Cloudflare Tunnel in front for HTTPS, then set `NEXT_PUBLIC_WORKER_URL=https://worker.your-domain` in Vercel.
