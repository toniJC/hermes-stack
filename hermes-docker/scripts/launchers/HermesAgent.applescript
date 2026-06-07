-- HermesAgent.app
-- Prompts for a workspace folder, then launches `hermes dashboard` in a new
-- Terminal window with WORKSPACE_PATH and HERMES_PROJECT correctly set.
-- mcp-proxy is managed by launchd (com.pirito.engram-mcp-proxy) — no manual restart needed.

try
	set chosenFolder to choose folder with prompt "Select project workspace:"
	set workspacePath to POSIX path of chosenFolder

	-- Strip trailing slash (POSIX path of a folder always ends in /).
	if workspacePath ends with "/" then
		set workspacePath to text 1 thru -2 of workspacePath
	end if

	set projectName to do shell script "basename " & quoted form of workspacePath

	-- Write the workspace path so engram-mcp-proxy-run.sh can cd into it
	-- before spawning engram mcp. This lets mem_current_project detect the project.
	do shell script "printf '%s' " & quoted form of workspacePath & " > ~/.hermes-current-workspace"

	-- Register project in Engram if not already known (idempotent).
	do shell script "/opt/homebrew/bin/engram projects list 2>/dev/null | grep -q '\\b" & projectName & "\\b' || /opt/homebrew/bin/engram save 'Project initialized' 'bootstrap' --project " & quoted form of projectName

	-- Restart mcp-proxy via launchd so it picks up the new workspace cwd.
	do shell script "launchctl kickstart -k gui/$(id -u)/com.pirito.engram-mcp-proxy 2>/dev/null || true"
	delay 2

	-- WORKSPACE_PATH overrides the docker-compose.yml default (./projects/miapp).
	-- The volume mount becomes: workspacePath → /workspace  (handled by compose).
	-- HERMES_PROJECT is passed as an env var so Engram detects the project correctly.
	set cmd to "export PATH=/opt/homebrew/bin:/usr/local/bin:$PATH && " & ¬
		"cd ~/projects/hermes-docker && " & ¬
		"HERMES_PROJECT=" & quoted form of projectName & ¬
		" WORKSPACE_PATH=" & quoted form of workspacePath & ¬
		" docker compose run --rm -p 9119:9119" & ¬
		" -e HERMES_PROJECT=" & quoted form of projectName & ¬
		" hermes hermes dashboard --tui --host 0.0.0.0 --insecure --no-open"

	tell application "Terminal"
		activate
		do script cmd
	end tell

	delay 10
	open location "http://localhost:9119"

on error errMsg number errNum
	if errNum is -128 then
		-- User cancelled the folder picker. Silent no-op.
		return
	else
		display dialog "HermesAgent failed: " & errMsg buttons {"OK"} default button "OK" with icon stop
	end if
end try
