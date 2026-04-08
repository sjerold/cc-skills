---
name: web-article-fetcher
description: |
  网页文章抓取：从指定URL发现文章链接并批量抓取正文内容。
  当用户要求"抓取网站文章"、"采集网页内容"、"批量抓取链接"、"抓取网页内容"时触发。
  支持网站别名：移动支付网、mpaypass。
argument-hint: <URL或网站名> [选项]
---

# 网页文章抓取

一个完整的网页文章抓取解决方案，支持链接发现、异步并行抓取、Markdown保存和增量更新。

## 核心功能

| 功能 | 说明 |
|-----|------|
| 链接发现 | 从网页中发现文章链接，智能过滤非文章链接 |
| 异步抓取 | 使用 common/web_fetcher 异步并行抓取内容 |
| MD保存 | 使用 common/markdown_writer 保存文章 |
| 增量更新 | 基于URL哈希跳过已抓取文章 |

## 快速开始

```bash
# 一键抓取（自动发现链接并抓取文章）
cmd //c "call conda activate dsbot_env && python $PLUGIN_DIR/scripts/fetcher.py https://www.mpaypass.com.cn/"

# 指定抓取数量和并发数
cmd //c "call conda activate dsbot_env && python $PLUGIN_DIR/scripts/fetcher.py https://www.mpaypass.com.cn/ -n 30 -w 4"
```

## 命令参数

```bash
python fetcher.py <URL> [选项]

参数:
  <URL>              源页面URL（首页或栏目页），支持多个URL直接抓取
  -n, --limit        最大抓取数量 (默认20)
  -o, --output       保存目录 (默认 ~/Downloads/web_article_fetcher)
  -w, --workers      并发数 (默认4)
  --full             全量抓取（忽略增量状态）
  --json             输出JSON格式
```

## 使用示例

```bash
# 默认抓取：发现链接并抓取20篇文章
python fetcher.py https://www.mpaypass.com.cn/

# 抓取50篇文章，并发数6
python fetcher.py https://www.mpaypass.com.cn/ -n 50 -w 6

# 全量重新抓取
python fetcher.py https://www.mpaypass.com.cn/ --full

# 指定保存目录
python fetcher.py https://www.mpaypass.com.cn/ -o ./my_articles

# JSON输出
python fetcher.py https://www.mpaypass.com.cn/ --json

# 直接抓取多个URL（跳过链接发现）
python fetcher.py https://example.com/a.html https://example.com/b.html
```

## 输出文件结构

每次抓取会在保存目录下生成：

```
web_article_fetcher/
├── mpaypass/                      # 站点子目录
│   ├── 数字人民币试点扩展_xxx.md  # 抓取的文章
│   └── 支付行业发展趋势_xxx.md
├── .fetched_urls.json             # 增量状态文件
└── 抓取报告_20260408_xxx.md       # 抓取报告
```

### 文件说明

- **文章文件**: 保存在站点子目录下，命名规则 `{标题}_{时间戳}_{URL哈希}.md`
- **状态文件**: `.fetched_urls.json`，记录已抓取URL，用于增量更新
- **抓取报告**: 包含统计信息、成功/失败列表

## 文章文件格式

```markdown
# 数字人民币试点扩展

- **URL**: https://www.mpaypass.com.cn/news/123
- **原始URL**: https://www.mpaypass.com.cn/news/123
- **抓取时间**: 2026-04-08 14:30:52
- **抓取方式**: playwright_async
- **内容长度**: 2500 字符

---

## 正文内容

{正文内容}
```

## 增量更新机制

系统自动记录已抓取URL，后续运行会跳过已抓取的文章：

- 状态文件: `.fetched_urls.json`
- URL哈希: MD5前8位
- 全量重抓: 使用 `--full` 参数

## 工作流程

```
用户输入URL
      ↓
+-----------------+
|   链接发现      |
| 发现文章链接    |
| 过滤非文章链接  |
+-----------------+
      ↓
+-----------------+
|   增量过滤      |
| URL哈希检查     |
| 跳过已抓取      |
+-----------------+
      ↓
+-----------------+
| 异步并行抓取    |
| 使用 web_fetcher|
| 并发处理URL     |
+-----------------+
      ↓
+-----------------+
|   MD保存        |
| 站点子目录      |
| 元信息嵌入      |
+-----------------+
      ↓
+-----------------+
|   抓取报告      |
| 统计成功/失败   |
| 更新状态文件    |
+-----------------+
```

## 依赖模块

本插件依赖 `common` 模块的组件：

| 组件 | 用途 |
|------|------|
| chrome_manager | 获取源页面原始HTML |
| web_fetcher | 异步并行抓取网页内容 |
| content_parser | 内容解析、反爬检测 |
| markdown_writer | 文章保存为Markdown |

## 站点适配

预设支持的站点：

| 站点 | 链接特征 | 别名 |
|------|---------|------|
| mpaypass.com.cn | /news/, /article/ | 移动支付网 |
| 36kr.com | /p/ | 36氪 |

## 反爬处理

- 自动检测反爬/验证码页面
- 使用 Chrome CDP 连接复用登录状态
- 标记失败文章便于重试