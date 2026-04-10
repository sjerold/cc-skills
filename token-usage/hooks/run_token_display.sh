#!/bin/bash
# Stop hook - log token stats and auto sync
# NOTE: Update PYTHON_PATH for your environment

PLUGIN_ROOT=~/.claude/plugins/token-usage
PYTHON_PATH=~/miniconda3/envs/dsbot_env/python.exe
SCRIPT_PATH="$PLUGIN_ROOT/scripts/token_usage.py"
LOG_FILE=~/.claude/token-stats.log

# Log stats
stats=$("$PYTHON_PATH" "$SCRIPT_PATH" --hook 2>/dev/null)
if [ -n "$stats" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $stats" >> "$LOG_FILE"
fi

# Auto sync to leaderboard (silent, non-blocking)
"$PYTHON_PATH" "$SCRIPT_PATH" --sync --quiet 2>/dev/null &