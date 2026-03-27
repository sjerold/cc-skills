# Token Usage Plugin

Claude Code 的 Token 用量统计插件。

## 功能

- 统计 API 调用次数
- 统计输入/输出 Token 数量
- 支持按天、周、月查看
- 命令行美观输出

## 安装

将插件目录放置到 `~/.claude/plugins/token-usage/`

## 使用

```bash
/token-usage           # 显示今日统计
/token-usage --week    # 显示本周统计
/token-usage --month   # 显示本月统计
/token-usage --all     # 显示所有历史统计
```

## 示例输出

```
  ==========================================================
  |                 Token Usage Statistics                 |
  +==========================================================+
  |  Period: Today                                          |
  +==========================================================+
  |  API Calls:                 655                         |
  |  Input Tokens:        44,718,301                        |
  |  Output Tokens:          102,064                        |
  |  Total Tokens:        44,820,365                        |
  +==========================================================+
```

## 依赖

- Python 3.6+
- 无外部依赖（使用 Python 标准库）

## 数据来源

从 `~/.claude/projects/` 目录下的 JSONL 会话日志文件读取真实使用数据。

## License

MIT