# 衔风搜索 (Xianfeng Search)

飞书云文档智能搜索工具，支持私有化部署版本。

## 功能特性

- **目录扫描** - 递归遍历飞书文件夹，获取完整文档树
- **智能缓存** - 增量缓存机制，避免重复扫描
- **文档抓取** - 抓取文档内容并保存为 Markdown
- **目录结构** - MD文件保持原有目录层级
- **名称-ID格式** - 缓存文件使用"名称-ID"格式，易于识别

## 安装

```bash
# 安装依赖
pip install playwright beautifulsoup4

# 安装 Playwright 浏览器
playwright install chromium
```

## 使用方法

### CLI 命令

```bash
# 扫描目录 - 生成JSON文档树
python xianfeng_search.py 扫描 --url https://your-feishu.com/drive/folder/xxx

# 缓存文档 - 扫描+抓取MD
python xianfeng_search.py 缓存 --url https://your-feishu.com/drive/folder/xxx

# 搜索文档
python xianfeng_search.py 搜索 关键词

# 查看缓存状态
python xianfeng_search.py --status

# 关闭Chrome
python xianfeng_search.py --close
```

### 选项

| 选项 | 说明 |
|------|------|
| `--show-browser` | 显示浏览器窗口（默认后台运行） |
| `--login-timeout` | 登录等待超时时间（秒） |
| `--limit` | 搜索结果数量限制 |

## 架构

```
xianfeng-search/
├── .claude-plugin/
│   └── plugin.json          # 插件配置
├── skills/
│   └── xianfeng-search/
│       └── SKILL.md         # Skill定义
├── scripts/
│   ├── xianfeng_search.py   # CLI入口
│   ├── operations.py        # 核心操作
│   ├── directory_scanner.py # 目录扫描
│   ├── content_fetcher.py   # 内容抓取
│   ├── sheets_fetcher.py    # 表格抓取
│   ├── cache_manager.py     # 缓存管理
│   ├── feishu_navigator.py  # 浏览器导航
│   └── chrome_helper.py     # Chrome启动
└── cache/                   # 缓存目录
```

## 缓存结构

```
衔风云文档缓存/
├── 文件夹名-ID.json         # 目录结构缓存
├── 文档内容/
│   ├── My Space/
│   │   └── 文档名-ID.md
│   └── My Space_子文件夹/
│       └── 文档名-ID.md
```

## 更新日志

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

## License

MIT