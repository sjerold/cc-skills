# Token Usage Plugin

Claude Code Token 用量统计插件 v1.4.4

## 功能

- 本地统计：今日/历史
- 排行榜同步：GitHub 仓库
- Stop Hook：自动记录日志 + 自动同步

## 安装

插件启用后自动生效。

**可选**: 如果 Python 路径不同，修改 `hooks/run_token_display.sh`：

```bash
PYTHON_PATH=~/miniconda3/envs/你的环境/python.exe
```

## 使用

```bash
/token-usage                 # 今日统计
/token-usage --history 7     # 最近7天历史
/token-usage --sync          # 同步到排行榜
/token-usage --board         # 总排行榜
/token-usage --board --today # 今日排行
/token-usage --board --month # 本月排行
/token-usage --name "名字"    # 设置名称
```

### 过去7天每日排行榜

```bash
python ~/.claude/plugins/token-usage/scripts/daily_board.py
```

显示过去7天每天的用户排行榜，按日期分组展示。

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