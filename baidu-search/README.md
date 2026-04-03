# 百度搜索增强版 (baidu-search)

大规模搜索、智能分数筛选、内容抓取、自动总结。

## 功能特性

- **大规模搜索** - 支持获取多达 50+ 条搜索结果
- **智能筛选** - 基于域名和内容质量自动评分，筛选高价值结果
- **内容抓取** - 使用 Playwright 动态渲染，支持 JS 页面
- **自动总结** - 生成 Markdown 格式的搜索报告和总结
- **Session 管理** - 每次搜索独立目录，便于管理

## 使用方法

```bash
# 基本搜索
python baidu_search.py "搜索关键词"

# 指定结果数量
python baidu_search.py "搜索关键词" -n 10

# JSON 输出
python baidu_search.py "搜索关键词" --json
```

## 版本历史

### v2.4.0 (2026-04-03)
- 添加应用下载链接过滤（应用宝、Google Play、软件下载站等）
- 默认并发数改为 4，提升抓取效率
- 优化搜索结果质量筛选

### v2.3.0
- 改进跳转链接检测逻辑
- 使用 wait_for_selector 优化页面加载等待

### v2.2.0
- 全部改为 Playwright async API
- 分离 content_parser 和 markdown_writer 模块

## 依赖

- `common` 模块 >= 1.4.0
- Playwright
- BeautifulSoup4