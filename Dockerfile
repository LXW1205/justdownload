# syntax=docker/dockerfile:1.7
# ---------- deps ----------
FROM node:20-alpine AS deps
WORKDIR /app
RUN apk add --no-cache libc6-compat
RUN corepack enable
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# ---------- builder ----------
FROM node:20-alpine AS builder
WORKDIR /app
RUN corepack enable
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN pnpm build

# ---------- runner ----------
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME=0.0.0.0
ENV DOWNLOAD_DIR=/app/downloads
ENV COOKIES_PATH=/app/cookies.txt

# yt-dlp needs python3; ffmpeg is required for merging best video+audio streams.
# tini reaps zombie yt-dlp/ffmpeg processes when downloads are cancelled.
RUN apk add --no-cache python3 py3-pip ffmpeg ca-certificates tini \
 && pip3 install --no-cache-dir --break-system-packages -U yt-dlp \
 && yt-dlp --version

# Standalone Next.js output: server.js + minimal node_modules
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

RUN mkdir -p /app/downloads

EXPOSE 3000
ENTRYPOINT ["/sbin/tini", "--"]
CMD ["node", "server.js"]
