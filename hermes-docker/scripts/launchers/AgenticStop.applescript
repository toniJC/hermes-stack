tell application "Terminal"
	do script "echo '==> Stopping services...' && for p in 7437 8000 8001 8004 8005 8006 8010; do pid=$(lsof -ti :$p 2>/dev/null); if [ -n \"$pid\" ]; then echo \"  killing :$p (pid $pid)\"; echo \"$pid\" | xargs kill -9 2>/dev/null; else echo \"  already stopped :$p\"; fi; done && echo '==> Stopping Langfuse...' && cd ~/projects/langfuse-docker && docker compose down && echo '==> Done.'"
	activate
end tell
