-- AgenticStack.app
-- Launches ~/bin/agentic-up.sh in a new Terminal window.
-- Spotlight inherits a minimal PATH, so we prepend Homebrew paths
-- (both Apple Silicon and Intel) inside the do script payload.

tell application "Terminal"
	activate
	do script "export PATH=/opt/homebrew/bin:/usr/local/bin:$PATH && ~/bin/agentic-up.sh"
end tell
