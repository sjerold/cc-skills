---
name: docx-img2md
description: 将包含图片的docx文档转换为Markdown格式。当用户说"docx转md"、"docx图片转文字"、"转换docx"、"识别docx图片"时触发。
version: 2.5.0
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

### 步骤3：组装Markdown（遍历txt目录，读取，写入md）

**按文件名顺序读取txt文件，追加到md**：

```powershell
# 1. 遍历txt目录，按文件名排序
$txtFiles = Get-ChildItem "C:\Users\admin\Downloads\文字版\<文档名>\txt" | Sort-Object Name

# 2. 逐个读取txt文件，追加到md.
foreach ($txt in $txtFiles) {
    # 用Read工具读取txt内容。每次读取1个txt文件， 不允许超过这个限制！！！
    Read $txt.FullName
    
    # 路径：`文字版/<文档名>/<文档名>.md`
    # **保持OCR原始内容**，只做以下调整：
      ## 表格列对齐（`|---|` 格式）
      ## 图片引用路径修正为相对路径 `pic/xxx.png`
      ## 跨页表格：后续页追加数据行，不重复表头
    # `[纯文字]` → 直接追加OCR内容
    # `[混合]` → 追加OCR内容 + `![image](pic/xxx.png)`
    # `[纯图形]` → 只追加 `![image](pic/xxx.png)`
    
    # 定期输出进度（每处理10张）
    # "进度良好（30/72，42%）"
}
```

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

---

## 备注

- 环境变量：`$env:SP_TOKEN = "your-api-key"`