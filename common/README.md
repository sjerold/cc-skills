# Common 插件

公共模块，提供统一的Chrome浏览器管理、网页抓取、内容解析、Markdown生成功能，供其他插件引用。

## 模块结构

```
scripts/
├── chrome_manager.py    # Chrome浏览器管理（异步API）
├── web_fetcher.py       # 网页抓取（异步API）
├── content_parser.py    # 网页内容解析（纯函数）
└── markdown_writer.py   # Markdown文件生成（纯函数）
```

## 功能

### chrome_manager.py

统一的Chrome调试模式连接和启动管理（异步版本）。

**使用方式**：
```python
from chrome_manager import get_browser_async, get_page_async, close_browser_async

playwright, browser = await get_browser_async()
page = await get_page_async(browser, url='https://example.com')
# ... 操作页面 ...
await close_browser_async(browser, playwright, keep_running=True)
```

### web_fetcher.py

统一的网页内容抓取（异步版本）。

**使用方式**：
```python
from web_fetcher import fetch_url_async, fetch_urls_async

result = await fetch_url_async('https://example.com')
results = await fetch_urls_async(['url1', 'url2'], save_dir='./output')
```

### content_parser.py

网页内容解析（纯函数，方便测试和扩展）。

**使用方式**：
```python
from content_parser import extract_content, check_anti_crawl, is_redirect_url

content = extract_content(html, url)
is_blocked = check_anti_crawl(html, url)
is_redirect = is_redirect_url(url)
```

**可用函数**：
- `extract_content(html, url)` - 提取正文内容
- `check_anti_crawl(html, url)` - 检测反爬/验证码
- `is_redirect_url(url)` - 检测是否跳转链接
- `extract_links(html, base_url)` - 提取所有链接
- `extract_images(html, base_url)` - 提取所有图片
- `clean_text(text)` - 清理文本

### markdown_writer.py

Markdown文件生成（纯函数）。

**使用方式**：
```python
from markdown_writer import save_result_to_markdown, save_search_report, save_summary

filepath = save_result_to_markdown(result, save_dir)
report_path = save_search_report(query, results, fetched, save_dir, session_id)
summary_path = save_summary(query, results, md_contents, save_dir, session_id)
```

## 依赖插件

以下插件依赖本模块：

| 插件 | 版本 | 说明 |
|------|------|------|
| baidu-search | 2.2.0 | 百度搜索增强版 |
| xianfeng-search | 1.3.0 | 飞书云文档搜索 |
| web-article-fetcher | 1.2.0 | 网页文章批量抓取 |

## 安装依赖

```bash
pip install playwright beautifulsoup4 requests
playwright install chromium
```

## 变更日志

### 2.0.0 (2026-04-03)
- **全面异步重构**：chrome_manager 和 web_fetcher 全部使用 async_playwright
- **简化代码结构**：移除 threading workaround，直接使用 asyncio.run()
- **EPIPE修复**：CDP连接不调用 browser.close()/playwright.stop()，避免断开外部Chrome时出错
- **页面追踪**：添加 pages_opened 列表确保所有页面正确关闭
- **等待策略优化**：使用 `wait_until="load"` 替代 `domcontentloaded`，等待跳转完成
- **内容校验**：检查内容长度，过短时标记失败
- **API变更**：
  - `get_browser()` → `get_browser_async()` 返回 `(playwright, browser)` 元组
  - `get_page()` → `get_page_async()`
  - `close_browser()` → `close_browser_async()`
  - `fetch_url()` → `fetch_url_async()`
  - `fetch_urls()` → `fetch_urls_async()`
  - 保留同步包装函数供命令行使用

### 1.5.0 (2026-04-03)
- **异步抓取重构**：使用 asyncio.create_task 正确管理并发任务
- **EPIPE修复**：CDP连接不调用 browser.close()/playwright.stop()，避免断开外部Chrome时出错
- **页面追踪**：添加 pages_opened 列表确保所有页面正确关闭
- **等待策略优化**：使用 `wait_until="load"` 替代 `domcontentloaded`，等待跳转完成
- **错误输出**：增加详细错误日志，便于排查失败原因
- **内容校验**：检查内容长度，过短时标记失败

### 1.4.0 (2026-04-02)
- **页面关闭修复**：确保每次抓取后关闭页面，避免内存泄漏
- **线程池并行抓取**：静态抓取支持多线程并行（默认3线程）
- **搜索数量优化**：百度搜索最小数量20，避免结果不足

### 1.3.0 (2026-04-02)
- **最小化窗口启动**：Chrome 默认最小化启动，不抢焦点，不影响其他工作
- 添加 `--start-minimized` 参数
- 使用 Windows STARTUPINFO 控制窗口显示

### 1.2.0 (2026-04-02)
- **默认后台运行**：Chrome 默认 headless 模式启动（无窗口）
- 修复 get_browser() 的 headless 默认参数

### 1.1.0 (2026-04-02)
- **修复编码问题**：静态抓取时显式检测和设置正确编码，解决中文乱码问题
- **修复Playwright复用问题**：使用全局Playwright实例，避免asyncio循环冲突
- **动态内容加载**：添加滚动功能，加载更多动态内容
- 支持保存为Markdown文件

### 1.0.0 (2026-04-02)
- 初始版本
- 统一Chrome管理（端口9222）
- 统一网页抓取
- 支持共享session/cookie