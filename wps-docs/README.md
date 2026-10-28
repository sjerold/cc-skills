# WPS 云文档读写插件（wps-docs）

通过 WPS 网页版暴露的 JSAPI 读写 kdocs/金山云文档，支持智能文档（otl）、文字文档（docx/wps）等以 WPS 文字引擎打开的文档。

## 能力

| 命令 | 作用 | 是否需要登录 |
|------|------|--------------|
| `info` | 标题、字数、登录状态、编辑/评论权限 | 否 |
| `read` | 读取正文（可保存为 txt） | 否（公开分享链接可读） |
| `append` | 文末追加一段文字 | 是，且需编辑权限 |
| `replace` | 查找并替换文字 | 是，且需编辑权限 |
| `patch` | 按最小化 diff 逐段改稿，每段单独成一条修订 | 是，且需编辑权限 |
| `login` | 打开保持的 Chrome 窗口扫码登录 | — |

## 原理

kdocs 网页版把文档交给 WPS 编辑器渲染，页面暴露了 VBA 风格的 JSAPI：

```js
const doc = await window.WPSOpenApi.Application.ActiveDocument
const text = await (await doc.Content).Text
```

插件用 Playwright 打开文档、等待 `WPSOpenApi` 就绪，再读写 `Content`，最后调用 `WPSOpenApi.save()` 保存。写入前自动把原文备份到 `%LOCALAPPDATA%\wps-docs\backups\`。

## 安装

```bash
pip install -r requirements.txt
# 需要本机安装 Chrome
```

插件依赖 `common`（>=2.6.0）的 Chrome 管理模块；`--use-common` 模式会复用统一的 9222 调试 Chrome。

## 首次登录

```bash
python scripts/wps_doc.py login "https://www.kdocs.cn/l/xxxx"
```

窗口会一直保持打开，扫码登录后自动返回。登录态保存在 `%LOCALAPPDATA%\wps-docs\profile`，之后读写直接复用。

## 使用

```bash
# 文档信息
python scripts/wps_doc.py info "https://www.kdocs.cn/l/xxxx"

# 读取正文到文件
python scripts/wps_doc.py read "https://www.kdocs.cn/l/xxxx" --out doc.txt

# 文末追加
python scripts/wps_doc.py append "https://www.kdocs.cn/l/xxxx" "补充说明"

# 查找替换（默认只允许唯一匹配；多处匹配会列出位置并拒绝，--all 才全部替换）
python scripts/wps_doc.py replace "https://www.kdocs.cn/l/xxxx" "旧文字" "新文字"

# 最小化改稿（修订模式推荐）：每处改动拆成最小片段，逐条成为可审阅的修订
python scripts/wps_doc.py patch "https://www.kdocs.cn/l/xxxx" pairs.json
python scripts/wps_doc.py patch "https://www.kdocs.cn/l/xxxx" pairs.json --dry-run
```

### patch：最小化改稿

`pairs.json`：

```json
[
  ["旧的完整句子", "新的完整句子"],
  {"old": "另一处旧文字", "new": "另一处新文字"}
]
```

每处 `old` 必须在正文中唯一。命令会把每处替换拆成最小的 insert/delete/replace，
**按位置倒序**逐个写入，让每条修订只覆盖最小的字符区间：

```
关于数币达、智能合约、数币系统平台三接入的报告
→ 插入「公司接入」/ 「、」→「框架和央行端」/ 删除「平台三接入」
```

实现要点：

- 修订模式下被删除的文字仍占用 `Range` 坐标，所以必须倒序处理，保证已产生的修订标记都在右侧；
- 写入前用左侧 20 字上下文试探偏移，`Range(...).Text` 与原文逐字一致才落笔；
- 每步写完回读全文比对，任何不一致立即 `Revisions.RejectAll()` 整体回滚；
- 输出里带 `range: [start, end]`，即该操作精确落在正文的第几个字符。
- 标题编号（一、二、三）由 WPS 自动生成，正文里看不到，**不要手写编号**。

### 复用 common 的统一 Chrome

```bash
python scripts/wps_doc.py read "https://www.kdocs.cn/l/xxxx" --use-common
```

要求 9222 调试 Chrome 已登录 WPS；否则先在该 Chrome 中登录。

## 限制

- 仅支持网页版 WPS 能打开、且暴露 `WPSOpenApi` 的文档；表格/多维表请用 WPS 官方 AirScript。
- 写入需要账号对该文档有编辑权限；分享链接的匿名权限通常是“可评论”，只能读。
- `replace` 默认**只允许唯一匹配**：匹配到多处会返回 `multiple_matches` 并列出位置，不写入；确需全部替换才加 `--all`。
- `replace` 用 `Range` 精确改匹配片段，保留其余格式；但 WPS 文末的结构性段落标记无法删除，删除文末文字后可能留下一个空段落。
- **开启修订模式后不要用 `replace`**：被删除的文字仍占用 `Range` 坐标，正文索引与 `Range` 坐标不再相等，第 2 处起会错位。修订稿请用 `patch`（内部倒序执行并逐步校准）。
- 自动编号（一、二、三）不属于正文文字，`read` 读不到；改标题时不要手写编号，否则会出现「一、一、」。
- kdocs 前端实现可能变化，JSAPI 探测失败时先运行 `info` 排查。
- 请遵守 WPS 服务条款，控制操作频率。

## 故障排查

| 现象 | 处理 |
|------|------|
| `当前 Chrome 未登录 WPS` | 运行 `login` |
| `只有评论权限` | 请文档所有者把分享权限改为“可编辑” |
| `未读取到文档正文` | 确认链接可打开，且不是 PDF/表格/多维表 |
| 写入后未生效 | 刷新页面确认；查看 `backup` 文件比对原文 |
