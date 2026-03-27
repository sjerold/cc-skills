# Claude Code Skills 合集

为 Claude Code 提供的实用 Skill 插件集合。

## Skill 列表

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