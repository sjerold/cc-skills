#!/usr/bin/env python3
"""
Token Usage Statistics for Claude Code

Reads JSONL log files from ~/.claude/projects/ and aggregates token usage data.
"""

import json
import os
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple


def get_claude_projects_dir() -> Path:
    """Get the Claude projects directory path."""
    home = Path.home()
    return home / ".claude" / "projects"


def find_jsonl_files() -> List[Path]:
    """Find all JSONL log files in the Claude projects directory."""
    projects_dir = get_claude_projects_dir()
    if not projects_dir.exists():
        return []

    jsonl_files = []
    for project_dir in projects_dir.iterdir():
        if project_dir.is_dir():
            for file in project_dir.glob("*.jsonl"):
                jsonl_files.append(file)
    return jsonl_files


def parse_usage_data(file_path: Path) -> List[Dict]:
    """
    Parse usage data from a JSONL file.

    Returns a list of dicts with keys: timestamp, input_tokens, output_tokens
    """
    usage_records = []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)

                    # Only process assistant messages with usage data
                    if data.get('type') == 'assistant':
                        message = data.get('message', {})
                        usage = message.get('usage', {})

                        if usage:
                            timestamp_str = data.get('timestamp', '')
                            if timestamp_str:
                                # Parse ISO format timestamp
                                timestamp = datetime.fromisoformat(
                                    timestamp_str.replace('Z', '+00:00')
                                )

                                usage_records.append({
                                    'timestamp': timestamp,
                                    'input_tokens': usage.get('input_tokens', 0),
                                    'output_tokens': usage.get('output_tokens', 0)
                                })
                except (json.JSONDecodeError, ValueError):
                    # Skip malformed lines
                    continue
    except Exception as e:
        print(f"Warning: Error reading {file_path}: {e}")

    return usage_records


def aggregate_by_period(records: List[Dict], period: str) -> Dict[str, Dict]:
    """
    Aggregate usage data by time period.

    Args:
        records: List of usage records
        period: 'day', 'week', 'month', or 'all'

    Returns:
        Dict mapping period key to aggregated data
    """
    aggregated = defaultdict(lambda: {'input': 0, 'output': 0, 'calls': 0})

    for record in records:
        ts = record['timestamp']

        if period == 'day':
            key = ts.strftime('%Y-%m-%d')
        elif period == 'week':
            # Get the Monday of the week
            monday = ts - timedelta(days=ts.weekday())
            key = f"Week of {monday.strftime('%Y-%m-%d')}"
        elif period == 'month':
            key = ts.strftime('%Y-%m')
        else:  # all
            key = 'all'

        aggregated[key]['input'] += record['input_tokens']
        aggregated[key]['output'] += record['output_tokens']
        aggregated[key]['calls'] += 1

    return dict(aggregated)


def get_period_filter(period: str) -> Tuple[datetime, datetime]:
    """
    Get start and end datetime for a period filter.

    Returns:
        Tuple of (start_datetime, end_datetime)
    """
    now = datetime.now()

    if period == 'day':
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = now
    elif period == 'week':
        # Start from Monday of current week
        start = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        end = now
    elif period == 'month':
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = now
    else:  # all
        start = datetime.min
        end = now

    return start, end


def format_number(num: int) -> str:
    """Format a number with thousand separators."""
    return f"{num:,}"


def print_report(data: Dict[str, Dict], period: str, filter_current: bool = True):
    """
    Print a formatted usage report.

    Args:
        data: Aggregated usage data
        period: The time period type
        filter_current: Whether to show only current period
    """
    if not data:
        print("\n  No usage data found for the specified period.\n")
        return

    # Get current period key if filtering
    if filter_current and period != 'all':
        now = datetime.now()
        if period == 'day':
            current_key = now.strftime('%Y-%m-%d')
        elif period == 'week':
            monday = now - timedelta(days=now.weekday())
            current_key = f"Week of {monday.strftime('%Y-%m-%d')}"
        else:  # month
            current_key = now.strftime('%Y-%m')

        # Filter to show only current period
        data = {k: v for k, v in data.items() if k == current_key}

    # Sort by key (date)
    sorted_keys = sorted(data.keys(), reverse=True)

    # Calculate totals
    total_input = sum(d['input'] for d in data.values())
    total_output = sum(d['output'] for d in data.values())
    total_calls = sum(d['calls'] for d in data.values())
    total_all = total_input + total_output

    # Print header
    period_names = {
        'day': 'Today',
        'week': 'This Week',
        'month': 'This Month',
        'all': 'All Time'
    }

    period_display = period_names.get(period, period.title())

    print()
    print("  " + "=" * 58)
    print(f"  |{'Token Usage Statistics':^56}|")
    print("  +" + "=" * 58 + "+")
    print(f"  |  Period: {period_display:<47}|")
    print("  +" + "=" * 58 + "+")

    # Print each period's data
    for key in sorted_keys:
        d = data[key]
        total = d['input'] + d['output']
        # Show date key for all periods when multiple entries
        if len(sorted_keys) > 1 or period == 'all':
            print(f"  |  Date: {key:<49}|")
        print(f"  |  API Calls:      {format_number(d['calls']):>15}                      |")
        print(f"  |  Input Tokens:   {format_number(d['input']):>15}                      |")
        print(f"  |  Output Tokens:  {format_number(d['output']):>15}                      |")
        print(f"  |  Total Tokens:   {format_number(total):>15}                      |")
        if len(sorted_keys) > 1:
            print("  +" + "-" * 58 + "+")

    # Print totals if multiple periods
    if len(sorted_keys) > 1:
        print("  +" + "=" * 58 + "+")
        print(f"  |  {'TOTALS':<20}                                    |")
        print(f"  |  API Calls:      {format_number(total_calls):>15}                      |")
        print(f"  |  Input Tokens:   {format_number(total_input):>15}                      |")
        print(f"  |  Output Tokens:  {format_number(total_output):>15}                      |")
        print(f"  |  Total Tokens:   {format_number(total_all):>15}                      |")

    print("  +" + "=" * 58 + "+")
    print()


def main():
    parser = argparse.ArgumentParser(
        description='Token Usage Statistics for Claude Code'
    )
    parser.add_argument(
        '--week',
        action='store_true',
        help='Show statistics for the current week'
    )
    parser.add_argument(
        '--month',
        action='store_true',
        help='Show statistics for the current month'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Show all historical statistics'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=None,
        help='Show statistics for the last N days (e.g., --days 14 for last 2 weeks)'
    )

    args = parser.parse_args()

    # Determine period
    if args.all:
        period = 'all'
    elif args.week:
        period = 'week'
    elif args.month:
        period = 'month'
    elif args.days:
        period = 'day'
    else:
        period = 'day'

    # Find and parse all JSONL files
    jsonl_files = find_jsonl_files()

    if not jsonl_files:
        print("\n  No Claude Code session logs found.")
        print(f"  Expected location: {get_claude_projects_dir()}\n")
        return

    # Collect all usage records
    all_records = []
    for jsonl_file in jsonl_files:
        records = parse_usage_data(jsonl_file)
        all_records.extend(records)

    if not all_records:
        print("\n  No usage data found in session logs.\n")
        return

    # Filter by date range if --days specified
    if args.days:
        from datetime import timezone
        now = datetime.now(timezone.utc)
        start_date = now - timedelta(days=args.days)
        all_records = [r for r in all_records if r['timestamp'] >= start_date]

    # Aggregate data
    aggregated = aggregate_by_period(all_records, period)

    # Print report
    filter_current = period != 'all' and args.days is None
    print_report(aggregated, period, filter_current)


if __name__ == '__main__':
    main()