#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
百度搜索脚本 - 异步版本

使用异步 Playwright，配合 common 模块的异步 chrome_manager。
"""

import sys
import os
import re
import json
import io
import base64
import argparse
import uuid
import urllib.parse
from datetime import datetime

# 添加common模块路径
_current_dir = os.path.dirname(os.path.abspath(__file__))
_common_dir = os.path.join(os.path.dirname(os.path.dirname(_current_dir)), 'common', 'scripts')
sys.path.insert(0, _common_dir)

# 导入异步 common 模块（sys.path 已设置，直接导入）
from chrome_manager import (
    get_browser_async, get_page_async, close_browser_async, close_page_async,
    try_acquire_instance_lock,
    HAS_PLAYWRIGHT
)

from web_fetcher import fetch_urls_async

from content_parser import extract_content

from markdown_writer import save_search_report, save_summary

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

# 导入评分器
try:
    from scorer import calculate_quality_score
except ImportError:
    _scorer_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scorer.py')
    import importlib.util
    spec = importlib.util.spec_from_file_location("scorer", _scorer_path)
    scorer_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scorer_module)
    calculate_quality_score = scorer_module.calculate_quality_score

# 导入 AI 总结器（用于主流程生成深度分析，可选）
try:
    import ai_summarizer
    HAS_AI_SUMMARIZER = True
except ImportError:
    HAS_AI_SUMMARIZER = False


# ============ 配置 ============

DEFAULT_OUTPUT_DIR = os.path.join(os.path.expanduser('~'), 'Downloads', 'baidu_search')

# 跳过的域名（视频、图片、下载站等）
SKIP_DOMAINS = [
    # 视频网站
    'bilibili.com', 'www.bilibili.com',
    'youtube.com', 'youtu.be',
    'youku.com', 'v.youku.com',
    'iqiyi.com', 'www.iqiyi.com',
    'qq.com/video', 'v.qq.com',
    'douyin.com', 'www.douyin.com',
    'kuaishou.com', 'www.kuaishou.com',
    'acfun.cn', 'www.acfun.cn',
    'ted.com',
    # 图片网站
    'image.baidu.com', 'tupian.baidu.com',
    'images.baidu.com',
    'pixiv.net',
    'unsplash.com',
    'pinterest.com',
    'instagram.com',
    'flickr.com',
    # 文件下载站
    'download.csdn.net',
    'pan.baidu.com',
    'wenku.baidu.com',
    # 其他无文章内容的站点
    'music.163.com',
    'weibo.com',  # 微博内容太短
]


def resolve_real_url(href):
    """把百度跳转链接还原为真实地址；非跳转链接原样返回。

    百度搜索结果 href 通常是 https://www.baidu.com/link?url=<base64url>，
    不还原时域名检测(should_skip_url / 打分)全部失效。
    """
    if not href:
        return href
    href = href.strip()

    # 协议相对链接补全
    if href.startswith('//'):
        href = 'https:' + href

    # 仅对已知跳转域名尝试解码
    if 'baidu.com/link?' in href or '/link?' in href or 'baidu.com/baidu.php' in href:
        try:
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
            enc = qs.get('url', [None])[0]
            if enc:
                enc = urllib.parse.unquote(enc).strip('=')
                pad = '=' * (-len(enc) % 4)
                try:
                    decoded = base64.urlsafe_b64decode(enc + pad)
                except Exception:
                    decoded = base64.b64decode(enc + pad)
                real = decoded.decode('utf-8', 'ignore').strip()
                if real.startswith('//'):
                    real = 'https:' + real
                if real.startswith(('http://', 'https://')):
                    return real
        except Exception:
            pass

    return href


def extract_domain(url):
    """从 URL 提取主域名(小写)"""
    if not url:
        return ''
    u = url
    if '://' in u:
        u = u.split('://', 1)[1]
    u = u.split('/')[0]
    u = u.split(':')[0]
    u = u.split('@')[-1]
    return u.lower()


def backfill_real_urls(results, query, urls_to_fetch, fetched):
    """抓取后用真实 URL/域名回填结果并重打分。

    百度跳转链接的 url= 参数无法离线解码出真实地址，因此真实域名只能在抓取
    (page.url 跳转后)拿到。回填后，展示真实链接、用真实域名重新评分。
    """
    url_to_result = {r.get('url'): r for r in results}
    for fr in fetched:
        orig = fr.get('original_url')
        r = url_to_result.get(orig)
        if not r or not fr.get('success'):
            continue
        final_url = fr.get('url') or orig
        r['url'] = final_url
        r['real_url'] = final_url
        r['raw_url'] = orig
        r['real_domain'] = extract_domain(final_url)
        r['score'] = calculate_quality_score(r, query)
    return results


def should_skip_url(url, real_domain=''):
    """检查URL是否应该跳过（视频、图片、下载站等）

    优先用已还原的真实域名精确匹配，避免跳转链接导致误判。
    """
    url_lower = url.lower()
    for domain in SKIP_DOMAINS:
        if domain in url_lower:
            return True
    # 基于真实域名的精确匹配（含子域）
    if real_domain:
        for domain in SKIP_DOMAINS:
            if real_domain == domain or real_domain.endswith('.' + domain):
                return True
    return False


def generate_session_id():
    """生成会话ID"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    short_uuid = uuid.uuid4().hex[:8]
    return f"{timestamp}_{short_uuid}"


def get_session_dir(base_dir=None, session_id=None):
    """获取会话目录"""
    if base_dir is None:
        base_dir = DEFAULT_OUTPUT_DIR

    if session_id is None:
        session_id = generate_session_id()

    session_dir = os.path.join(base_dir, session_id)
    os.makedirs(session_dir, exist_ok=True)

    return session_dir, session_id


async def check_captcha_async(page):
    """检测验证码（异步）"""
    indicators = ['wappass.baidu.com', 'captcha', '验证']

    try:
        url = page.url.lower()
        content = await page.content()
        content_lower = content.lower()

        is_captcha = any(i in url for i in indicators) or '百度安全验证' in content

        if is_captcha:
            print("\n检测到验证码！", file=sys.stderr)
            return True
    except Exception:
        pass
    return False


async def search_async(query, limit=50):
    """执行百度搜索（异步）

    Args:
        query: 搜索关键词
        limit: 结果数量

    Returns:
        list: 搜索结果列表
    """
    if not HAS_PLAYWRIGHT:
        print("请安装: pip install playwright && playwright install chromium", file=sys.stderr)
        return []

    playwright, browser = await get_browser_async()
    if not browser:
        print("无法连接Chrome", file=sys.stderr)
        return []

    results = []

    page = None
    try:
        page = await get_page_async(browser, url='https://www.baidu.com', timeout=30000)
        if not page:
            print("无法创建页面", file=sys.stderr)
            return []

        # 检查验证码
        if await check_captcha_async(page):
            print("请在浏览器窗口中完成验证...", file=sys.stderr)
            import asyncio
            for _ in range(60):
                await asyncio.sleep(1)
                if not await check_captcha_async(page):
                    print("验证完成！", file=sys.stderr)
                    break

        # 搜索
        import asyncio
        for pagenum in range(1, (limit + 9) // 10 + 1):
            pn = (pagenum - 1) * 10
            url = f"https://www.baidu.com/s?wd={urllib.parse.quote(query)}&pn={pn}"

            await page.goto(url, timeout=30000, wait_until="domcontentloaded")
            # 等 DOM 而非全部资源（load 要等广告/图片），动态脚本用一个短 sleep 兜底
            await asyncio.sleep(1)

            if await check_captcha_async(page):
                break

            try:
                await page.wait_for_selector('div.result', timeout=10000)
            except Exception:
                continue

            html = await page.content()

            if HAS_BS4:
                soup = BeautifulSoup(html, 'html.parser')
                for item in soup.select('div.result, div.c-container'):
                    title_tag = item.select_one('h3 a')
                    if title_tag:
                        title = title_tag.get_text(strip=True)
                        raw_url = title_tag.get('href', '')

                        # 还原真实地址，供域名跳过/打分使用
                        real_url = resolve_real_url(raw_url)
                        real_domain = extract_domain(real_url)

                        # 过滤广告、推广、视频/图片网站（用真实域名判断）
                        if '广告' not in title and '推广' not in title and not should_skip_url(real_url, real_domain):
                            result = {
                                'title': title,
                                'url': real_url,
                                'raw_url': raw_url,
                                'real_url': real_url,
                                'real_domain': real_domain,
                                'abstract': (item.select_one('.c-abstract') or item).get_text(strip=True)[:300],
                                'score': 1.0
                            }
                            result['score'] = calculate_quality_score(result, query)
                            results.append(result)

            if len(results) >= limit:
                break

    except Exception as e:
        print(f"搜索错误: {e}", file=sys.stderr)
    finally:
        if page:
            await close_page_async(page)
        await close_browser_async(browser, playwright, keep_running=True)

    # 去重
    seen = set()
    unique = []
    for r in results:
        if r['url'] not in seen:
            seen.add(r['url'])
            unique.append(r)

    # 按质量分数排序
    unique.sort(key=lambda x: x.get('score', 1.0), reverse=True)

    return unique[:limit]


def compile_results(query, results, fetched, save_dir, session_id):
    """整理抓取结果，生成最终Markdown报告（调用markdown_writer模块）"""
    return save_search_report(query, results, fetched, save_dir, session_id)


def read_all_md_files(save_dir):
    """读取目录下所有md文件内容"""
    md_contents = {}

    if not save_dir or not os.path.exists(save_dir):
        return md_contents

    for filename in os.listdir(save_dir):
        if filename.endswith('.md') and not filename.startswith('搜索报告') and not filename.startswith('搜索总结') and not filename.startswith('AI分析'):
            filepath = os.path.join(save_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    md_contents[filename] = f.read()
            except Exception as e:
                print(f"读取文件失败 {filename}: {e}", file=sys.stderr)

    return md_contents


def _parse_md_source(filename, content):
    """从抓取生成的 md 文件里解析标题/URL/正文，供 AI 总结使用"""
    title_m = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    title = title_m.group(1).strip() if title_m else filename
    url_m = re.search(r'-\s*\*\*URL\*\*:\s*(\S+)', content)
    url = url_m.group(1).strip() if url_m else ''
    body_m = re.search(r'## 正文内容\s*\n([\s\S]+)$', content)
    body = body_m.group(1).strip() if body_m else content.strip()
    return {'filename': filename, 'title': title, 'url': url, 'content': body}


def try_ai_summary(query, md_contents, save_dir, session_id):
    """尝试用 LLM 生成深度分析。已配置 LLM_API_KEY 才启用；否则返回 None。"""
    if not HAS_AI_SUMMARIZER:
        return None

    try:
        api_key, api_base, model = ai_summarizer.get_api_config()
        if not api_key:
            return None

        contents = [_parse_md_source(name, content) for name, content in md_contents.items()]
        if not contents:
            return None

        summary, err = ai_summarizer.summarize_contents(query, contents, api_key, api_base, model)
        if err or not summary:
            print(f"AI 深度总结失败: {err}", file=sys.stderr)
            return None

        path = os.path.join(save_dir, f"AI分析_{session_id}.md")
        with open(path, 'w', encoding='utf-8') as f:
            f.write(f"# AI 深度分析：{query}\n\n")
            f.write(f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"> 会话ID：{session_id}\n\n")
            f.write(summary)
            f.write("\n\n---\n## 参考来源\n\n")
            for i, c in enumerate(contents, 1):
                f.write(f"{i}. [{c['title']}]({c.get('url', '')})\n")

        print(f"AI 深度分析已保存: {path}", file=sys.stderr)
        return path
    except Exception as e:
        print(f"AI 深度总结失败: {e}", file=sys.stderr)
        return None


def generate_summary(query, results, md_contents, save_dir, session_id):
    """生成搜索结果总结（本地逐条要点）；若配置了 LLM 则额外生成 AI 深度分析"""
    summary_path = save_summary(query, results, md_contents, save_dir, session_id)
    try_ai_summary(query, md_contents, save_dir, session_id)
    return summary_path


async def main_async():
    """异步主函数"""
    parser = argparse.ArgumentParser(description='百度搜索增强版（异步）')
    parser.add_argument('query', nargs='*', help='搜索词')
    parser.add_argument('-n', '--limit', type=int, default=50, help='搜索结果数量 (默认50)')
    parser.add_argument('-t', '--top-percent', type=float, default=35, help='按分数筛选前N%%的结果进行抓取 (默认35%%)')
    parser.add_argument('--min-score', type=float, default=1.0, help='最低分数阈值 (默认1.0)')
    parser.add_argument('-o', '--output', help='保存目录')
    parser.add_argument('--session-id', help='指定会话ID')
    parser.add_argument('-w', '--workers', type=int, default=4, help='抓取并发数')
    parser.add_argument('--json', action='store_true', help='JSON输出')
    parser.add_argument('--no-summarize', action='store_true', help='不生成总结报告')

    args = parser.parse_args()

    if not args.query:
        parser.print_help()
        return

    query = ' '.join(args.query)

    # 单实例并发保护：仅允许一个搜索/抓取实例运行，其余直接拒绝
    # （共享同一个 CDP Chrome，并发会互相干扰页面）
    if not try_acquire_instance_lock():
        print("检测到另一个搜索/抓取实例正在运行，本次请求被拒绝（并发数量限制）。请稍后重试。", file=sys.stderr)
        sys.exit(2)

    # 创建会话目录
    session_dir, session_id = get_session_dir(args.output, args.session_id)
    print(f"搜索: {query}", file=sys.stderr)
    print(f"会话ID: {session_id}", file=sys.stderr)
    print(f"保存目录: {session_dir}", file=sys.stderr)

    # 搜索（异步）——尊重用户传入的 limit，不再强制垫到 50
    limit = max(args.limit, 1)
    results = await search_async(query, limit)
    print(f"找到 {len(results)} 条结果", file=sys.stderr)

    if not results:
        print("未找到搜索结果", file=sys.stderr)
        return

    # 按分数筛选
    top_count = max(1, int(len(results) * args.top_percent / 100))
    filtered_results = [r for r in results if r.get('score', 1.0) >= args.min_score]
    fetch_count = min(top_count, len(filtered_results))
    fetch_count = max(1, fetch_count)

    print(f"筛选: 分数前{args.top_percent}% + 最低{args.min_score}分 = {fetch_count}条", file=sys.stderr)

    # 抓取网页（异步并行）- 过滤掉视频/图片网站
    urls_to_fetch = []
    skipped_urls = []
    for r in results[:fetch_count]:
        if should_skip_url(r.get('url', ''), r.get('real_domain', '')):
            skipped_urls.append(r['url'])
        else:
            urls_to_fetch.append(r['url'])

    if skipped_urls:
        print(f"跳过 {len(skipped_urls)} 个视频/图片/下载网站", file=sys.stderr)

    if not urls_to_fetch:
        print("无有效URL可抓取", file=sys.stderr)
        return

    fetched = await fetch_urls_async(urls_to_fetch, save_dir=session_dir, workers=args.workers)
    success_count = sum(1 for r in fetched if r.get('success'))
    print(f"抓取成功: {success_count}/{len(urls_to_fetch)}", file=sys.stderr)

    # 抓取后用真实 URL/域名回填，纠正打分
    results = backfill_real_urls(results, query, urls_to_fetch, fetched)

    # 用真实域名二次剔除视频/无正文站（此前仅凭跳转链接无法识别）
    removed_by_domain = 0
    kept = []
    for r in results:
        if should_skip_url(r.get('url', ''), r.get('real_domain', '')):
            removed_by_domain += 1
            continue
        kept.append(r)
    if removed_by_domain:
        print(f"按真实域名剔除 {removed_by_domain} 个视频/图片/下载网站", file=sys.stderr)
    results = kept

    # 按回填后的真实分数重排
    if results:
        results.sort(key=lambda x: x.get('score', 1.0), reverse=True)

    # 生成报告
    if success_count > 0:
        compile_results(query, results, fetched, session_dir, session_id)

        if not args.no_summarize:
            md_contents = read_all_md_files(session_dir)
            if md_contents:
                summary_path = generate_summary(query, results, md_contents, session_dir, session_id)
                print(f"\n总结文件: {summary_path}", file=sys.stderr)

    # 输出结果
    if args.json:
        output = {
            'query': query,
            'session_id': session_id,
            'save_dir': session_dir,
            'total_results': len(results),
            'fetched_count': fetch_count,
            'success_count': success_count,
            'results': [
                {
                    'index': i + 1,
                    'title': r['title'],
                    'url': r['url'],
                    'score': r.get('score', 1.0),
                    'abstract': r.get('abstract', '')[:200]
                }
                for i, r in enumerate(results)
            ]
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print("\n" + "=" * 60)
        print(f"搜索结果: {query}")
        print(f"共找到 {len(results)} 条，抓取 {fetch_count} 条，成功 {success_count} 条")
        print("=" * 60)

        for i, r in enumerate(results[:20], 1):
            score = r.get('score', 1.0)
            score_indicator = "★" * min(5, int(score * 2))
            is_fetched = i <= fetch_count
            fetch_mark = "✓" if is_fetched else " "
            print(f"\n{i}. [{fetch_mark}] [{score_indicator}] {r['title']}")
            print(f"   分数: {score:.2f}")
            print(f"   链接: {r['url']}")
            if r.get('abstract'):
                abstract = r['abstract'][:100] + ('...' if len(r['abstract']) > 100 else '')
                print(f"   摘要: {abstract}")

        print("\n" + "=" * 60)
        print(f"会话目录: {session_dir}")
        print("=" * 60)


def main():
    """同步入口"""
    import asyncio
    asyncio.run(main_async())


if __name__ == '__main__':
    # 直接修改原 stdout 的编码，而非新建 wrapper 替换——后者会令旧对象 GC 时关闭同名 buffer。
    # 作为模块被 import 时此块不执行，不影响调用方 stdout。
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    main()