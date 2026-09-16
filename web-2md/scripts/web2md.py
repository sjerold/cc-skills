# -*- coding: utf-8 -*-
"""
web-2md: 单篇网页精抓 → 标注 Markdown(文字 + 图片本地化)

与 web-article-fetcher(批量链接发现)的区别:
  - 本工具针对【单篇文章 URL】,完整还原正文 + 图片
  - 图片用 Playwright request 上下文抓取(共享 cookie,绕过 CORS / 防盗链)
  - 输出一份带元信息标注、图片本地化的 md

用法:
  python web2md.py <URL> [-o 输出目录] [--name 文件名(不含扩展名)]
"""
import sys, os, io, re, asyncio, hashlib, argparse
import concurrent.futures
from pathlib import Path
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 接入 common 模块(Playwright 浏览器管理)
_HERE = os.path.dirname(os.path.abspath(__file__))
_COMMON = os.path.join(_HERE, '..', '..', 'common', 'scripts')
sys.path.insert(0, _COMMON)
from chrome_manager import get_browser_async, get_page_async, close_browser_async
from markdownify import markdownify as md_convert

# img2txt:复用 common 的 external_ocr(讯飞 MaaS 多模态)
_EXTERNAL_OCR = os.path.join(_HERE, '..', '..', 'common', 'scripts', 'external_ocr.py')

# 描述型 prompt —— 详细描述图片内容,供非多模态模型理解
# 要求覆盖:图片类型、各区域内容、关键文字、数据/流程/对比关系等
DESC_PROMPT = """请详细描述这张图片的内容,目标是让无法看图的读者(如纯文本模型)能完整理解图片传达的信息。按以下要点展开:

1. 图片类型:截图/图表/流程图/示意图/对比图/照片等
2. 主体内容:图里有什么,各区域/模块分别表示什么
3. 关键文字:标题、坐标轴标签、图例、节点文字、注释等(尽量原文列出)
4. 数据与关系:若是图表,说明趋势/对比/数值含义;若是流程图,说明节点间的流转关系;若是对比图,说明左右/前后差异
5. 结论:这张图想表达的核心观点是什么

要求:
- 信息完整,不遗漏关键要素,但不要臆造图中没有的内容
- 用清晰的条理组织(可分点),便于阅读
- 不要加"这张图片显示了"之类的前缀,直接开始描述
- 中文输出"""

# GitHub 数学公式渲染成 MathML(<math-renderer>),markdownify 会把每个符号拆成独立行。
# 对 .md 文件直接抓 raw 原文(公式保留 $...$),得到真正的原文。
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36'
GITHUB_BLOB_RE = re.compile(r'https?://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)')


# ---------- 站点适配:正文选择器、图片 Referer ----------
SITE_PROFILES = {
    'juejin.cn': {
        'selectors': ['.article-viewer', 'article', '[class*="article-content"]'],
        'title_suffix': ' - 掘金',
        'referer': 'https://juejin.cn/',
    },
    'zhuanlan.zhihu.com': {
        'selectors': ['.Post-RichTextContainer', '.RichText.ztext', 'article'],
        'title_suffix': ' - 知乎',
        'referer': 'https://www.zhihu.com/',
        # 知乎匿名访问会弹登录 modal,遮挡正文;需先关弹窗+滚动触发懒加载,
        # 否则正文选择器取到的是页面底部的"推荐阅读"区
        'dismiss_selectors': ['svg.Icon--close', 'button.Modal-closeButton', '.Modal-closeButton', 'button[class*=close]'],
        'scroll_lazy': True,
    },
    'mp.weixin.qq.com': {
        'selectors': ['#js_content', '.rich_media_content'],
        'title_suffix': '',
        'referer': 'https://mp.weixin.qq.com/',
    },
    # 默认通用适配
    '_default': {
        'selectors': ['article', 'main', '[role="main"]', '.content', '#content'],
        'title_suffix': '',
        'referer': None,
    },
}


def get_profile(url):
    for host, prof in SITE_PROFILES.items():
        if host != '_default' and host in url:
            return prof
    return SITE_PROFILES['_default']


def slugify(s, maxlen=60):
    """标题转文件名安全串"""
    s = re.sub(r'[\\/:*?"<>|\n\r\t]', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s[:maxlen] if s else 'article'


async def fetch_page(url):
    """抓页面,返回 (title, html, page) —— page 保留用于后续图片抓取"""
    prof = get_profile(url)
    pw, br = await get_browser_async()
    if not br:
        print("浏览器启动失败"); return None
    page = await get_page_async(br, url=url, timeout=45000)

    # 预动作:部分站点有登录弹窗遮挡正文,或有内容需滚动才懒加载
    # (典型:知乎匿名访问的登录 modal → 正文取不到,只拿到底部"推荐阅读")
    for sel in prof.get('dismiss_selectors', []):
        try:
            await page.locator(sel).first.click(timeout=2500)
            await page.wait_for_timeout(600)
            print(f"  已关闭遮挡弹窗: {sel}")
        except Exception:
            pass
    if prof.get('scroll_lazy'):
        try:
            await page.evaluate("""async () => {
                for (let y = 0; y < document.body.scrollHeight; y += window.innerHeight) {
                    window.scrollTo(0, y);
                    await new Promise(r => setTimeout(r, 300));
                }
                window.scrollTo(0, 0);
                await new Promise(r => setTimeout(r, 800));
            }""")
            print("  已滚动触发懒加载")
            await page.wait_for_timeout(1500)
        except Exception:
            pass

    # 等正文选择器出现
    for sel in prof['selectors']:
        try:
            await page.wait_for_selector(sel, timeout=15000)
            break
        except Exception:
            continue
    await page.wait_for_timeout(3000)  # 等懒加载图片

    title = (await page.title()).replace(prof['title_suffix'], '').strip()
    sel_list = prof['selectors']
    html = await page.evaluate("""(sels) => {
        for (const s of sels) {
            const el = document.querySelector(s);
            if (el && el.innerText.length > 200) return el.outerHTML;
        }
        return document.body.innerHTML;
    }""", sel_list)
    return title, html, page, pw, br


def desc_image(img_path, max_retries=5):
    """调 external_ocr 给单张图生成描述,失败自动重试(带退避)。
    OCR 脚本本身只执行一次,重试职责由本调用方承担(对齐 docx-img2md 规范)。
    返回描述字符串或 None。
    """
    import subprocess, time
    txt_path = Path(str(img_path) + '.txt')
    last_err = ''
    for attempt in range(1, max_retries + 1):
        # 清掉上次失败的残留输出文件
        txt_path.unlink(missing_ok=True)
        try:
            r = subprocess.run(
                ['python', _EXTERNAL_OCR, '--images', str(img_path),
                 '--prompt', DESC_PROMPT, '--output', str(txt_path)],
                capture_output=True, timeout=300, text=True, encoding='utf-8'
            )
            if r.returncode == 0 and txt_path.exists() and txt_path.stat().st_size > 10:
                desc = txt_path.read_text(encoding='utf-8').strip()
                txt_path.unlink(missing_ok=True)
                # 去掉首行可能的图片名/标签行(多种格式)
                desc = re.sub(r'^=+\s*\S+\s*=+\s*\n', '', desc)  # === img_xx.webp ===
                desc = re.sub(r'^(image_[^\n]*|图片[^\n]*)\n', '', desc)
                desc = desc.strip()
                if desc:
                    if attempt > 1:
                        print(f"    {img_path.name} 第{attempt}次重试成功")
                    return desc[:1000]
            # 失败:记录错误,退避后重试
            last_err = (r.stderr or '').strip().split('\n')[-1][:80] or f'exit={r.returncode}'
        except subprocess.TimeoutExpired:
            last_err = 'timeout'
        except Exception as e:
            last_err = str(e)[:80]
        if attempt < max_retries:
            wait = 5 * attempt  # 5,10,15,20 秒递增退避
            print(f"    {img_path.name} 第{attempt}次失败({last_err}),{wait}s 后重试")
            time.sleep(wait)
    print(f"    {img_path.name} 放弃({max_retries}次均失败): {last_err}")
    txt_path.unlink(missing_ok=True)
    return None


def extract_svg_desc(svg_path):
    """SVG 是矢量图(XML 文本),无需 OCR,直接读 <title>/<desc>/<text> 提取描述"""
    import xml.etree.ElementTree as ET
    try:
        tree = ET.parse(str(svg_path))
        root = tree.getroot()
        title = desc = ''
        for child in root:
            tag = child.tag.split('}')[-1]
            if tag == 'title' and not title:
                title = (child.text or '').strip()
            elif tag == 'desc' and not desc:
                desc = (child.text or '').strip()
        texts = []
        for elem in root.iter():
            tag = elem.tag.split('}')[-1]
            if tag == 'text' and elem.text and elem.text.strip():
                texts.append(elem.text.strip())
        parts = []
        if title:
            parts.append(f"图题: {title}")
        if desc:
            parts.append(f"说明: {desc}")
        if texts:
            parts.append("图中文字: " + " | ".join(texts[:20]))
        return "\n".join(parts) if parts else None
    except Exception:
        return None


def desc_images_parallel(img_dir, names, workers=3):
    """并行给图片生成描述,返回 {文件名: 描述}"""
    desc_map = {}
    if not names:
        return desc_map
    # SP_TOKEN 由用户自行配置(skill 不内置),未配置则跳过 OCR
    if not os.environ.get('SP_TOKEN'):
        print("    [跳过] 未配置 SP_TOKEN 环境变量,跳过图片描述(图片仍保留,仅无文字描述)")
        return desc_map
    # SVG 矢量图无需 OCR:直接从 XML 提取 title/desc/文本作为描述
    svg_names = [n for n in names if n.lower().endswith('.svg')]
    for n in svg_names:
        d = extract_svg_desc(img_dir / n)
        if d:
            desc_map[n] = d
            print(f"    [SVG] {n} 已从 XML 提取描述")
    # 位图(非 SVG)走 OCR
    ocr_names = [n for n in names if not n.lower().endswith('.svg')]
    if not ocr_names:
        return desc_map
    # 并发降到2:讯飞网关 503 主因是高并发,低并发 + 重试更稳
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        future_to_name = {ex.submit(desc_image, img_dir / n): n for n in ocr_names}
        done = 0
        for fut in concurrent.futures.as_completed(future_to_name):
            n = future_to_name[fut]
            try:
                d = fut.result()
                if d:
                    desc_map[n] = d
                done += 1
                print(f"    描述进度 {done}/{len(ocr_names)}")
            except Exception:
                done += 1
    return desc_map


async def grab_images(page, srcs, img_dir, referer):
    """用 page.context.request 抓图,返回 {原src: 本地文件名}"""
    img_map = {}
    ok = 0
    for i, src in enumerate(srcs):
        try:
            headers = {}
            if referer:
                headers['Referer'] = referer
            resp = await page.context.request.get(src, timeout=30000)
            if not resp.ok:
                continue
            body = await resp.body()
            if len(body) < 200:
                continue
            ct = resp.headers.get('content-type', 'image/png')
            ext = '.png'
            for e in ['jpeg', 'jpg', 'png', 'gif', 'webp', 'svg', 'bmp']:
                if e in ct:
                    ext = '.jpg' if e == 'jpeg' else '.' + e
            name = f"img_{ok:02d}{ext}"
            (img_dir / name).write_bytes(body)
            img_map[src] = name
            ok += 1
        except Exception:
            continue
    return img_map, ok


def build_markdown(title, html, img_map, srcs, url, desc_map):
    # 优先用正文第一个 h1 作为标题:页面 <title> 常是站点导航名(如 GitHub 的 "repo/blob at main")
    m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S | re.I)
    if m:
        h1 = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        if h1:
            title = h1
    # 剥离 style/script
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.S | re.I)
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.S | re.I)

    # 替换图片 src 为本地相对路径(覆盖 &amp; 与协议相对形式)
    for src, name in img_map.items():
        rel = 'images/' + name
        html = html.replace(src, rel)
        html = html.replace(src.replace('&', '&amp;'), rel)
        if src.startswith('https://'):
            html = html.replace('//' + src.split('//', 1)[1], rel)
            # 单斜杠站内相对路径形式(/owner/repo/raw/...),HTML 里 src 可能是这种
            path_only = '/' + src.split('//', 1)[1].split('/', 1)[1]
            html = html.replace(path_only, rel)
            html = html.replace(path_only.replace('&', '&amp;'), rel)

    md_text = md_convert(html, heading_style='ATX', strip=['script', 'style'])
    md_text = re.sub(r'\n{3,}', '\n\n', md_text).strip()

    # markdownify 对带 alt 属性的 <img> 可能转成畸形(如 "**alt文字**](path)" 或孤立 "](path)")。
    # 用正则把每个含 images/img_xx 的图片引用整行重写为标准格式:原图 + 独立注脚块。
    # 原图保持简洁(空 alt),大段详细描述放进引用块 > 【图片内容】...,作为图片注脚,
    # 不塞进 alt、不重复、不破坏原文正文结构,纯文本模型也能读到。
    def rewrite_img(m):
        rel = m.group(1)
        name = rel.split('/')[-1]
        desc = desc_map.get(name)
        line = f'![]({rel})'
        if desc:
            # 描述里可能含 ##/--- 等会破坏文档结构的 markdown 标记,在引用块里需转义
            safe = desc
            safe = re.sub(r'(?m)^(\s*)(#{1,6}\s)', r'\1\\#\2', safe)  # 转义行首标题
            safe = re.sub(r'(?m)^\s*-{3,}\s*$', '', safe)             # 删分隔线
            safe = re.sub(r'(?m)^\s*={3,}\s*$', '', safe)           # 删另一种分隔线
            desc_lines = safe.strip().split('\n')
            block = '\n'.join('> ' + l if l.strip() else '>' for l in desc_lines)
            line += f'\n\n> 【图片内容】\n{block}'
        return line
    md_text = re.sub(
        r'(?m)^[^\n]*?\]\((images/img_[^)\s]+)\)[^\n]*$',
        rewrite_img, md_text
    )

    short_title = title.split('本文介绍了')[0].strip()
    short_title = re.sub(r'\s+', ' ', short_title)[:60] or '网页文章'

    meta = f"""# {short_title}

> **来源**: [{url}]({url})
> **抓取时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
> **本地图片**: images/ 目录（{len(img_map)}/{len(srcs)} 张，已内嵌相对路径）
> **图片描述**: {len(desc_map)}/{len(img_map)} 张已生成 img2txt 文字描述（括号内）,便于非多模态模型解析

---

"""
    return meta + md_text


def is_github_md(url):
    """GitHub blob 页面的 .md 文件 → 直接抓 raw 原文(避免 MathML 公式拆行)"""
    m = GITHUB_BLOB_RE.match(url)
    return bool(m and m.group(4).lower().endswith('.md'))


def fetch_github_raw(url):
    """抓 GitHub .md 的 raw 原文。返回 (title, markdown, img_base_url)"""
    import urllib.request
    m = GITHUB_BLOB_RE.match(url)
    owner, repo, branch, path = m.groups()
    head, _sep, _tail = path.rpartition('/')
    dirname = (head + '/') if head else ''  # 根目录文件(如 README.md)目录名应为空,否则拼成 FILE/ 使相对图 404
    raw_url = f'https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}'
    img_base = f'https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{dirname}'
    req = urllib.request.Request(raw_url, headers={'User-Agent': UA})
    md_text = urllib.request.urlopen(req, timeout=30).read().decode('utf-8')
    title = '网页文章'
    for line in md_text.split('\n'):
        ls = line.strip()
        if ls.startswith('# ') and not ls.startswith('## '):
            title = ls[2:].strip()
            break
    # 兜底:README 常把标题写成 HTML <h1>(可能带属性),而 markdown 首个 # 藏在注释里
    if title == '网页文章':
        m = re.search(r'<h1[^>]*>(.*?)</h1>', md_text, re.S | re.I)
        if m:
            h1 = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if h1:
                title = h1
    return title, md_text, img_base


def grab_images_raw(md_text, img_dir, img_base):
    """从 raw markdown 提取图片引用并下载(urllib,无需 Playwright)。返回 (img_map, ok)"""
    import urllib.request
    img_map = {}
    ok = 0
    # markdown 引用 ![...](...) 与 HTML <img src="..."> 都提取
    # (README 常用 HTML 形式放架构总览图,如 <img src="assets/main.png">)
    refs = re.findall(r'!\[[^\]]*\]\(([^)]+)\)|<img\b[^>]*\bsrc=["\']([^"\']+)["\']', md_text, re.I)
    refs = [a or b for a, b in refs]
    seen = set()
    for path in refs:
        if path in seen:
            continue
        seen.add(path)
        if path.startswith('data:') or path.startswith('#'):
            continue
        if path.startswith('http'):
            url = path
        elif path.startswith('/'):
            continue
        else:
            url = img_base + path
        ext = os.path.splitext(path)[1].lower()
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            body = urllib.request.urlopen(req, timeout=30).read()
            if len(body) < 100:
                continue
            if ext not in ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp'):
                ext = '.png'
            name = f'img_{ok:02d}{ext}'
            (img_dir / name).write_bytes(body)
            img_map[path] = name
            ok += 1
        except Exception:
            continue
    return img_map, ok


def build_raw_markdown(title, md_text, img_map, url, desc_map):
    """把 raw markdown 的图片引用替换为本地路径,嵌入描述块,公式保留 $...$ 原样"""
    def block_of(desc):
        safe = re.sub(r'(?m)^(\s*)(#{1,6}\s)', r'\1\\#\2', desc)
        safe = re.sub(r'(?m)^\s*-{3,}\s*$', '', safe)
        safe = re.sub(r'(?m)^\s*={3,}\s*$', '', safe)
        dl = safe.strip().split('\n')
        return '\n'.join('> ' + l if l.strip() else '>' for l in dl)

    def repl(m):
        path = m.group(1)
        name = img_map.get(path)
        if not name:
            return m.group(0)
        line = f'![](images/{name})'
        desc = desc_map.get(name)
        if desc:
            line += f'\n\n> 【图片内容】\n{block_of(desc)}'
        return line

    md_text = re.sub(r'!\[[^\]]*\]\(([^)]+)\)', repl, md_text)

    # HTML <img src="..."> 本地化(README 常用此形式放架构图),保留 src 之外属性
    def repl_html_src(m):
        src = m.group(2)
        name = img_map.get(src)
        if not name:
            return m.group(0)
        return m.group(1) + f'images/{name}' + m.group(3)
    md_text = re.sub(r'(<img\b[^>]*\bsrc=["\'])([^"\']+)(["\'])', repl_html_src, md_text)

    md_text = re.sub(r'\n{3,}', '\n\n', md_text).strip()
    meta = f"""# {title}

> **来源**: [{url}]({url})
> **抓取时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
> **本地图片**: images/ 目录（{len(img_map)} 张，已内嵌相对路径）
> **图片描述**: {len(desc_map)}/{len(img_map)} 张已生成 img2txt 文字描述（括号内）,便于非多模态模型解析

---

"""
    return meta + md_text


async def main():
    ap = argparse.ArgumentParser(description='单篇网页精抓 → 标注 Markdown(含图片本地化)')
    ap.add_argument('url', help='文章 URL')
    ap.add_argument('-o', '--output', default='~/Downloads/web_2md', help='输出目录(默认 ~/Downloads/web_2md)')
    ap.add_argument('--name', default=None, help='输出文件名(不含扩展名,默认用标题)')
    ap.add_argument('--limit-img', type=int, default=0, help='只处理前 N 张图(0=全部,测试用)')
    args = ap.parse_args()

    url = args.url
    out_dir = Path(os.path.expanduser(args.output))
    out_dir.mkdir(parents=True, exist_ok=True)
    prof = get_profile(url)

    # GitHub .md 文件:直接抓 raw 原文(公式保留 $...$,避免 MathML 拆行),无需 Playwright
    if is_github_md(url):
        title, md_text, img_base = fetch_github_raw(url)
        print(f"[1/4] 抓取 raw 原文: {url}")
        print(f"  标题: {title}")
        print(f"  原文: {len(md_text)} 字符")

        fname_base = args.name or slugify(title)
        fname = fname_base + '.md'
        article_dir = out_dir / fname_base
        img_dir = article_dir / 'images'
        article_dir.mkdir(parents=True, exist_ok=True)
        img_dir.mkdir(parents=True, exist_ok=True)
        out_file = article_dir / fname

        refs = re.findall(r'!\[[^\]]*\]\(([^)]+)\)', md_text)
        if args.limit_img and args.limit_img > 0:
            refs = refs[:args.limit_img]
            print(f"  --limit-img {args.limit_img}: 只处理前 {len(refs)} 张")
        print(f"  发现图片 {len(refs)} 张")

        print("[2/4] 下载图片(raw, urllib)...")
        img_map, ok = grab_images_raw(md_text, img_dir, img_base)
        print(f"  成功 {ok}/{len(refs)}")

        print("[3/4] 图片转文字(img2txt)...")
        names = sorted(img_map.values())
        desc_map = desc_images_parallel(img_dir, names, workers=2)
        print(f"  描述成功 {len(desc_map)}/{len(names)}")

        print("[4/4] 生成 Markdown...")
        md_out = build_raw_markdown(title, md_text, img_map, url, desc_map)
        out_file.write_text(md_out, encoding='utf-8')

        print(f"\n完成")
        print(f"  Markdown → {out_file}")
        print(f"  图片目录 → {img_dir}（{ok} 张）")
        print(f"  图片描述 → {len(desc_map)}/{len(names)} 张已生成")
        return

    print(f"[1/4] 抓取页面: {url}")
    res = await fetch_page(url)
    if not res:
        return
    title, html, page, pw, br = res
    print(f"  标题: {title[:50]}")
    print(f"  正文 HTML: {len(html)} 字符")

    # 先确定文件名(与 --name 或标题 slug 一致),图片子目录与 md 同名
    # 避免多篇文章图片堆在同一 images/ 目录导致重名冲突
    fname_base = args.name or slugify(title)
    fname = fname_base + '.md'
    article_dir = out_dir / fname_base
    img_dir = article_dir / 'images'
    article_dir.mkdir(parents=True, exist_ok=True)
    img_dir.mkdir(parents=True, exist_ok=True)
    out_file = article_dir / fname

    # 提取图片 src(含 data-src),还原 &amp; -> &,补协议
    raw = re.findall(r'<img[^>]+(?:src|data-src)=["\']([^"\']+)["\']', html, re.I)
    from urllib.parse import urlsplit
    origin = f"{urlsplit(url).scheme}://{urlsplit(url).netloc}"
    srcs = []
    for s in raw:
        if s.startswith('data:'):
            continue
        s = s.replace('&amp;', '&')
        if s.startswith('//'):
            s = 'https:' + s
        elif s.startswith('/'):
            # 站内相对路径(如 GitHub 仓库内 /owner/repo/raw/...),补页面 origin
            s = origin + s
        srcs.append(s)
    seen = set()
    srcs = [s for s in srcs if not (s in seen or seen.add(s))]
    if args.limit_img and args.limit_img > 0:
        srcs = srcs[:args.limit_img]
        print(f"  --limit-img {args.limit_img}: 只处理前 {len(srcs)} 张")
    print(f"  发现图片 {len(srcs)} 张")

    print("[2/4] 下载图片(Playwright request 上下文,绕过 CORS/防盗链)...")
    img_map, ok = await grab_images(page, srcs, img_dir, prof['referer'])
    print(f"  成功 {ok}/{len(srcs)}")

    await close_browser_async(br, pw, keep_running=True)

    print("[3/4] 图片转文字(img2txt,并行)...")
    names = sorted(img_map.values())
    desc_map = desc_images_parallel(img_dir, names, workers=2)
    print(f"  描述成功 {len(desc_map)}/{len(names)}")

    print("[4/4] 生成 Markdown...")
    md_text = build_markdown(title, html, img_map, srcs, url, desc_map)

    out_file.write_text(md_text, encoding='utf-8')

    print(f"\n完成")
    print(f"  Markdown → {out_file}")
    print(f"  图片目录 → {img_dir}（{ok} 张）")
    print(f"  图片描述 → {len(desc_map)}/{len(names)} 张已生成")


if __name__ == '__main__':
    asyncio.run(main())
