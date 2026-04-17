---
name: xianfeng-subscribe
description: |
  衔风订阅：飞书消息推送。当用户要求"推送到飞书"、"发送飞书卡片"、"注册webhook"、
  "飞书通知"、"发送通知到群"时触发。
argument-hint: 发送卡片 --title <标题> --content <内容>
---

# 衔风订阅

飞书消息推送工具，通过Webhook机器人向群聊发送卡片消息。

## 功能点

| 功能 | 说明 | 命令 |
|------|------|------|
| **注册** | 注册Webhook地址 | `注册webhook --name <名称> --url <URL>` |
| **测试** | 测试Webhook连接 | `测试webhook --id <ID>` |
| **列表** | 查看已注册Webhook | `列表webhooks` |
| **发送文本** | 发送简单文本 | `发送文本 <内容>` |
| **发送卡片** | 发送通知卡片 | `发送卡片 --title <标题> --content <内容>` |
| **发送搜索** | 搜索并推送结果 | `发送搜索 <关键词>` |

## 快速开始

```bash
# 1. 注册Webhook（从飞书群获取webhook地址）
cmd //c "call conda activate dsbot_env && python $PLUGIN_DIR/scripts/subscribe_cli.py 注册webhook --name '产品群' --url https://open.feishu.cn/open-apis/bot/v2/hook/xxx"

# 2. 测试连接
cmd //c "call conda activate dsbot_env && python $PLUGIN_DIR/scripts/subscribe_cli.py 测试webhook --id wh_xxx"

# 3. 发送通知卡片
cmd //c "call conda activate dsbot_env && python $PLUGIN_DIR/scripts/subscribe_cli.py 发送卡片 --title '文档更新' --content '新文档已发布'"
```

## 获取Webhook地址

1. 在飞书群聊中，点击群设置（右上角）
2. 选择「群机器人」→「添加机器人」
3. 选择「自定义机器人」，输入名称
4. 复制生成的Webhook地址

## 卡片模板

### 通知卡片
发送简单通知，包含标题、内容、可选链接按钮。

### 搜索结果卡片
推送衔风搜索结果，显示匹配文档列表。

## 示例用法

**推送到飞书群**：
```
推送到飞书：文档已更新，请查看
```

**发送飞书卡片**：
```
发送飞书卡片，标题是"系统告警"，内容是"服务响应时间超过阈值"
```

**推送搜索结果**：
```
把搜索"产品需求"的结果推送到飞书
```