#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Token Usage Plugin for Claude Code
统计 Token 用量，支持排行榜同步

配置目录: ~/.claude/token-usage/ (与插件代码分离)
"""

import json
import socket
import uuid
import subprocess
import os
import sys
import io
import getpass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ============================================================================
# 配置路径（独立于插件目录，提高安全性）
# ============================================================================
CONFIG_DIR = Path.home() / ".claude" / "token-usage"
CONFIG_FILE = CONFIG_DIR / "config.json"
TOKEN_FILE = CONFIG_DIR / ".token"  # 隐藏文件
CACHE_DIR = CONFIG_DIR / ".cache"

REPO_URL = "https://github.com/sjerold/token-board.git"
REPO_BRANCH = "main"


def ensure_config_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# 用户配置
# ============================================================================
def load_config() -> Dict:
    ensure_config_dir()
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
        except:
            pass
    return {}


def save_config(cfg: Dict):
    ensure_config_dir()
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding='utf-8')


def get_user_id() -> str:
    cfg = load_config()
    if 'user_id' not in cfg:
        cfg['user_id'] = uuid.uuid4().hex[:12]
        save_config(cfg)
    return cfg['user_id']


def get_user_name() -> str:
    return load_config().get('user_name', socket.gethostname())


def set_user_name(name: str):
    cfg = load_config()
    cfg['user_name'] = name
    save_config(cfg)
    print(f"✅ 用户名称: {name}")


# ============================================================================
# Token 管理（安全存储）
# ============================================================================
def get_token() -> str:
    """获取 Token"""
    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text(encoding='utf-8').strip()
    return ""


def set_token(token: str):
    """保存 Token（设置权限）"""
    ensure_config_dir()
    TOKEN_FILE.write_text(token.strip(), encoding='utf-8')
    try:
        os.chmod(TOKEN_FILE, 0o600)  # 仅用户可读写
    except:
        pass
    print("✅ Token 已保存")


def prompt_token():
    """交互式输入 Token"""
    print("\n🔑 需要配置 GitHub Token 才能使用排行榜功能")
    print("   获取方式: https://github.com/settings/tokens/new")
    print("   权限: Contents (Read and Write)")
    print()
    token = getpass.getpass("请输入 GitHub Token: ").strip()
    if token:
        set_token(token)
        return token
    return None


def ensure_token() -> str:
    """确保有 Token"""
    token = get_token()
    if not token:
        token = prompt_token()
    return token


# ============================================================================
# 数据统计
# ============================================================================
def get_projects_dir() -> Path:
    return Path.home() / ".claude" / "projects"


def get_daily_stats() -> Dict:
    """获取按日期分组的统计"""
    projects_dir = get_projects_dir()
    if not projects_dir.exists():
        return {'daily': {}, 'total': {'input_tokens': 0, 'output_tokens': 0, 'calls': 0, 'total_tokens': 0}}

    daily = {}
    total_input, total_output, total_calls = 0, 0, 0

    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue
        for jsonl_file in project_dir.glob("*.jsonl"):
            try:
                with open(jsonl_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            if data.get('type') == 'assistant':
                                usage = data.get('message', {}).get('usage', {})
                                ts = data.get('timestamp', '')
                                if usage and ts:
                                    try:
                                        t = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                                        date_key = t.strftime('%Y-%m-%d')
                                        inp = usage.get('input_tokens', 0)
                                        out = usage.get('output_tokens', 0)

                                        if date_key not in daily:
                                            daily[date_key] = {'input': 0, 'output': 0, 'calls': 0}
                                        daily[date_key]['input'] += inp
                                        daily[date_key]['output'] += out
                                        daily[date_key]['calls'] += 1

                                        total_input += inp
                                        total_output += out
                                        total_calls += 1
                                    except:
                                        pass
                        except json.JSONDecodeError:
                            pass
            except:
                pass

    return {
        'daily': daily,
        'total': {
            'input_tokens': total_input,
            'output_tokens': total_output,
            'calls': total_calls,
            'total_tokens': total_input + total_output
        }
    }


def fmt_tokens(n: int) -> str:
    if n >= 1000000:
        return f"{n/1000000:.1f}M"
    elif n >= 1000:
        return f"{n/1000:.0f}K"
    return str(n)


# ============================================================================
# 本地显示
# ============================================================================
def show_today():
    stats = get_daily_stats()
    today = datetime.now().strftime('%Y-%m-%d')
    d = stats['daily'].get(today, {'input': 0, 'output': 0, 'calls': 0})
    total = d['input'] + d['output']

    print()
    print("📊 今日统计")
    print("-" * 40)
    print(f"  输入: {fmt_tokens(d['input'])} tokens")
    print(f"  输出: {fmt_tokens(d['output'])} tokens")
    print(f"  总计: {fmt_tokens(total)} tokens ({d['calls']}次)")
    print()


def show_history(days: int = 7):
    stats = get_daily_stats()
    daily = stats['daily']
    sorted_days = sorted(daily.keys(), reverse=True)[:days]

    print()
    print(f"📊 最近 {days} 天统计")
    print("-" * 50)

    for date in sorted_days:
        d = daily[date]
        tokens = d['input'] + d['output']
        print(f"  {date}  {fmt_tokens(tokens):>8} tokens ({d['calls']}次)")

    print("-" * 50)
    t = stats['total']
    print(f"  总计      {fmt_tokens(t['total_tokens']):>8} tokens ({t['calls']}次)")
    print()


# ============================================================================
# Hook 输出
# ============================================================================
def hook_output():
    """Stop Hook: 输出到日志"""
    projects_dir = get_projects_dir()
    if not projects_dir.exists():
        return

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    s_inp, s_out, s_calls = 0, 0, 0  # 本次
    t_inp, t_out, t_calls = 0, 0, 0  # 今日

    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue
        for jsonl_file in project_dir.glob("*.jsonl"):
            try:
                with open(jsonl_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            if data.get('type') == 'assistant':
                                usage = data.get('message', {}).get('usage', {})
                                ts = data.get('timestamp', '')
                                if usage and ts:
                                    try:
                                        t = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                                        inp = usage.get('input_tokens', 0)
                                        out = usage.get('output_tokens', 0)

                                        if t >= cutoff:
                                            s_inp += inp
                                            s_out += out
                                            s_calls += 1
                                        if t.strftime('%Y-%m-%d') == today:
                                            t_inp += inp
                                            t_out += out
                                            t_calls += 1
                                    except:
                                        pass
                        except json.JSONDecodeError:
                            pass
            except:
                pass

    print(f"📊 本次: {fmt_tokens(s_inp+s_out)} tokens ({s_calls}次) │ 今日: {fmt_tokens(t_inp+t_out)} tokens ({t_calls}次)")


# ============================================================================
# Git 同步
# ============================================================================
def run_git(args: List[str], cwd: Path = None) -> Tuple[int, str, str]:
    cmd = ["git"] + args
    try:
        r = subprocess.run(cmd, cwd=cwd or CACHE_DIR, capture_output=True, text=True, timeout=60)
        return r.returncode, r.stdout, r.stderr
    except Exception as e:
        return -1, "", str(e)


def sync_up(quiet: bool = False):
    """上传数据"""
    token = ensure_token() if not quiet else get_token()
    if not token:
        return False

    token_url = REPO_URL.replace("https://", f"https://{token}@")
    user_id = get_user_id()
    user_name = get_user_name()

    stats = get_daily_stats()
    user_data = {
        "user_id": user_id,
        "user_name": user_name,
        "machine_name": socket.gethostname(),
        "total": stats['total'],
        "daily": stats['daily'],
        "updated_at": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    }

    # 克隆或更新仓库
    if not CACHE_DIR.exists():
        if not quiet:
            print("📥 克隆仓库...")
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        code, _, err = run_git(["clone", "-b", REPO_BRANCH, token_url, "."], CACHE_DIR)
        if code != 0:
            if not quiet:
                print(f"❌ 克隆失败: {err}")
            return False
    else:
        if not quiet:
            print("📥 更新仓库...")
        run_git(["remote", "set-url", "origin", token_url])
        run_git(["fetch", "origin"])
        code, _, _ = run_git(["rebase", f"origin/{REPO_BRANCH}"])
        if code != 0:
            run_git(["rebase", "--abort"])
            run_git(["reset", "--hard", f"origin/{REPO_BRANCH}"])

    # 合并历史数据
    data_file = CACHE_DIR / "data" / f"{user_id}.json"
    data_file.parent.mkdir(parents=True, exist_ok=True)

    if data_file.exists():
        try:
            existing = json.loads(data_file.read_text(encoding='utf-8'))
            for date, d in existing.get('daily', {}).items():
                if date not in user_data['daily']:
                    user_data['daily'][date] = d
            user_data['daily'] = dict(sorted(user_data['daily'].items()))
        except:
            pass

    data_file.write_text(json.dumps(user_data, ensure_ascii=False, indent=2), encoding='utf-8')

    # 提交推送
    run_git(["config", "user.email", "token-usage@local"])
    run_git(["config", "user.name", "token-usage"])
    run_git(["add", str(data_file)])
    run_git(["commit", "-m", f"Token usage {datetime.now():%Y-%m-%d}: {user_name}"])

    if not quiet:
        print("📤 推送数据...")
    code, _, err = run_git(["push", "origin", REPO_BRANCH])

    if code == 0:
        if not quiet:
            print(f"✅ 同步成功! {fmt_tokens(stats['total']['total_tokens'])} tokens ({stats['total']['calls']}次)")
        return True
    else:
        if not quiet:
            print(f"❌ 推送失败: {err}")
        return False


def sync_down() -> List[Dict]:
    """拉取所有用户数据"""
    token = get_token()
    if not token:
        return []

    token_url = REPO_URL.replace("https://", f"https://{token}@")

    if not CACHE_DIR.exists():
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        code, _, _ = run_git(["clone", "--depth", "1", "-b", REPO_BRANCH, token_url, "."], CACHE_DIR)
        if code != 0:
            return []
    else:
        run_git(["remote", "set-url", "origin", token_url])
        run_git(["fetch", "origin"])
        run_git(["reset", "--hard", f"origin/{REPO_BRANCH}"])

    data_dir = CACHE_DIR / "data"
    all_data = []
    if data_dir.exists():
        for f in data_dir.glob("*.json"):
            try:
                all_data.append(json.loads(f.read_text(encoding='utf-8')))
            except:
                pass
    return all_data


def show_board(period: str = None):
    """显示排行榜"""
    all_data = sync_down()
    if not all_data:
        print("\n⚠️ 暂无数据，请先 --sync\n")
        return

    user_id = get_user_id()
    board = []

    for data in all_data:
        if period:
            daily = data.get('daily', {})
            if period in daily:
                d = daily[period]
                board.append({
                    "user_id": data.get("user_id"),
                    "user_name": data.get("user_name", "匿名"),
                    "total_tokens": d['input'] + d['output'],
                    "total_calls": d['calls']
                })
            elif len(period) == 7:  # 月份
                mt, mc = 0, 0
                for date, d in daily.items():
                    if date.startswith(period):
                        mt += d['input'] + d['output']
                        mc += d['calls']
                if mt > 0:
                    board.append({
                        "user_id": data.get("user_id"),
                        "user_name": data.get("user_name", "匿名"),
                        "total_tokens": mt,
                        "total_calls": mc
                    })
        else:
            t = data.get('total', {})
            board.append({
                "user_id": data.get("user_id"),
                "user_name": data.get("user_name", "匿名"),
                "total_tokens": t.get('total_tokens', 0),
                "total_calls": t.get('calls', 0)
            })

    board.sort(key=lambda x: x["total_tokens"], reverse=True)
    for i, e in enumerate(board):
        e["rank"] = i + 1

    print()
    print(f"🏆 Token排行榜 ({period or '全部'})")

    my_rank = None
    for e in board[:10]:
        is_me = " ← 你" if e["user_id"] == user_id else ""
        if is_me:
            my_rank = e
        print(f"  #{e['rank']} {e['user_name']:<12} {fmt_tokens(e['total_tokens']):>8} tokens ({e['total_calls']}次){is_me}")

    if my_rank and my_rank["rank"] > 10:
        print(f"  ...")
        print(f"  #{my_rank['rank']} {my_rank['user_name']:<12} {fmt_tokens(my_rank['total_tokens']):>8} tokens ({my_rank['total_calls']}次) ← 你")

    print()


# ============================================================================
# 主入口
# ============================================================================
def main():
    import argparse

    p = argparse.ArgumentParser(description='Token Usage Statistics')
    p.add_argument('--history', type=int, metavar='N', help='最近N天历史')
    p.add_argument('--sync', action='store_true', help='上传数据')
    p.add_argument('--board', action='store_true', help='排行榜')
    p.add_argument('--today', action='store_true', help='今日排行/统计')
    p.add_argument('--month', action='store_true', help='本月排行')
    p.add_argument('--name', type=str, help='设置用户名')
    p.add_argument('--token', type=str, help='设置 Token')
    p.add_argument('--hook', action='store_true', help='Stop Hook')
    p.add_argument('--quiet', action='store_true', help='静默模式')

    args = p.parse_args()

    if args.token:
        set_token(args.token)
    elif args.name is not None:
        set_user_name(args.name)
    elif args.sync:
        sync_up(quiet=args.quiet)
    elif args.board:
        period = datetime.now().strftime('%Y-%m') if args.month else None
        period = datetime.now().strftime('%Y-%m-%d') if args.today else period
        show_board(period)
    elif args.history:
        show_history(args.history)
    elif args.hook:
        hook_output()
    elif args.today:
        show_today()
    else:
        show_today()


if __name__ == '__main__':
    main()