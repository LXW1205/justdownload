// pm2 config — `pm2 start ecosystem.config.cjs`
module.exports = {
  apps: [
    {
      name: "ytdl-term-worker",
      script: "node_modules/.bin/tsx",
      args: "src/server.ts",
      cwd: __dirname,
      env: {
        NODE_ENV: "production",
      },
      max_restarts: 10,
      restart_delay: 2000,
      kill_timeout: 5000,
      out_file: "logs/out.log",
      error_file: "logs/err.log",
      merge_logs: true,
      time: true,
    },
  ],
}
