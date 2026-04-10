# Token Usage Plugin

Claude Code Token 用量统计插件 v1.4.0

## 功能

- 本地统计：今日/历史
- 排行榜同步：GitHub 仓库
- Stop Hook：自动记录日志 + 自动同步

## 安装

修改 `hooks/run_token_display.sh` 中的路径：

```bash
PYTHON_PATH="你的Python路径"
SCRIPT_PATH="你的插件路径/scripts/token_usage.py"
LOG_FILE="你的日志路径/token-stats.log"
```

## 使用

```bash
/token-usage              # 今日统计
/token-usage --history 7  # 最近7天
/token-usage --sync       # 手动同步到排行榜
/token-usage --board      # 显示排行榜
/token-usage --name "名字" # 设置名称
```

## 自动同步

Stop Hook 会在每次对话结束时：
1. 记录统计到 `~/.claude/token-stats.log`
2. 后台静默同步到排行榜（无需手动 `--sync`）

## 数据存储

配置独立存储在 `~/.claude/token-usage/`：

```
~/.claude/token-usage/
├── config.json   # 用户配置
├── .token        # GitHub Token
└── .cache/       # Git 缓存
```

**安全性**：Token 文件权限 600，仅用户可读。

## Token 获取

1. https://github.com/settings/tokens/new
2. 选择 "Fine-grained token"
3. 仓库: sjerold/token-board
4. 权限: Contents (Read and Write)

首次 `--sync` 时会提示输入 Token。

## License

MIT