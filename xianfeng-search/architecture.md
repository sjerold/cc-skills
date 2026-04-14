# 衔风 - 架构设计文档

## 1. 设计概述

### 1.1 系统背景

**目标系统**: 飞书云文档私有化部署版本（衔风云文档）
- 访问方式: 网页浏览器
- 登录要求: 需要用户手动登录
- 文档类型: 在线文档

### 1.2 设计思路

采用 Playwright 驱动 Chrome 浏览器，模拟用户操作飞书网页：

1. **登录处理层**: 打开浏览器，等待用户完成登录
2. **目录导航层**: 遍历飞书知识库/文件夹目录结构
3. **内容抓取层**: 打开文档页面，提取文档内容
4. **缓存管理层**: 缓存目录结构，加速后续搜索

### 1.3 技术选型

| 技术/框架 | 用途 | 选型理由 |
|-----------|------|----------|
| Python 3.10+ | 主语言 | 与百度搜索插件保持一致 |
| Playwright | 浏览器自动化 | 复用百度搜索配置，支持SPA页面 |
| Chrome CDP | 浏览器控制 | 复用Chrome配置复制方案，保持登录状态 |
| JSON | 缓存格式 | 轻量级，易于读写和调试 |

## 2. 模块设计

### 2.1 飞书导航模块 (feishu_navigator.py)

- **职责**: 处理登录、导航到知识库、处理飞书特定的UI交互
- **接口**:
  ```python
  class FeishuNavigator:
      def __init__(self, domain: str, headless: bool = True)
      def open_and_wait_login(self, timeout: int = 300) -> bool
      def navigate_to_drive(self) -> bool
      def get_current_page_type(self) -> str  # 'drive', 'doc', 'wiki', etc.
      def close(self)
  ```
- **依赖**: Playwright, Chrome配置复制逻辑

### 2.2 目录扫描模块 (directory_scanner.py)

- **职责**: 遍历飞书知识库/文件夹，获取文档列表
- **接口**:
  ```python
  def scan_drive_structure(navigator: FeishuNavigator) -> dict
  def expand_folder(folder_element) -> list
  def get_document_info(doc_element) -> dict
  def scroll_to_load_all(container_element) -> None
  ```
- **依赖**: FeishuNavigator

### 2.3 缓存管理模块 (cache_manager.py)

- **职责**: 管理目录结构缓存的读写、验证、更新
- **接口**:
  ```python
  def load_cache(domain: str) -> dict
  def save_cache(domain: str, data: dict) -> bool
  def is_cache_valid(domain: str, max_age_hours: int = 24) -> bool
  def clear_cache(domain: str = None) -> bool
  ```
- **依赖**: 无

### 2.4 内容抓取模块 (content_fetcher.py)

- **职责**: 打开文档页面，提取文档内容，保存为MD
- **接口**:
  ```python
  def fetch_document_content(navigator: FeishuNavigator, doc_url: str) -> dict
  def extract_text_from_editor(page) -> str
  def save_as_markdown(content: dict, save_path: str) -> str
  def fetch_batch(navigator: FeishuNavigator, docs: list, save_dir: str) -> list
  ```
- **依赖**: FeishuNavigator

### 2.5 主搜索模块 (xianfeng_search.py)

- **职责**: 协调各模块，提供命令行接口
- **接口**: 命令行参数解析和主流程控制
- **依赖**: 以上所有模块

## 3. 数据流

```
┌─────────────────────────────────────────────────────────────────────┐
│                         用户输入关键词                               │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    FeishuNavigator 初始化                            │
│                    - 复制Chrome配置                                  │
│                    - 启动Chrome调试端口                              │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    打开飞书网页，等待登录                             │
│                    open_and_wait_login()                            │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    cache_manager.is_cache_valid()                   │
│                    检查缓存是否存在且有效                            │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
              ┌─────────────────┴─────────────────┐
              │                                   │
              ▼                                   ▼
    ┌─────────────────┐               ┌─────────────────┐
    │  缓存有效        │               │  缓存无效/不存在  │
    │  加载缓存数据    │               │  扫描目录结构    │
    └────────┬────────┘               └─────────┬────────┘
             │                                  │
             └────────────────┬─────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    文档名匹配 (本地操作)                             │
│                    从缓存中筛选匹配关键词的文档                       │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    依次抓取匹配的文档内容                            │
│                    fetch_document_content()                         │
│                    - 打开文档页面                                    │
│                    - 等待内容加载                                    │
│                    - 提取文档正文                                    │
│                    - 保存为MD文件                                    │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    整合结果，输出JSON                                │
└─────────────────────────────────────────────────────────────────────┘
```

## 4. 飞书页面结构分析

### 4.1 登录页面
- 可能需要扫码登录或账号密码登录
- 登录成功后URL会变化

### 4.2 知识库/云文档页面
- 左侧: 目录树（文件夹层级）
- 右侧: 文档列表或文档内容

### 4.3 文档页面
- URL格式: `https://domain/docx/xxx` 或 `https://domain/wiki/xxx`
- 内容区域: 通常在 `.editor`, `.doc-content`, `[contenteditable]` 等元素中
- 需要等待JS渲染完成

## 5. 缓存数据结构

```json
{
  "version": "1.0",
  "domain": "https://your-feishu.example.com",
  "scan_time": "2026-03-27T10:30:00",
  "total_docs": 500,
  "total_folders": 50,
  "structure": [
    {
      "type": "folder",
      "name": "产品文档",
      "id": "folder_xxx",
      "children": [
        {
          "type": "doc",
          "name": "需求文档 v1.0",
          "id": "doc_xxx",
          "url": "https://your-feishu.example.com/docx/xxx",
          "path": "产品文档/需求文档 v1.0"
        }
      ]
    }
  ],
  "flat_list": [
    {
      "type": "doc",
      "name": "需求文档 v1.0",
      "id": "doc_xxx",
      "url": "https://your-feishu.example.com/docx/xxx",
      "path": "产品文档/需求文档 v1.0"
    }
  ]
}
```

## 6. 文件清单

### 需要创建的文件

| 文件路径 | 用途 |
|----------|------|
| `scripts/xianfeng_search.py` | 主搜索脚本，命令行入口 |
| `scripts/feishu_navigator.py` | 飞书导航模块（登录、导航） |
| `scripts/directory_scanner.py` | 目录扫描模块 |
| `scripts/cache_manager.py` | 缓存管理模块 |
| `scripts/content_fetcher.py` | 内容抓取模块 |
| `scripts/config.py` | 配置管理 |
| `.claude-plugin/plugin.json` | 插件配置 |
| `skills/xianfeng-search/SKILL.md` | 技能说明文档 |
| `requirements.txt` | Python依赖 |
| `cache/.gitkeep` | 缓存目录占位 |

### 复用的代码（百度搜索插件）

| 复用内容 | 来源 |
|----------|------|
| Chrome配置复制逻辑 | `baidu_search.py: copy_chrome_profile()` |
| Chrome启动逻辑 | `baidu_search.py: start_chrome()` |
| Playwright连接逻辑 | `web_fetcher.py: fetch_with_chrome()` |

## 7. 实现步骤

### Step 1: 基础结构
1. 创建插件目录结构
2. 编写 `plugin.json` 和 `SKILL.md`
3. 编写 `requirements.txt`
4. 编写 `config.py` 配置文件

### Step 2: 飞书导航模块
1. 实现 Chrome 启动（复用百度搜索逻辑）
2. 实现 `open_and_wait_login()` 登录等待
3. 实现登录状态检测
4. 实现导航到知识库/云文档

### Step 3: 目录扫描模块
1. 实现展开文件夹操作
2. 实现滚动加载更多
3. 实现文档信息提取
4. 实现递归遍历整个目录结构

### Step 4: 缓存管理模块
1. 实现缓存读写
2. 实现缓存有效性检查
3. 实现缓存清理

### Step 5: 内容抓取模块
1. 实现打开文档页面
2. 实现等待内容加载
3. 实现文档内容提取（飞书编辑器）
4. 实现保存为MD文件

### Step 6: 主搜索脚本
1. 实现命令行参数解析
2. 实现主流程协调
3. 实现结果输出格式化

## 8. 风险与注意事项

### 8.1 技术风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 飞书UI变化 | 高 | 使用语义化选择器，添加多种备选方案 |
| 登录方式多样 | 中 | 支持等待用户手动登录，不自动处理登录 |
| 大型目录加载慢 | 中 | 实现增量加载检测，优化遍历策略 |
| 文档内容动态渲染 | 中 | 等待编辑器加载完成，重试机制 |
| Chrome进程残留 | 低 | 实现进程清理机制 |

### 8.2 注意事项

1. **Chrome端口**: 使用独立端口(9225)，避免与百度搜索冲突
2. **登录超时**: 默认5分钟，用户可根据需要调整
3. **隐私保护**: 不保存登录凭据，使用复制的Chrome配置
4. **内容提取**: 飞书文档可能包含表格、图片、代码块等，需要处理
5. **请求频率**: 避免过快操作，防止触发风控

## 9. 测试建议

### 9.1 单元测试

- [ ] 缓存读写测试
- [ ] 文档名匹配测试
- [ ] MD文件生成测试

### 9.2 集成测试

- [ ] 登录流程测试
- [ ] 目录遍历测试
- [ ] 文档内容抓取测试
- [ ] 完整搜索流程测试

### 9.3 手动测试场景

- [ ] 首次使用（无缓存）
- [ ] 缓存命中场景
- [ ] 登录过期重新登录
- [ ] 大型知识库（500+文档）

## 10. 配置项

```python
# config.py 默认配置

# 飞书域名（需要用户配置）
DEFAULT_DOMAIN = None  # 或从环境变量读取

# Chrome配置
CHROME_DEBUG_PORT = 9225
CHROME_USER_DATA_DIR = os.path.join(os.environ['LOCALAPPDATA'], 'Google', 'Chrome', 'User Data')  # Windows
TEMP_CHROME_DIR = os.path.join(os.environ['TEMP'], 'chrome-xianfeng-profile')

# 缓存配置
CACHE_DIR = os.path.expanduser("~/.claude/plugins/xianfeng-search/cache")
CACHE_MAX_AGE_HOURS = 24

# 超时配置
LOGIN_WAIT_TIMEOUT = 300  # 5分钟
PAGE_LOAD_TIMEOUT = 30
CONTENT_WAIT_TIMEOUT = 10

# 搜索配置
DEFAULT_RESULT_LIMIT = 50

# 输出配置
DEFAULT_OUTPUT_DIR = os.path.expanduser("~/Downloads/xianfeng_search")
```

## 11. 命令行接口

```
usage: xianfeng_search.py [-h] [--domain DOMAIN] [-r] [--scan-only]
                          [--cache-status] [--clear-cache] [-n N]
                          [--show-browser] [--json] [-o OUTPUT]
                          [keyword]

衔风 - 飞书云文档搜索工具

positional arguments:
  keyword               搜索关键词

optional arguments:
  -h, --help            显示帮助信息
  --domain DOMAIN       飞书域名 (如: https://your-feishu.example.com)
  -r, --refresh         强制刷新缓存
  --scan-only           仅扫描目录，不搜索
  --cache-status        显示缓存状态
  --clear-cache         清理缓存
  -n N, --limit N       限制结果数量 (默认: 50)
  --show-browser        显示浏览器窗口
  --json                JSON格式输出
  -o OUTPUT, --output OUTPUT
                        输出目录 (默认: ~/Downloads/xianfeng_search)
```

## 12. 后续扩展

### Phase 2 功能
- [ ] 全文搜索（需要先下载所有文档内容）
- [ ] 文档导出（支持导出为PDF/Word）
- [ ] 定时同步（定期更新缓存）

### Phase 3 功能
- [ ] 多知识库支持
- [ ] 协作文档实时监控
- [ ] 文档变更通知