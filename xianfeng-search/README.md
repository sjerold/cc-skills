# 衔风

飞书云文档智能搜索工具，支持私有化部署版本。

## 功能特性

- **递归扫描** - 自动遍历子文件夹，最大深度3层，获取完整文档树
- **智能缓存** - 单独缓存子文件夹时更新父缓存，避免重复文件
- **增量更新** - 比对 edit_time，跳过未修改的文档
- **全文搜索** - 集成 file-searcher，支持在 Markdown 内容中搜索关键词
- **文档抓取** - 抓取文档内容并保存为 Markdown，表格格式正确
- **目录结构** - MD文件保持原有目录层级
- **名称-ID格式** - 缓存文件使用"名称-ID"格式，易于识别

## 安装

```bash
# 安装依赖
pip install playwright beautifulsoup4 python-docx PyMuPDF

# 安装 Playwright 浏览器
playwright install chromium
```

## 使用方法

### CLI 命令

```bash
# 缓存文档 - 递归扫描+抓取MD
衔风 缓存 https://your-feishu.com/drive/folder/xxx

# 搜索文档 - 名称+内容全文搜索
衔风 搜索 关键词

# 查看缓存状态
衔风 --status

# 关闭Chrome
衔风 --close
```

### Skill 调用

```
衔风 缓存 <URL>      # 缓存文件夹或单个文档
衔风 搜索 <关键词>    # 搜索（名称匹配 + 内容全文搜索）
```

## 架构

```
xianfeng-search/
├── .claude-plugin/
│   └── plugin.json          # 插件配置
├── skills/
│   └── xianfeng-search/
│       └── SKILL.md         # Skill定义
├── scripts/
│   ├── xianfeng_search_cli.py   # CLI入口
│   ├── operations.py        # 核心操作（搜索、缓存）
│   ├── directory_scanner.py # 目录扫描（支持递归）
│   ├── cache_manager.py     # 缓存管理（智能合并）
│   ├── feishu_navigator.py  # 浏览器导航
│   └── fetch/
│       ├── async_fetcher.py # 异步并行抓取
│       ├── markdown_writer.py # Markdown保存
│       └── table_parser.py  # 表格解析
└── cache/                   # 缓存目录
```

## 缓存结构

```
衔风云文档缓存/
├── 目录结构/
│   └── 文件夹名-ID.json     # 目录结构缓存（含子文件夹）
├── 文档内容/
│   ├── 文件夹名/
│   │   └── 文档名-ID.md     # 抓取的Markdown内容
│   └── 文件夹名_子文件夹/
│       └── 文档名-ID.md
```

## 搜索功能

### 名称匹配
- 精确匹配文档名称
- 路径匹配
- 模糊匹配

### 内容搜索
- 调用 file-searcher 插件
- 在已抓取的 Markdown 文件中搜索
- 显示匹配上下文片段
- 关键词用【】标注

## 更新日志

### v1.6.0 (2026-04-15)

- **新增** 递归扫描子文件夹（最大深度3层）
- **新增** 智能缓存：单独缓存子文件夹时更新父缓存children，避免重复文件
- **新增** 全文搜索：集成 file-searcher 插件，支持在 Markdown 内容中搜索
- **改进** 搜索结果显示：分名称匹配和内容匹配两部分

### v1.5.0 (2026-04-14)

- **修复** 表格内容重复问题，通过检测 `parent_id` 跳过表格子块
- **改进** 品牌更名：衔风搜索 → 衔风
- **改进** 清理调试日志代码

### v1.1.0 (2026-04-02)

- **修复** folder_path 传播问题，子文件夹现在正确继承完整路径
- **修复** 文档重定向导致的 `net::ERR_ABORTED` 错误
- **修复** 内容提取失败问题，添加多种备用选择器
- **改进** 导航稳定性，使用 `domcontentloaded` 替代 `load`
- **改进** 缓存文件使用"名称-ID"格式
- **改进** MD文件保持目录结构

### v1.0.0

- 初始版本
- 支持目录扫描、缓存、搜索

## 依赖

- Python 3.8+
- Playwright
- BeautifulSoup4
- file-searcher 插件（用于全文搜索）

## License

MIT