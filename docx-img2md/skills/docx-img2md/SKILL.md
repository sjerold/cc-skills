---
name: docx-img2md
description: 将包含图片的docx文档转换为Markdown格式。当用户说"docx转md"、"docx图片转文字"、"转换docx"、"识别docx图片"时触发。
version: 3.0.0
---

# Docx图片转Markdown 技能

## 核心规则

| 规则 | 说明 |
|------|------|
| **OCR必须用Agent** | 步骤2批量OCR必须启动 3 个 Agent 并行；**禁止用 Bash 后台任务 / shell 脚本循环 / 任何非 Agent 方式替代**。Agent 的自动修复能力是 OCR 失败兜底的唯一保障 |
| **md组装也用Agent** | 步骤3组装md同样启动 3 个 Agent 并行，每个 Agent 负责约1/3的txt，输出独立 part 片段文件；最后主线程拼接 |
| **每次1张/每批10个** | OCR 单次传1张图（API限制）；md组装每批读 **10个txt** 写一次 |
| **Agent自修复** | OCR 每张图后必须检查结果；空txt/报错/非0退出码即失败，Agent 须自行重试该张直到成功，不得跳过、不得依赖事后补跑 |
| **保持原内容** | OCR结果不删减、不重写；结构化整理只做去页眉页脚/合并跨页续表/去重复序列图，文字忠于原文，OCR误识保留并标注不擅改 |
| **用PowerShell+UTF8 BOM** | 禁止Bash执行中文路径；.ps1 脚本必须存为 **UTF-8 with BOM**（PowerShell 5.1 无BOM按GBK解码中文乱码） |

**禁止**：修改txt文字内容、自行设置SP_TOKEN环境变量、用脚本/后台任务代替Agent跑OCR、用脚本做md内容智能处理（机械拼接part片段除外）

---

## 操作步骤

### 0. 预处理
**⚠️ 先拷贝到Downloads目录再执行**（WPS云盘等中文长路径必须先拷到本地）

中文路径禁止用 Bash 直接传参（会乱码）。用 PowerShell，且 .ps1 脚本文件必须存为 **UTF-8 with BOM**（PowerShell 5.1 默认按 GBK 解码无 BOM 的 ps1，中文变乱码）。生成带 BOM 的 ps1 可用 Python：`codecs.open(path,'wb').write(codecs.BOM_UTF8 + content.encode('utf-8'))`。

```powershell
Copy-Item "<docx原路径>" -Destination "C:\Users\admin\Downloads\<文档名>.docx" -Force
```

### 1. 提取图片
```powershell
cmd /c "call conda activate dsbot_env && python <extract_images.py路径> <docx路径> --output-dir <工作目录>"
```
默认输出到 `<工作目录>/pic/`，图片命名 `image_001.png` ~ `image_NNN.png`。

### 2. 批量OCR（必须用3个Agent并行，每个顺序处理约1/3图片）
**⚠️ 必须用 Agent 工具（subagent）并行，禁止用 Bash `run_in_background` / shell 循环 / 任何脚本替代。**
**⚠️ 必须等所有txt生成完毕，才能进入步骤3**

启动3个Agent并行处理，每个Agent顺序处理约1/3的图片列表：
- Agent 1: image_001 到 image_N/3
- Agent 2: image_N/3+1 到 image_2N/3
- Agent 3: image_2N/3+1 到 image_N（最后一批）

每个Agent内部按顺序逐张处理，一次一张图片，**每张之间间隔1秒**（避开讯飞秒级流控）。

为避免 Agent 自行拼命令时中文路径乱码，主线程预先生成一个**参数化的单张 OCR ps1**（带 BOM），Agent 只需 `powershell -File <ps1> -Num <编号>` 调用：

```powershell
# _ocr_one.ps1（参数化单张OCR，传入图片编号，输出 OK/FAIL）
param([Parameter(Mandatory=$true)][int]$Num)
$py = "C:\Users\admin\Miniconda3\envs\dsbot_env\python.exe"
$ocrPy = "<external_ocr.py路径>"
$pic = "<pic路径>\image_$($Num.ToString('D3')).png"
$txt = "<txt路径>\image_$($Num.ToString('D3')).txt"
& $py $ocrPy --images $pic 2>&1 | Set-Content -LiteralPath $txt -Encoding UTF8
if ($LASTEXITCODE -eq 0 -and (Get-Item -LiteralPath $txt).Length -gt 30) { Write-Output "OK"; exit 0 }
else { Write-Output "FAIL"; exit 1 }
```

**Agent 自修复职责（强制）**：
- 每张图执行后，Agent 必须检查：① 退出码为0；② 输出 `OK`。
- 任一不满足即失败（常见原因：讯飞秒级流控 11202、网络抖动、单张超时、**503 系统繁忙**）。
- 失败时 Agent 必须**立即重试该张**，重试间隔1秒，直到成功才处理下一张。**不得跳过、不得记 FAIL 继续、不得留给主线程事后补跑。**
- 遇 **503 持续错误**：暂停30秒后重试当前张（网关瞬时繁忙，等一会就好），不要因 503 放弃。
- 同一张连续失败5次仍不成功，才可上报该张并停止。

**检查OCR完成**：3个Agent全部结束后，主线程核对 `txt目录文件数 = pic目录文件数` 且无空txt（>30字节），才能进入步骤3。若有Agent上报的顽固失败项或中途503中断，主线程**串行**补跑剩余（不再并行，降低503概率）。

### 3. 组装md（必须用3个Agent并行，每个每批读10个txt写一次）
**⚠️ 步骤2全部完成后才能开始此步骤**
**⚠️ 必须用 3 个 Agent 并行，每个 Agent 输出独立 part 片段文件，最后主线程拼接。禁止多Agent直接写同一个md文件（会冲突）。**

#### 3.1 划分区间与 part 文件
按图片总数 N 分3段，每个 Agent 负责约 N/3 个 txt：
- Agent A: image_001 ~ image_N/3 → 输出 `part_A.md`
- Agent B: image_N/3+1 ~ image_2N/3 → 输出 `part_B.md`
- Agent C: image_2N/3+1 ~ image_N → 输出 `part_C.md`

part 文件放在工作目录下，**各 Agent 只写自己的 part 文件，不碰主 md**。

#### 3.2 每个 Agent 的工作方式
- 用 Read 工具**每批读 10 个 txt**，整理后用 Edit 追加到自己的 part 文件。
- part 文件开头用 Write 建一个含 `<!-- part X: image_aaa-bbb -->` 注释的空文件，之后每批用 Edit 在末尾 `<!--END-->` 锚点处滚动追加（替换为「新内容 + 新 `<!--END-->`」）。
- 最后一批写完，删除末尾 `<!--END-->` 锚点。

#### 3.3 整理规则（每个 Agent 严格遵守）
| 项 | 规则 |
|----|------|
| **去页眉页脚** | 每页重复的页眉（如「数字人民币 互联规范...」）、页脚（版本号、单独成列的修订人名）删除；表格行内的修订人保留 |
| **合并跨页续表** | 同一报文结构表跨多页时合并成一张 markdown 表，表头只保留一次 |
| **去重复序列图** | 连续多页文字大面积重复（OCR跨页重复识别同一序列图）时，保留最全的一页，其余去重，用 `> 注：image_XXX重复，已去重` 标注 |
| **分类处理** | `[纯文字]`→追加OCR正文（去掉首行图片名和分类标签行）；`[纯图形]`→只追加 `![image_XXX](pic/image_XXX.png)`；`[混合]`→OCR文字 + `![image_XXX](pic/image_XXX.png)`，末尾 `[需要原图引用]` 删除 |
| **文字忠于原文** | 不删段落、不改字、不臆造。OCR误识（如 dcap/dcep、Tag名乱码）保留原文，用 `> 注：` 标注疑似，不擅自改正 |
| **标题层级** | 按章节编号层级统一：`##`一级章、`###`类(5.x)、`####`报文(5.x.y)、`#####`节(5.x.y.z)、`######`场景(5.x.y.z.w) |

#### 3.4 边界续表处理（强制）
- Agent 开头若发现首个 txt 是上一区间的续表行（无表头），先 Read 上区间最后一个 txt 看末尾是什么表，按续行处理并标注 `> 注：image_XXX 疑似承接 image_YYY 续表`。
- Agent 末尾若某表未结束，标注 `> 注：image_XXX 的表NN未结束，续行见后文`。

#### 3.5 主线程拼接
3个Agent全部完成后：
1. 核对3个 part 文件都生成、各自区间末尾图片编号正确。
2. 用脚本（机械拼接，允许）把3个 part 按顺序拼到主 md：读主 md 头部 → 去各 part 末尾 `<!--END-->` 锚点和开头 part 注释 → 顺序拼接 → 写回主 md。
3. **删 part 之间的 `---` 分隔线**（拼接时易残留，正文流中不应有）。
4. **统一标题层级**：用脚本按章节编号层级批量规整全 md 标题（各 Agent 标的层级可能不一致）。
5. 删除 part 片段文件（已合并）。

---

## 输出结构

```
文字版/<文档名>/
├── pic/           # 图片
├── txt/           # OCR结果
├── part_A/B/C.md  # 组装中间产物（拼接后删除）
└── <文档名>.md    # 最终输出
```

---

## 备注

- `$env:SP_TOKEN` 由用户预配置，模型禁止修改
- 讯飞网关 503 在多 Agent 并行时易触发；OCR 或组装 Agent 中途 503 中断后，主线程**串行**补跑剩余区间，不要继续并行
- 大文档（>200张图）步骤2/3 都可能因 503 多次中断，属正常，按「串行补跑剩余」策略推进即可