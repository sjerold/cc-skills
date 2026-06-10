---
name: docx-img2md
description: 将包含图片的docx文档转换为Markdown格式。当用户说"docx转md"、"docx图片转文字"、"转换docx"、"识别docx图片"时触发。
version: 2.5.2
---

# Docx图片转Markdown 技能

## ⚠️ 核心规则（必须严格遵守）

| 规则 | 说明 | 违反后果 |
|------|------|---------|
| **每次1张** | 单次调用只传递1张图片 | 会导致API失败 |
| **保持原始内容** | OCR结果保持原格式，只调整表格对齐 | 内容失真 |
| **使用PowerShell** | 所有脚本用PowerShell执行 | 中文路径失败 |

**绝对禁止**：
- ❌ 禁止OCR脚本单次传递多张图片。
- ❌ 禁止处理多次后才写入md，读取一次txt文件，写入一次md文件。
- ❌ 禁止修改txt文件内容（删减、重写、合并）
- ❌ 禁止使用Bash执行脚本
- ❌ 禁止一次性读取所有txt文件内容（会导致上下文累积超限）

---

## ⚠️ 上下文管理（防止 API Error）

**GLM-5 API 限制**：输入长度上限 **202,752 字节**（约 200KB）

**问题**：每次 Read 都会累积上下文，处理大量文件时可能触发 `API Error: 400 InternalError.Algo.InvalidParameter: Range of input length should be [1, 202752]`

**解决方案**：分批处理 + 用户确认继续

| 批次 | 图片数量 | 说明 |
|------|----------|------|
| 第1批 | 1-10张 | 处理完暂停，输出进度 |
| 第2批 | 11-20张 | 用户确认"继续"，清空部分上下文 |
| ... | ... | 循环直到完成 |

---

## 操作流程

### 步骤0：预处理（WPS云盘文件）

**⚠️ WPS云盘文件会被同步进程锁定，需要先复制到本地普通目录**

```powershell
# 检查文件是否在WPS云盘（路径包含WPSDrive）
# 如果是，先复制到Downloads或普通本地目录
Copy-Item "C:\Users\admin\WPSDrive\...\xxx.docx" -Destination "C:\Users\admin\Downloads\xxx.docx" -Force
```

### 步骤1：提取图片

```powershell
# 默认输出到docx同目录的文字版/<文档名>/pic/
cmd /c "call conda activate dsbot_env && python C:\Users\admin\.claude\plugins\docx-img2md\skills\docx-img2md\extract_images.py <docx路径>"

# 检查提取结果
Get-ChildItem "C:\Users\admin\Downloads\文字版\<文档名>\pic" | Select-Object Name, Count
```

### 步骤2：批量OCR（多线程并发）

**⚠️ 中文编码说明**：Windows PowerShell 显示 UTF-8 中文会乱码，必须写入临时文件再用 Read 工具读取

**输出结构**：OCR结果存放在 `txt/` 目录（与 `pic/` 平级），文件名与图片对应（如 `image_001.txt` 对应 `image_001.png`）

**执行流程**：
```powershell
# 1. 创建txt目录
New-Item -ItemType Directory -Path "C:\Users\admin\Downloads\文字版\<文档名>\txt" -Force

# 2. 并发执行OCR（3线程），每张图片生成对应txt文件
# 使用3个并发Agent，每个Agent处理一批图片
# Agent1处理 image_001~image_024
# Agent2处理 image_025~image_048  
# Agent3处理 image_049~image_072

# 单张图片OCR命令（在Agent中执行）：
$env:PYTHONIOENCODING = "utf-8"; & cmd /c "call conda activate dsbot_env && python C:\Users\admin\.claude\plugins\docx-img2md\skills\docx-img2md\external_ocr.py --images C:\Users\admin\Downloads\文字版\<文档名>\pic\image_XXX.png > C:\Users\admin\Downloads\文字版\<文档名>\txt\image_XXX.txt 2>&1"

# 3. 检查OCR完成情况
Get-ChildItem "C:\Users\admin\Downloads\文字版\<文档名>\txt" | Select-Object Name, Count

# 4. 读取OCR生成的txt内容，看是否有错误，如果有错误，需要重新OCR
```

### 步骤3：组装Markdown（分批处理，每批10张）

**⚠️ 重要**：分批处理避免上下文累积超限！

**执行流程**：
```powershell
# 1. 查看txt目录文件总数
$txtFiles = Get-ChildItem "C:\Users\admin\Downloads\文字版\<文档名>\txt" | Sort-Object Name
$totalCount = $txtFiles.Count
"共 $totalCount 个txt文件需要处理"

# 2. 分批处理（每批10张）
# 第1批：image_001 ~ image_010
# 处理完输出进度，暂停等待用户确认"继续"
# 用户确认后，上下文部分清空，继续下一批
```

**单张处理流程**（在每批内循环执行）：
```powershell
# 读取当前txt文件（只读1个！）
Read "C:\Users\admin\Downloads\文字版\<文档名>\txt\image_XXX.txt"

# 立即追加到md文件
# 路径：`文字版/<文档名>/<文档名>.md`
# **保持OCR原始内容**，只做以下调整：
  ## 表格列对齐（`|---|` 格式）
  ## 图片引用路径修正为相对路径 `pic/xxx.png`
  ## 跨页表格：后续页追加数据行，不重复表头
# `[纯文字]` → 直接追加OCR内容
# `[混合]` → 追加OCR内容 + `![image](pic/xxx.png)`
# `[纯图形]` → 只追加 `![image](pic/xxx.png)`
```

**每批完成后输出进度**：
```
进度：10/55 ✅（第1批完成，上下文约 XX KB）
已处理：image_001 ~ image_010
请回复"继续"处理下一批...
```

**上下文估算方法**：
- 每处理1张txt平均增加约 2-4KB上下文
- 已处理10张 → 上下文约 20-40KB（加上初始上下文）
- 上下文超过150KB时建议暂停
- 用户确认"继续"后，部分上下文清空，重置估算

**用户确认"继续"后**：
- 清空部分上下文（新对话轮次）
- 继续处理下一批：image_011 ~ image_020
- 循环直到所有txt处理完成

---

## 输出结构

```
文字版/<文档名>/
├── pic/
│   ├── image_001.png
│   └── ...
├── txt/
│   ├── image_001.txt
│   └── ...
└── <文档名>.md
```

---

## 常见问题

### Q1：Edit 匹配失败 "Found 2 matches"
**原因**：old_string 太短，在文件中出现多次
**解决**：使用更多上下文（包含表名、章节号等唯一标识）
```markdown

# 错误
old_string: "| runCtxId | String | Y |"
# 正确
old_string: "表90 envGetCallbackArg参数\n\n| 名称 | 类型 | 必填 | 描述 |\n| runCtxId | String | Y |"
```

### Q2：文件被修改后 Edit 失败
**现象**：`File content has changed since it was last read`
**解决**：先 Read 刷新缓存，再 Edit

### Q3：API Error: Range of input length should be [1, 202752]
**原因**：上下文累积超过 GLM-5 API 的 200KB 限制
**解决**：
1. 查看当前处理进度：检查 md 文件中最后处理的图片编号
2. 从下一张继续处理，回复"继续"让模型清空部分上下文
3. 每批只处理 10 张，避免再次超限

---

## 备注

- 环境变量：`$env:SP_TOKEN = "your-api-key"`