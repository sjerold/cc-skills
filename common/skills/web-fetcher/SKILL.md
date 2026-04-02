---
name: web-fetcher
description: 网页内容抓取工具。抓取指定URL的正文内容，支持动态页面渲染，自动提取标题和正文。
trigger:
  - 抓取网页
  - 打开网页
  - 获取网页内容
  - 提取正文
  - fetch url
  - web content
---

# 网页内容抓取

抓取指定URL的内容，自动提取标题和正文。

## 使用方式

用户可以说：
- "抓取 https://example.com 的内容"
- "打开这个网页并提取正文：[URL]"
- "获取这个URL的内容"

## 执行脚本

```bash
cmd //c "call conda activate dsbot_env && python C:\Users\admin\.claude\plugins\common\scripts\web_fetcher.py {URL}"
```

## 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| URL | 要抓取的URL | 必填 |
| -o, --output | 保存目录 | 不保存 |

## 输出格式

返回 JSON 格式的抓取结果：
- success: 是否成功
- title: 页面标题
- content: 正文内容
- url: 最终URL（可能经过重定向）
- length: 内容长度
- fetch_type: 抓取方式（playwright/static）

## 示例

```bash
# 抓取单个URL
python web_fetcher.py https://www.baidu.com

# 抓取并保存为Markdown
python web_fetcher.py https://example.com -o ./output
```

## 注意事项

1. 会自动启动Chrome浏览器（调试模式）
2. 支持动态渲染的页面
3. 自动检测反爬/验证码
4. 内容过长会自动截断（15000字符）