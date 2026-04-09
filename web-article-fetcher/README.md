# Web Article Fetcher

网页文章抓取插件 - Clean Code 版本

## 功能特性

- **链接发现**: 智能发现网页中的文章链接
- **异步抓取**: 并行抓取，高效快速
- **增量更新**: 自动跳过已抓取文章
- **Markdown保存**: 结构化保存，便于阅读
- **站点适配**: 预设常用站点配置

## 架构设计

Clean Code 原则，模块化设计：

```
scripts/
├── fetcher.py        # 主流程入口 (328行)
├── site_configs.py   # 站点配置 (60行)
└── link_discovery.py # 链接发现 (100行)
```

### 模块职责

| 模块 | 职责 |
|------|------|
| `fetcher.py` | 主流程编排、状态管理、文章保存 |
| `site_configs.py` | 站点别名、链接规则配置 |
| `link_discovery.py` | 从HTML中发现文章链接 |

## 快速开始

```bash
# 抓取网站文章（自动发现链接）
python scripts/fetcher.py https://www.mpaypass.com.cn/

# 指定数量和并发
python scripts/fetcher.py https://www.mpaypass.com.cn/ -n 50 -w 4

# 全量重新抓取
python scripts/fetcher.py https://www.mpaypass.com.cn/ --full

# 直接抓取多个URL
python scripts/fetcher.py <url1> <url2> <url3>
```

## 命令参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `<url>` | 源页面URL或网站别名 | 必填 |
| `-n, --limit` | 最大抓取数量 | 20 |
| `-w, --workers` | 并发数 | 4 |
| `-o, --output` | 保存目录 | `~/Downloads/web_article_fetcher` |
| `--full` | 全量抓取（忽略增量状态） | - |

## 输出结构

```
web_article_fetcher/
├── 移动支付网/                          # 站点子目录
│   ├── 202604_08100524_移动支付网_工行大模型落地.md
│   └── 202604_08113538_移动支付网_6大行科技投入.md
├── .fetched_urls.json                   # 增量状态
└── 抓取报告_20260408_143052.md           # 抓取报告
```

### 文件命名规则

```
{日期时间}_{站点名}_{标题}.md
```

示例: `202604_08100524_移动支付网_工行大模型体系落地500+AI应用场景.md`

## 依赖

依赖 `common` 模块：

- `chrome_manager`: 浏览器管理
- `web_fetcher`: 异步网页抓取
- `content_parser`: 内容解析
- `markdown_writer`: Markdown保存

## 扩展站点

编辑 `scripts/site_configs.py`:

```python
SITE_CONFIGS = {
    'example.com': {
        'name': '示例网站',
        'link_patterns': [r'/article/\d+\.html'],
        'exclude_patterns': [r'/tag/', r'/author/'],
    },
}
```

## 版本历史

### v2.2.0 (2026-04-09)

- 新增: 支持单线程模式 (`-w 1`)，降低并发压力
- 新增: 站点别名支持（移动支付网、mpaypass）
- 优化: 文件命名格式，时间戳前置便于排序
- 优化: 内容解析精度，移除更多噪音元素
- 修复: Windows下路径编码问题

### v2.1.0 (2026-04-08)

- Clean Code 重构，代码量减少 60%
- 模块化设计：拆分 site_configs.py、link_discovery.py
- 支持直接抓取多个URL
- 改进文件命名格式（时间戳在前）
- 优化内容解析（移除导航栏、噪音）

### v2.0.0

- 使用 common 模块组件
- 异步并行抓取
- 边抓边保存

## License

MIT