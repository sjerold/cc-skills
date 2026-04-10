---
name: token-usage
description: 统计Claude Code的Token使用情况，支持排行榜同步。使用/token-usage查看统计，/token-usage --sync同步排行榜。
argument-hint: "[--history N|--sync|--board|--name <名称>|--token <token>]"
---

# Token用量统计

统计Claude Code的Token使用情况，支持按天查看历史，以及排行榜同步。

## 安装配置

插件启用后自动生效。

**可选**: 如果 Python 路径不同，修改 `hooks/run_token_display.sh`：

```bash
PYTHON_PATH=~/miniconda3/envs/你的环境/python.exe
```

**首次使用排行榜**: 运行 `--sync` 时会提示输入 GitHub Token

## 使用方法

### 本地统计

```bash
/token-usage              # 今日统计
/token-usage --history 7  # 最近7天历史
```

### 排行榜功能

```bash
/token-usage --sync          # 上传数据（首次会提示输入Token）
/token-usage --board         # 总排行榜
/token-usage --board --month # 本月排行
/token-usage --board --today # 今日排行
/token-usage --name "名字"   # 设置显示名称
```

## 数据存储

**配置目录**: `~/.claude/token-usage/`（独立于插件，更安全）

```
~/.claude/token-usage/
├── config.json   # 用户配置
├── .token        # GitHub Token（权限600）
└── .cache/       # Git 缓存
```

## Stop Hook

每次对话结束自动记录到 `~/.claude/token-stats.log`