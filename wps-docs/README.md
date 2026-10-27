# WPS 云文档读写插件（wps-docs）

通过 WPS 网页版暴露的 JSAPI 读写 kdocs/金山云文档，支持智能文档（otl）、文字文档（docx/wps）等以 WPS 文字引擎打开的文档。

## 能力

| 命令 | 作用 | 是否需要登录 |
|------|------|--------------|
| `info` | 标题、字数、登录状态、编辑/评论权限 | 否 |
| `read` | 读取正文（可保存为 txt） | 否（公开分享链接可读） |
| `append` | 文末追加一段文字 | 是，且需编辑权限 |
| `replace` | 查找并替换文字 | 是，且需编辑权限 |
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
```

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
- kdocs 前端实现可能变化，JSAPI 探测失败时先运行 `info` 排查。
- 请遵守 WPS 服务条款，控制操作频率。

## 故障排查

| 现象 | 处理 |
|------|------|
| `当前 Chrome 未登录 WPS` | 运行 `login` |
| `只有评论权限` | 请文档所有者把分享权限改为“可编辑” |
| `未读取到文档正文` | 确认链接可打开，且不是 PDF/表格/多维表 |
| 写入后未生效 | 刷新页面确认；查看 `backup` 文件比对原文 |
