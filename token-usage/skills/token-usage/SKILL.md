---
name: token-usage
description: 统计和显示Claude Code的Token使用情况。使用/token-usage查看统计。
argument-hint: "[--week|--month|--all]"
---

# Token用量统计

统计Claude Code的Token使用情况，支持按天、周、月查看。

## 使用方法

```bash
/token-usage           # 显示今日统计
/token-usage --week    # 显示本周统计
/token-usage --month   # 显示本月统计
/token-usage --all     # 显示所有历史统计
```

## 统计维度

- **API调用次数**: API请求的总次数
- **输入Token (Input)**: 用户输入和上下文的Token数量
- **输出Token (Output)**: AI响应的Token数量
- **总计 (Total)**: 输入和输出的总和

## 数据来源

从 `~/.claude/projects/` 目录下的会话日志文件中读取真实使用数据。

## 示例输出

```
  ==========================================================
  |                 Token Usage Statistics                 |
  +==========================================================+
  |  Period: Today                                          |
  +==========================================================+
  |  API Calls:                 125                         |
  |  Input Tokens:        125,430                           |
  |  Output Tokens:        45,678                           |
  |  Total Tokens:        171,108                           |
  +==========================================================+
```

## 执行脚本

```bash
/c/Users/admin/miniconda3/envs/dsbot_env/python.exe "$PLUGIN_DIR/scripts/token_usage.py" $ARGUMENTS
```