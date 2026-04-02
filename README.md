# Claude Code Skills 合集

为 Claude Code 提供的实用 Skill 插件集合。

## Skill 列表

### 网页文章抓取 (web-article-fetcher) v1.0.0

从指定网页发现文章链接并批量抓取正文内容，保存为Markdown格式。

**核心功能**：
- 自动发现网页中的文章链接
- 智能过滤导航、广告、分页等非文章链接
- 支持静态和动态页面（Playwright渲染）
- 增量更新，自动跳过已抓取文章
- 按网站分子目录保存Markdown文件
- 支持网站别名（如"移动支付网"）

```bash
/web-article-fetcher https://www.mpaypass.com.cn/
抓取网页内容 移动支付网 -n 50
```

### Token用量统计 (token-usage) v1.0.0

统计和显示 Claude Code 的 Token 使用情况，支持按天、周、月查看。

**核心功能**：
- API 调用次数统计
- 输入/输出 Token 统计
- 支持按天、周、月、全部历史查看
- 美观的命令行输出

```bash
/token-usage           # 显示今日统计
/token-usage --week    # 显示本周统计
/token-usage --month   # 显示本月统计
/token-usage --all     # 显示所有历史统计
```

### 百度搜索 (baidu-search) v2.0.0

中文网络搜索增强工具，支持大规模搜索、智能筛选、内容抓取和自动总结。

**核心功能**：
- 默认搜索 150 条结果
- 智能筛选前 35% 高质量网页
- Playwright 动态渲染抓取
- Session 管理，文件独立保存
- 自动生成 Markdown 报告和总结

```bash
/baidu-search 关键词
/baidu-search 苏州银行 -n 100 -t 40
```

### 文件搜索 (file-searcher) v1.1.0

在本地文件中搜索关键词，支持 Word/PDF/Markdown 等多种格式。

```bash
/file-searcher 关键词
/file-searcher 外包 --path C:\Documents --ext docx,pdf
```

### 公文写作 (gongwen-writer) v1.2.1

创建符合党政机关公文格式规范的 Word 文档，包括通知、报告、请示等公文类型。

```bash
/gongwen-writer 写一份关于xxx的通知
```

### 衔风搜索 (xianfeng-search) v1.1.0

飞书云文档智能搜索工具，支持私有化部署版本。

**核心功能**：
- 递归目录扫描，生成JSON文档树
- 智能缓存，增量更新
- 文档内容抓取为Markdown
- 保持目录结构
- 支持表格文档抓取

```bash
# 扫描目录
衔风搜索 扫描 https://your-feishu.com/drive/folder/xxx

# 缓存文档（扫描+抓取）
衔风搜索 缓存 https://your-feishu.com/drive/folder/xxx

# 搜索文档
衔风搜索 搜索 关键词
```

## 安装方法

### 步骤 1：添加 Marketplace

```
/marketplace add https://github.com/sjerold/cc-skills.git
```

### 步骤 2：安装插件

```
/marketplace
```

### 步骤 3：安装依赖环境

```
/baidu-setup
/file-setup
/gongwen-setup
```

注意：
- web-article-fetcher 使用与 baidu-search 相同的依赖环境，无需额外安装
- xianfeng-search 需要额外安装 Playwright 浏览器：`playwright install chromium`

## 依赖环境

所有插件推荐使用 Miniconda + dsbot_env 虚拟环境：

```bash
# 创建虚拟环境
conda create -n dsbot_env python=3.10 -y
conda activate dsbot_env

# 安装依赖
pip install -r baidu-search/requirements.txt
pip install -r file-searcher/requirements.txt
pip install -r gongwen-writer/requirements-minimal.txt
```

**注意**: token-usage 插件无需额外依赖，使用 Python 标准库即可运行。

## 更新插件

```
/marketplace
```

找到已安装的插件，点击更新。

## 更新日志

### xianfeng-search v1.1.0 (2026-04-02)
- 首次发布
- 递归目录扫描，生成JSON文档树
- 智能缓存机制，增量更新
- 文档内容抓取为Markdown
- 保持目录结构
- 支持表格文档
- 修复 folder_path 传播问题
- 修复文档重定向导致的 ERR_ABORTED 错误

### web-article-fetcher v1.0.0 (2026-03-31)
- 首次发布
- 自动发现网页文章链接
- 智能过滤非文章链接
- 支持Playwright动态页面渲染
- 增量更新，避免重复抓取
- 按网站分子目录保存Markdown
- 支持网站别名（移动支付网、36氪等）

### token-usage v1.0.0 (2026-03-27)
- 首次发布
- 支持 API 调用次数统计
- 支持按天/周/月/全部历史查看 Token 用量
- 无外部依赖，使用 Python 标准库

### baidu-search v2.0.0 (2026-03-27)
- 添加 Session ID 管理，每次搜索单独保存
- 默认搜索 150 条结果
- 智能筛选前 35% 自动抓取
- Playwright 动态渲染
- Markdown 格式保存
- 自动生成搜索总结

### file-searcher v1.1.0 (2026-03-26)
- 支持 Word/PDF/Markdown 多格式搜索
- 添加依赖环境配置说明

### gongwen-writer v1.2.1 (2026-03-26)
- 所有阿拉伯数字使用 Times New Roman 字体

## License

MIT