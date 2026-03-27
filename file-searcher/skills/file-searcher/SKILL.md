---
name: file-searcher
description: |
  在本地文件中搜索关键词内容。支持 Word (.docx)、PDF、Markdown (.md)、文本文件等格式。
  当用户要求"搜索文件"、"在文档中查找"、"搜索Word/PDF内容"时触发此技能。
argument-hint: <关键词> [--path <目录>] [--ext <扩展名>]
---

# 文件内容搜索

在本地文件中搜索指定关键词，支持多种文档格式。

## 支持的文件格式

- **Word 文档**: .docx
- **PDF 文档**: .pdf
- **Markdown**: .md
- **文本文件**: .txt, .json, .csv, .xml, .log, .yaml, .yml
- **代码文件**: .py, .js, .java, .ts, .go, .rs 等

## 执行搜索

运行 Python 脚本执行搜索：

```bash
/c/Users/admin/miniconda3/envs/dsbot_env/python.exe "$PLUGIN_DIR/scripts/file_searcher.py" "$ARGUMENTS"
```

### 参数说明

- `<关键词>`: 要搜索的关键词（必填）
- `--path, -p <目录>`: 搜索路径，默认为用户的下载目录 `C:\Users\admin\Downloads`
- `--ext, -e <扩展名>`: 限制文件扩展名，如 `--ext docx,md,pdf`
- `--max, -m <数量>`: 每个文件最多显示的匹配数，默认 3
- `--json, -j`: 输出 JSON 格式

### 示例

```bash
# 搜索"外包"关键词
外包

# 指定目录搜索
外包 --path C:\Users\admin\Documents

# 只搜索 Word 和 PDF 文档
外包 --ext docx,pdf

# 显示更多匹配内容
外包 --max 5
```

## 输出格式

默认输出易读格式，显示：
- 搜索关键词和路径
- 匹配文件列表
- 每个文件的匹配内容片段（关键词用【】标注）
- 匹配次数

示例：
```
============================================================
搜索关键词: 【外包】
搜索路径: C:\Users\admin\Downloads
共搜索 522 个文件，找到 25 个匹配文件
============================================================

[1] 苏州银行报告.docx
    路径: C:\Users\admin\Downloads\苏州银行报告.docx
    匹配次数: 2
    匹配内容:
      (1) ...坚持底线思维，统筹数据安全、网络安全、【外包】安全等...
      (2) ...科技【外包】风险管理...
```

## 注意事项

- PDF 文本提取可能不完整，取决于 PDF 格式
- 扫描版 PDF（图片）无法搜索文字
- 大文件可能需要较长处理时间

## 环境配置

### 方式一：使用 Miniconda + dsbot_env（推荐）

```bash
# 1. 安装 Miniconda（如未安装）
# Windows: 下载 https://docs.conda.io/en/latest/miniconda.html

# 2. 创建虚拟环境
conda create -n dsbot_env python=3.10 -y
conda activate dsbot_env

# 3. 安装依赖
pip install -r requirements.txt
```

### 方式二：直接安装

```bash
pip install python-docx PyPDF2
```

### 依赖包版本

```
python-docx>=0.8.11
PyPDF2>=3.0.0
```

### 运行命令

```bash
# 使用 dsbot_env 环境
/c/Users/admin/miniconda3/envs/dsbot_env/python.exe "$PLUGIN_DIR/scripts/file_searcher.py" "关键词"
```