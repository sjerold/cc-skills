# Common 插件

公共模块，提供统一的Chrome浏览器管理和网页抓取功能，供其他插件引用。

## 功能

### chrome_manager.py

统一的Chrome调试模式连接和启动管理。

**核心逻辑**：
1. 所有插件共用同一个调试端口（9222）
2. 先检测是否已有调试Chrome运行，有则直接连接
3. 用户Chrome运行中 → 复制配置启动，共享session/cookie
4. 无Chrome运行 → 使用用户配置启动

**使用方式**：
```python
from chrome_manager import get_browser, get_page, close_browser

browser = get_browser()  # 获取或启动Chrome
page = get_page(browser)  # 在现有浏览器开新tab
# ... 操作页面 ...
close_browser(browser, keep_running=True)  # 断开连接，保持Chrome运行
```

### web_fetcher.py

统一的网页内容抓取。

**使用方式**：
```python
from web_fetcher import fetch_url, fetch_urls

result = fetch_url('https://example.com')
results = fetch_urls(['url1', 'url2'], save_dir='./output')
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