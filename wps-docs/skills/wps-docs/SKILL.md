---
name: wps-docs
description: |
  WPS 云文档（kdocs / 金山文档）读写：查看文档信息、读取正文、在文末追加内容、查找替换并保存。
  当用户提到“WPS 云文档”“金山文档”“kdocs 链接”“在线文档读取/修改”“智能文档”时触发。
  仅适用于网页版 WPS 能打开并暴露 WPSOpenApi 的文档；需要编辑权限才能写入。
argument-hint: <info|read|append|replace|login> <URL> [...]
---

# WPS 云文档读写

用 Playwright 打开 kdocs 链接，调用 WPS 网页版 JSAPI 读写正文并保存。

## 快速开始

```bash
PLUGIN_DIR="C:/Users/admin/.claude/plugins/wps-docs"
PY="C:/Users/admin/miniconda3/envs/dsbot_env/python.exe"

# 1. 首次使用先登录（窗口保持打开，扫码后自动返回）
"$PY" "$PLUGIN_DIR/scripts/wps_doc.py" login "https://www.kdocs.cn/l/xxxx"

# 2. 查看文档状态
"$PY" "$PLUGIN_DIR/scripts/wps_doc.py" info "https://www.kdocs.cn/l/xxxx"

# 3. 读取正文
"$PY" "$PLUGIN_DIR/scripts/wps_doc.py" read "https://www.kdocs.cn/l/xxxx" --out doc.txt

# 4. 文末追加
"$PY" "$PLUGIN_DIR/scripts/wps_doc.py" append "https://www.kdocs.cn/l/xxxx" "补充说明"

# 5. 查找替换（默认只允许唯一匹配；多处会拒绝并列出位置，--all 才全部替换）
"$PY" "$PLUGIN_DIR/scripts/wps_doc.py" replace "https://www.kdocs.cn/l/xxxx" "旧文字" "新文字"
```

## 命令参数

```bash
python wps_doc.py <command> <URL> [选项]

info     URL                     标题、字数、登录状态、编辑/评论权限
read     URL [--json] [--out F]  读取正文；--json 同时输出 text 字段
append   URL TEXT                文末追加一段
replace  URL OLD NEW [--all]   查找替换；默认只允许唯一匹配，多处时拒绝并列出位置
login    URL [--profile-dir D]   打开窗口扫码登录，保持 profile

通用选项:
  --profile-dir DIR   独立 Chrome profile（默认 %LOCALAPPDATA%\wps-docs\profile）
  --use-common        复用 common 插件统一的 9222 调试 Chrome
  --headless          无头模式（read/info 默认开启，append/replace 默认关闭）
  --timeout SEC       页面加载超时（默认 60）
```

## 输出

所有命令输出 JSON。写入命令返回：

```json
{
  "ok": true,
  "action": "append",
  "url": "...",
  "backup": "C:\\Users\\...\\wps-docs\\backups\\20261027-170000.txt",
  "before_len": 4585,
  "after_len": 4588,
  "after_tail": "...\\r测试\\r",
  "saved": "WPSOpenApi.save"
}
```

`ok=false` 时看 `error` / `saveError`；原文已备份在 `backup`。

## 关键行为

1. **登录态**：默认使用 `%LOCALAPPDATA%\wps-docs\profile`，首次 `login` 后长期复用；`--use-common` 走 common 的统一 Chrome。
2. **权限检查**：`append`/`replace` 前检查页面是否显示“Sign in Now / 立即登录”和“Can Comment / 可评论”。只有评论权限时直接报错，不写入。
3. **自动备份**：写入前把全文保存到 `backups/`。
4. **保存与校验**：写入后调用 `WPSOpenApi.save()`，再回读 `Content.Text`，返回 `after_len` / `after_tail`。
5. **追加方式**：`doc.Range(content.End - 1, content.End - 1).Text = "\r" + text`。网页版没有 `Content.InsertAfter`。
6. **替换方式**：按正文索引定位匹配，用 `doc.Range(start, end).Text = new` 精确替换，保留其余格式。默认**只允许唯一匹配**；匹配多处时返回 `multiple_matches`、列出前 8 处上下文并拒绝写入，确需全部替换才加 `--all`。

## 限制

- 只支持网页版 WPS 能打开、且暴露 `WPSOpenApi` 的文档（智能文档 otl 以 WPS 文字引擎打开，可用）。
- 表格 / 多维表格请用 WPS 官方 AirScript（`KSDrive` 仅支持 et/ksheet/dbt）。
- 分享链接默认是“可评论”权限，写入前需文档所有者改为“可编辑”并用有权限账号登录。
- kdocs 前端可能改版；JSAPAI 不可用时先跑 `info` 排查。
- 控制频率，避免触发风控。

## 故障排查

| 现象 | 处理 |
|------|------|
| `当前 Chrome 未登录 WPS` | 先运行 `login` |
| `只有评论权限` | 让所有者把分享权限改为可编辑 |
| `未读取到文档正文` | 确认链接不是 PDF/表格/多维表，且页面已加载完成 |
| `connection refused 9222` | 加 `--profile-dir` 用独立 profile，或先启动 common 的调试 Chrome |
