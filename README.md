# justdownload

A terminal-styled YouTube downloader. Single-container Next.js app that wraps `yt-dlp` and `ffmpeg`, runs anywhere Docker runs, and saves completed files straight to a host folder.

![System Preview](/sample_screens/justdownload-1.png)

## Run it

You need [Docker](https://docs.docker.com/get-docker/) with the Compose plugin (any reasonably recent install has it built in).

**First run** — builds the image (installs Node deps, `yt-dlp`, `ffmpeg`):

```bash
docker compose up --build
```

**Every run after that:**

```bash
docker compose up
```

Add `-d` to either to run detached. Stop with `docker compose down`.

Open http://localhost:3000 once it boots.

## Where do my downloads go?

Anything you download lands in `./downloads/` next to `docker-compose.yml`, on the host machine. The folder is bind-mounted into the container at `/app/downloads`, so files persist across rebuilds and are accessible directly from your file manager.

![System Preview](/sample_screens/justdownload-3.png)

## Cookies (optional)

For age-restricted, members-only, or private videos, export a Netscape-format `cookies.txt` from your browser (the "Get cookies.txt LOCALLY" extension works well) and replace the placeholder `cookies.txt` in this folder. The container mounts it read-only at `/app/cookies.txt` and `yt-dlp` picks it up automatically. The status line in the UI tells you whether it was detected.

If you don't need cookies, leave the placeholder file as-is — an empty/comment-only file is ignored.

## Updating yt-dlp

YouTube changes things often and `yt-dlp` ships fixes constantly. To pull the latest version, rebuild:

```bash
docker compose build --no-cache
docker compose up
```

## Configuration

Two env vars, both already set sensibly in `docker-compose.yml`:

| Variable        | Default              | Purpose                                                             |
| --------------- | -------------------- | ------------------------------------------------------------------- |
| `DOWNLOAD_DIR`  | `/app/downloads`     | Where `yt-dlp` writes completed files inside the container.         |
| `COOKIES_PATH`  | `/app/cookies.txt`   | Path to the mounted cookies file. Used only if non-empty.           |

To bind to a different host port, change `"3000:3000"` in `docker-compose.yml` to e.g. `"8080:3000"`.

## Project layout

```
app/                 Next.js App Router pages + API routes
  api/fetch-info/    POST: probe a video, return metadata + format list
  api/download/      POST: spawn yt-dlp, stream progress as SSE
  api/file/[name]/   GET:  download the finished file
  api/status/        GET:  reports whether cookies.txt was detected
components/          Terminal-styled UI panels
lib/yt-dlp.ts        Shared helpers (paths, formatting, label builders)
Dockerfile           Multi-stage build: deps → build → minimal runner
docker-compose.yml   Volume mounts + port + env wiring
downloads/           Host folder where finished files appear
cookies.txt          Optional Netscape cookies, mounted read-only
```

## Stack

Next.js 16 (App Router) · Node 20 (Alpine) · yt-dlp · ffmpeg · Tailwind CSS 4
