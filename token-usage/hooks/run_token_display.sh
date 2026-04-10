#!/bin/bash
# Stop hook - log token stats
# NOTE: Update paths for your installation

PYTHON_PATH="C:/Users/admin/miniconda3/envs/dsbot_env/python.exe"
SCRIPT_PATH="C:/Users/admin/.claude/plugins/token-usage/scripts/token_usage.py"
LOG_FILE="C:/Users/admin/.claude/token-stats.log"

stats=$("$PYTHON_PATH" "$SCRIPT_PATH" --hook)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] $stats" >> "$LOG_FILE"