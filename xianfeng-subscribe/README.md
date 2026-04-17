# 衔风订阅

飞书消息推送工具，支持Webhook管理、卡片发送、搜索结果推送。

## 功能特性

- **Webhook管理** - 注册、测试、删除webhook地址
- **卡片发送** - 发送飞书标准卡片消息
- **通知卡片** - 发送通知类消息
- **搜索结果** - 与衔风搜索联动，推送搜索结果卡片
- **折叠面板** - 支持卡片内容折叠显示（飞书 V7.9+）

## 安装

无需额外安装，仅依赖 `requests`（已安装）。

## 使用方法

### CLI 命令

```bash
# Webhook管理
python subscribe_cli.py 注册webhook --name <名称> --url <URL>
python subscribe_cli.py 列表webhooks
python subscribe_cli.py 测试webhook --id <ID>
python subscribe_cli.py 删除webhook --id <ID>
python subscribe_cli.py 设置默认 --id <ID>

# 消息发送
python subscribe_cli.py 发送文本 <内容> [--webhook <ID>]
python subscribe_cli.py 发送卡片 --template notification --title <标题> --content <内容>
python subscribe_cli.py 发送搜索 <关键词> [--webhook <ID>]
```

## 获取Webhook地址

1. 在飞书群聊中，点击群设置 → 群机器人 → 添加机器人
2. 选择「自定义机器人」
3. 复制生成的Webhook地址

## 架构

```
xianfeng-subscribe/
├── .claude-plugin/
│   └── plugin.json          # 插件配置
├── skills/
│   └── xianfeng-subscribe/
│       └── SKILL.md         # Skill定义
├── scripts/
│   ├── subscribe_cli.py     # CLI入口
│   ├── operations.py        # 核心操作
│   ├── webhook_manager.py   # Webhook管理
│   ├── card_builder.py      # 卡片构建器
│   ├── card_sender.py       # 发送器
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py        # 配置
│   └── cards/
│       ├── __init__.py
│       ├── notification_card.py
│       └── search_result_card.py
├── config/
│   └── webhooks.json        # Webhook配置
└── README.md
```

## 更新日志

### v1.1.0

- 新增折叠面板 (collapsible_panel) 支持
- CardBuilder 新增 `add_collapsible_panel()` 和 `add_collapsible_div()` 方法
- notification_card 新增 `collapsible` 参数和 `build_collapsible_card()` 函数
- 新增测试脚本 `test_collapsible.py`

### v1.0.0

- 初始版本
- 支持Webhook管理
- 支持通知卡片发送
- 支持搜索结果推送

## 依赖

- Python 3.8+
- requests

## License

MIT