---
name: web-2md
description: |
  单篇网页精抓转Markdown：针对单个文章URL，完整抓取正文文字+所有图片，图片下载到本地 images/ 目录并以相对路径内嵌，同时为每张图生成 img2txt 文字描述(放括号内)，让非多模态模型(如GLM)也能理解图片内容。
  当用户说"抓这篇文章"、"把这个网页转成md"、"抓网页带图片"、"单篇抓取"、"网页转markdown带图"时触发。
  与 web-article-fetcher 互补：后者做批量链接发现+采集，本工具做单篇完整还原(文字+图片本地化+图片描述)。
argument-hint: <文章URL> [-o 输出目录] [--name 文件名]
---

# web-2md —— 单篇网页精抓转 Markdown

针对**单篇文章 URL**，完整抓取正文文字 + 所有图片，并为每张图生成文字描述，输出带元信息标注、图片本地化、图片描述内嵌的 Markdown 文件。

## 与 web-article-fetcher 的区别

| 工具 | 定位 | 输入 | 图片处理 |
|------|------|------|---------|
| **web-article-fetcher** | 批量采集 | 栏目/首页 URL → 发现 N 篇文章 | 仅抓正文，图片为远程链接 |
| **web-2md**(本工具) | 单篇精抓 | 单篇文章 URL | **图片下载到本地** + **img2txt 文字描述** |

选用建议：
- 想抓"某栏目最新 20 篇新闻" → 用 `web-article-fetcher`
- 想完整保存"这一篇文章(含图+图说)" → 用 `web-2md`

## 核心能力

- **正文提取**：按站点适配选择器(掘金/知乎/微信等)，通用兜底
- **图片本地化**：用 Playwright `page.context.request` 抓图，共享浏览器 cookie，**绕过 CORS 与防盗链**(掘金字节跳动 CDN 签名图可抓)
- **图片转文字(img2txt)**：复用 `common` 的 `external_ocr.py`(讯飞 MaaS 多模态模型)，为每张图生成**详细描述**(覆盖图片类型、各区域内容、关键文字、数据/流程关系、核心观点)，**同时写入 alt 和正文括号内**，让纯文本模型(如 GLM)也能完整理解图片
- **标注元信息**：顶部嵌入来源 URL、抓取时间、图片统计、描述统计
- **干净输出**：剥离内联 CSS/script，保留标题层级

## 快速开始

```bash
# 抓单篇文章(默认存到 ~/Downloads/web_2md/)
cmd //c "call conda activate dsbot_env && python $PLUGIN_DIR/scripts/web2md.py https://juejin.cn/post/7592094358658138146"

# 指定输出目录和文件名
cmd //c "call conda activate dsbot_env && python $PLUGIN_DIR/scripts/web2md.py https://juejin.cn/post/xxx -o ~/Downloads/my_article --name 文章标题"
```

## 命令参数

```bash
python web2md.py <URL> [选项]

参数:
  <URL>              单篇文章 URL
  -o, --output       输出目录 (默认 ~/Downloads/web_2md)
  --name             输出文件名(不含扩展名，默认用文章标题)
```

## 输出结构

每篇文章单独一个子目录(目录名=md文件名),图片互不干扰,避免多篇文章图片重名冲突:

```
web_2md/
├── 文章标题A/                 # 子目录名 = md 文件名
│   ├── 文章标题A.md          # 标注 md(含本地图片引用 + 图片描述)
│   └── images/
│       ├── img_00.webp
│       ├── img_01.png
│       └── ...
├── 文章标题B/
│   ├── 文章标题B.md
│   └── images/
│       └── ...
```

## md 文件格式(原图 + 注脚式描述)

每张图:原图引用保持简洁,详细描述作为独立引用块注脚(不塞进 alt,不破坏正文结构):

```markdown
# 文章标题

> **来源**: https://juejin.cn/post/xxx
> **抓取时间**: 2026-07-30 10:00:00
> **本地图片**: images/ 目录（54/54 张，已内嵌相对路径）
> **图片描述**: 50/54 张已生成 img2txt 详细描述（引用块注脚）,便于非多模态模型解析

---

## 正文章节

正文内容...

![](images/img_00.webp)

> 【图片内容】
> 这是一张信息图表,标题为"AI CODING LANDSCAPE (JUNE 2025)",展示...
> 
> ### 一、图表结构  (描述内的标题已转义,不破坏文档结构)
> 
> 图表采用二维矩阵布局:
> - 纵向(Y轴):AI能力层级 L1-L5
> - 横向(X轴):应用领域

后续正文...
```

**设计要点**:
- 原图 `![](path)` 保留,alt 留空(简洁,不喧宾夺主)
- 详细描述放进 `> 【图片内容】` 引用块(视觉上是图注,与正文区分)
- 描述内的 `#`/`---` 等会破坏文档结构的标记已自动转义,不会变成真标题
- 纯文本模型(如 GLM)读 `【图片内容】` 标签即可获取图片完整信息

## 站点适配

| 站点 | 正文选择器 | 备注 |
|------|-----------|------|
| juejin.cn | `.article-viewer` / `article` | 字节 CDN 签名图，需 request 上下文 |
| zhuanlan.zhihu.com | `.Post-RichTextContainer` | 知乎专栏 |
| mp.weixin.qq.com | `#js_content` | 微信公众号 |
| 其他 | `article` / `main` / `.content` 通用兜底 | 自动尝试 |

新增站点适配：编辑 `scripts/web2md.py` 的 `SITE_PROFILES` 字典。

## 工作流程

```
单篇文章 URL
    ↓
[1] Playwright 打开页面 → 等正文选择器 → 取 outerHTML
    ↓
[2] 正则提取所有 <img> src(含 data-src 懒加载) → page.context.request.get() 下载 → images/
    ↓
[3] img2txt: 调 common 的 external_ocr(讯飞多模态模型) 并行为每张图生成描述
    ↓
[4] 剥离 style/script → markdownify 转 md → 替换图片为相对路径 → 嵌入描述(alt + 括号)
    ↓
拼接元信息头 → 写出 .md
```

## 依赖

- **common** 模块：`chrome_manager`(Playwright 浏览器管理)、`external_ocr.py`(图片转文字,讯飞 MaaS 接入)
- 环境变量(用户自行配置,**skill 不内置**):
  - `SP_TOKEN` —— 讯飞 MaaS API Key,用于 img2txt 图片描述。设置方式(用户自己操作,不要写进 skill 配置):
    - PowerShell 临时:`$env:SP_TOKEN="你的key"`
    - 永久(用户级):`setx SP_TOKEN "你的key"`(设后需重开终端)
    - 若未配置,图片仍会下载,但**跳过描述生成**(降级为纯图片引用)
- Python 包:`playwright`、`markdownify`(dsbot_env 已装)

## 常见问题

- **图片 0 下载**：通常是站点改版导致选择器失效，检查 `SITE_PROFILES`；或图片走特殊协议
- **图片描述 0 生成**：检查 `SP_TOKEN` 环境变量是否配置(skill 不内置 token,需用户自行设置 env);讯飞网关 503 时会自动跳过该图(降级为仅图片引用)
- **正文为空**：页面可能是纯 SPA 渲染，可尝试增加 `wait_for_timeout` 等待时间
- **OCR 慢**：54 张图约需 3-8 分钟(逐张调 API + 并发3),耐心等待
- **抓取超时**：Playwright 首次启动较慢，单篇正常耗时 30-60 秒(不含 OCR)
