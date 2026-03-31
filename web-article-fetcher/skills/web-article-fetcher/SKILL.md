---
name: web-article-fetcher
description: |
  网页文章抓取：从指定URL发现文章链接并批量抓取正文内容。
  当用户要求"抓取网站文章"、"采集网页内容"、"批量抓取链接"、"抓取网页内容"时触发。
  支持网站别名：移动支付网、mpaypass。
argument-hint: <URL或网站名> [选项]
---

# 网页文章抓取

一个完整的网页文章抓取解决方案，支持链接发现、内容抓取、Markdown保存和增量更新。

## 核心功能

| 功能 | 说明 |
|-----|------|
| 链接发现 | 从网页中发现文章链接，智能过滤非文章链接 |
| 内容抓取 | 使用Playwright渲染动态页面，提取正文 |
| MD保存 | 按规范命名保存为Markdown文件 |
| 增量更新 | 基于URL哈希跳过已抓取文章 |

## 快速开始

```bash
# 一键抓取（自动发现链接并抓取文章）
cmd //c "call conda activate dsbot_env && python $PLUGIN_DIR/scripts/fetcher.py https://www.mpaypass.com.cn/"

# 指定抓取数量
cmd //c "call conda activate dsbot_env && python $PLUGIN_DIR/scripts/fetcher.py https://www.mpaypass.com.cn/ -n 30"
```

## 命令参数

```bash
python fetcher.py <URL> [选项]

参数:
  <URL>              源页面URL（首页或栏目页）
  -n, --limit        最大抓取数量 (默认20)
  -o, --output       保存目录 (默认 ~/Downloads/web_article_fetcher)
  --full             全量抓取（忽略增量状态）
  --show-browser     显示浏览器窗口（用于处理验证码）
  --close            关闭Chrome进程
  --json             输出JSON格式
```

## 使用示例

```bash
# 默认抓取：发现链接并抓取20篇文章
python fetcher.py https://www.mpaypass.com.cn/

# 抓取50篇文章
python fetcher.py https://www.mpaypass.com.cn/ -n 50

# 全量重新抓取（忽略已抓取状态）
python fetcher.py https://www.mpaypass.com.cn/ --full

# 指定保存目录
python fetcher.py https://www.mpaypass.com.cn/ -o ./my_articles

# 显示浏览器（处理验证码）
python fetcher.py https://www.mpaypass.com.cn/ --show-browser
```

## 输出文件结构

每次抓取会在保存目录下生成：

```
web_article_fetcher/
├── mpaypass_数字人民币试点扩展_20260330_143052.md  # 抓取的文章
├── mpaypass_支付行业发展趋势_20260330_143053.md
├── ...
├── .fetched_urls.json                              # 增量状态文件
└── 抓取报告_20260330_143052.md                      # 抓取报告
```

### 文件说明

- **文章文件**: 命名规则 `{来源}_{标题}_{时间戳}.md`
- **状态文件**: `.fetched_urls.json`，记录已抓取URL，用于增量更新
- **抓取报告**: 包含统计信息、成功/失败列表

## 文章文件格式

```markdown
# 数字人民币试点扩展

- **来源**: 移动支付网
- **URL**: https://www.mpaypass.com.cn/news/123
- **抓取时间**: 2026-03-30 14:30:52
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
      |
      v
+-----------------+
|   链接发现      |
| 发现文章链接    |
| 过滤非文章链接  |
+-----------------+
      |
      v
+-----------------+
|   增量过滤      |
| URL哈希检查     |
| 跳过已抓取      |
+-----------------+
      |
      v
+-----------------+
|   内容抓取      |
| Playwright渲染  |
| 正文提取        |
+-----------------+
      |
      v
+-----------------+
|   MD保存        |
| 规范命名        |
| 元信息嵌入      |
+-----------------+
      |
      v
+-----------------+
|   抓取报告      |
| 统计成功/失败   |
| 更新状态文件    |
+-----------------+
```

## 环境配置

### 使用 Miniconda + dsbot_env（推荐）

```bash
# 1. 创建虚拟环境
conda create -n dsbot_env python=3.10 -y
conda activate dsbot_env

# 2. 安装依赖
pip install -r requirements.txt

# 3. 安装 Playwright 浏览器
playwright install chromium
```

### 运行命令

```bash
# 使用 dsbot_env 环境
cmd //c "call conda activate dsbot_env && python $PLUGIN_DIR/scripts/fetcher.py https://www.mpaypass.com.cn/"
```

## 反爬处理

遇到验证码时的处理策略：

1. 检测到反爬会自动提示
2. 使用 `--show-browser` 显示浏览器窗口
3. 手动完成验证码后继续抓取
4. 使用 `--close` 关闭浏览器

## 站点适配

预设支持的站点：

| 站点 | 链接特征 | 正文选择器 |
|------|---------|-----------|
| mpaypass.com.cn | /news/, /article/ | .news-content, .article-body |
| 其他站点 | 自动识别 | 智能选择器 |