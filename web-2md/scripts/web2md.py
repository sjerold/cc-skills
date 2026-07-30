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


# ---------- 站点适配:正文选择器、图片 Referer ----------
SITE_PROFILES = {
    'juejin.cn': {
        'selectors': ['.article-viewer', 'article', '[class*="article-content"]'],
        'title_suffix': ' - 掘金',
        'referer': 'https://juejin.cn/',
    },
    'zhuanlan.zhihu.com': {
        'selectors': ['.Post-Sub', '.Post-RichTextContainer', 'article'],
        'title_suffix': ' - 知乎专栏',
        'referer': 'https://www.zhihu.com/',
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


def desc_image(img_path):
    """调 external_ocr 给单张图生成描述,返回描述字符串或 None"""
    import subprocess
    try:
        r = subprocess.run(
            ['python', _EXTERNAL_OCR, '--images', str(img_path),
             '--prompt', DESC_PROMPT, '--output', str(img_path) + '.txt'],
            capture_output=True, timeout=300, text=True, encoding='utf-8'
        )
        txt_path = Path(str(img_path) + '.txt')
        if r.returncode == 0 and txt_path.exists() and txt_path.stat().st_size > 10:
            desc = txt_path.read_text(encoding='utf-8').strip()
            txt_path.unlink(missing_ok=True)
            # 去掉首行可能的图片名/标签行(多种格式)
            desc = re.sub(r'^=+\s*\S+\s*=+\s*\n', '', desc)  # === img_xx.webp ===
            desc = re.sub(r'^(image_[^\n]*|图片[^\n]*)\n', '', desc)
            desc = desc.strip()
            return desc[:1000] if desc else None
    except Exception as e:
        print(f"    OCR失败 {img_path.name}: {e}")
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
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        future_to_name = {ex.submit(desc_image, img_dir / n): n for n in names}
        done = 0
        for fut in concurrent.futures.as_completed(future_to_name):
            n = future_to_name[fut]
            try:
                d = fut.result()
                if d:
                    desc_map[n] = d
                done += 1
                print(f"    描述进度 {done}/{len(names)}")
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
    srcs = []
    for s in raw:
        if s.startswith('data:'):
            continue
        s = s.replace('&amp;', '&')
        if s.startswith('//'):
            s = 'https:' + s
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
    desc_map = desc_images_parallel(img_dir, names, workers=3)
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
