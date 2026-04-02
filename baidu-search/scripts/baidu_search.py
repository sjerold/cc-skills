#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
百度搜索脚本 - 使用common模块统一Chrome管理

改动：
- 使用common/chrome_manager连接现有Chrome（端口9222）
- 使用common/web_fetcher抓取网页
- 在现有浏览器开新tab，复用登录状态
"""

import sys
import os
import json
import io
import argparse
import time
import uuid
import urllib.parse
from datetime import datetime

# 添加common模块路径
COMMON_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'common', 'scripts')
sys.path.insert(0, COMMON_PATH)

# 确保 UTF-8 编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 导入common模块
try:
    from chrome_manager import get_browser, get_page, close_browser, is_chrome_debug_running, start_debug_chrome
    HAS_PLAYWRIGHT = True
except ImportError as e:
    print(f"无法导入chrome_manager: {e}", file=sys.stderr)
    HAS_PLAYWRIGHT = False

try:
    from web_fetcher import fetch_urls, save_result_to_markdown
except ImportError as e:
    print(f"无法导入web_fetcher: {e}", file=sys.stderr)

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False


# ============ 配置 ============

DEFAULT_OUTPUT_DIR = os.path.join(os.path.expanduser('~'), 'Downloads', 'baidu_search')


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


def check_captcha(page):
    """检测验证码"""
    indicators = ['wappass.baidu.com', 'captcha', '验证']

    try:
        url = page.url.lower()
        content = page.content().lower()

        is_captcha = any(i in url for i in indicators) or '百度安全验证' in content

        if is_captcha:
            print("\n检测到验证码！", file=sys.stderr)
            return True
    except:
        pass
    return False


def calculate_quality_score(result):
    """根据URL和标题计算质量分数

    评分规则：
    - 官方文档/开源项目: python.org, github.com, gitee.com 等 × 2.5
    - 技术社区: stackoverflow, csdn, juejin, zhihu 等 × 1.4~2.3
    - 官方机构: edu.cn, gov.cn × 1.8
    - 企业官网: 主要企业域名 × 2.0
    - 新闻媒体: 主流新闻网站 × 1.5
    - 低质量: 贴吧、论坛灌水等 × 0.3~0.5
    """
    url = result.get('url', '').lower()
    title = result.get('title', '').lower()

    base_score = 1.0

    # 官方文档/开源项目 (× 2.5)
    official_patterns = ['python.org', 'github.com', 'gitee.com', 'pypi.org',
                        'readthedocs', 'docs.', 'developer.', 'documentation']
    for pattern in official_patterns:
        if pattern in url:
            return base_score * 2.5

    # 官方机构 (× 1.8)
    gov_patterns = ['.gov.cn', '.edu.cn', 'gov.cn', 'edu.cn']
    for pattern in gov_patterns:
        if pattern in url:
            return base_score * 1.8

    # 技术社区 (× 1.4~2.3)
    tech_community = {
        'stackoverflow.com': 2.3,
        'csdn.net': 1.8,
        'juejin.cn': 1.9,
        'zhihu.com': 1.6,
        'segmentfault.com': 1.8,
        'infoq.cn': 2.0,
        'jb51.net': 1.4,
        'w3cschool': 1.7,
        'runoob.com': 1.7,
    }
    for domain, multiplier in tech_community.items():
        if domain in url:
            return base_score * multiplier

    # 企业官网 (× 2.0)
    enterprise_patterns = ['.com.cn', '官方网站', '官网']
    for pattern in enterprise_patterns:
        if pattern in url or pattern in title:
            return base_score * 2.0

    # 新闻媒体 (× 1.5)
    news_patterns = ['news.', 'xinwen', 'sina.com', 'qq.com', 'sohu.com',
                     '163.com', 'ifeng.com', 'people.com.cn', 'xinhua']
    for pattern in news_patterns:
        if pattern in url:
            return base_score * 1.5

    # 低质量内容 (× 0.3~0.5)
    low_quality = ['tieba.baidu.com', 'forum', 'bbs', '贴吧', '灌水']
    for pattern in low_quality:
        if pattern in url or pattern in title:
            return base_score * 0.3

    return base_score


def search(query, limit=50):
    """执行百度搜索

    Args:
        query: 搜索关键词
        limit: 结果数量
    """
    if not HAS_PLAYWRIGHT:
        print("请安装: pip install playwright", file=sys.stderr)
        return []

    # 使用common模块连接Chrome
    browser = get_browser()
    if not browser:
        print("无法连接Chrome", file=sys.stderr)
        return []

    results = []

    page = None
    try:
        # 创建新页面（在现有浏览器开新tab）
        page = get_page(browser, url='https://www.baidu.com', timeout=30000)
        if not page:
            print("无法创建页面", file=sys.stderr)
            return []

        # 检查验证码
        if check_captcha(page):
            print("请在浏览器窗口中完成验证...", file=sys.stderr)
            # 等待用户处理验证码
            for _ in range(60):
                time.sleep(1)
                if not check_captcha(page):
                    print("验证完成！", file=sys.stderr)
                    break

        # 搜索
        for pagenum in range(1, (limit // 10) + 2):
            pn = (pagenum - 1) * 10
            url = f"https://www.baidu.com/s?wd={urllib.parse.quote(query)}&pn={pn}"

            page.goto(url, timeout=30000)
            time.sleep(2)

            if check_captcha(page):
                break

            try:
                page.wait_for_selector('div.result', timeout=10000)
            except:
                continue

            html = page.content()

            if HAS_BS4:
                soup = BeautifulSoup(html, 'html.parser')
                for item in soup.select('div.result, div.c-container'):
                    title_tag = item.select_one('h3 a')
                    if title_tag:
                        title = title_tag.get_text(strip=True)
                        if '广告' not in title and '推广' not in title:
                            result = {
                                'title': title,
                                'url': title_tag.get('href', ''),
                                'abstract': (item.select_one('.c-abstract') or item).get_text(strip=True)[:300],
                                'score': 1.0
                            }
                            result['score'] = calculate_quality_score(result)
                            results.append(result)

            if len(results) >= limit:
                break

    except Exception as e:
        print(f"搜索错误: {e}", file=sys.stderr)
    finally:
        # 关闭页面
        if page:
            try:
                page.close()
            except:
                pass
        # 断开连接，保持Chrome运行
        close_browser(browser, keep_running=True)

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
    """整理抓取结果，生成最终Markdown报告"""
    if not save_dir:
        return None

    os.makedirs(save_dir, exist_ok=True)
    report_path = os.path.join(save_dir, f"搜索报告_{session_id}.md")

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"# 搜索报告：{query}\n\n")
        f.write(f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"> 会话ID：{session_id}\n\n")

        f.write("## 搜索概况\n\n")
        f.write(f"- **搜索关键词**: {query}\n")
        f.write(f"- **搜索结果数**: {len(results)} 条\n")
        fetched_success = sum(1 for r in fetched if r.get('success'))
        f.write(f"- **抓取成功数**: {fetched_success}/{len(fetched)} 条\n\n")

        f.write("## 参考链接\n\n")
        f.write("| 序号 | 标题 | URL | 质量分数 |\n")
        f.write("|------|------|-----|----------|\n")
        for i, r in enumerate(results[:30], 1):
            title = r.get('title', 'N/A')[:40]
            url = r.get('url', '')
            score = r.get('score', 1.0)
            f.write(f"| {i} | {title} | [链接]({url}) | {score:.2f} |\n")
        f.write("\n")

        f.write("## 抓取内容摘要\n\n")
        for i, r in enumerate(fetched, 1):
            if r.get('success'):
                title = r.get('title', '无标题')
                url = r.get('url', '')
                content_len = r.get('length', 0)
                fetch_type = r.get('fetch_type', 'unknown')
                filepath = r.get('file', '')

                f.write(f"### {i}. {title}\n\n")
                f.write(f"- **URL**: {url}\n")
                f.write(f"- **内容长度**: {content_len} 字符\n")
                f.write(f"- **抓取方式**: {fetch_type}\n")
                if filepath:
                    f.write(f"- **本地文件**: `{os.path.basename(filepath)}`\n")
                f.write("\n")

                content = r.get('content', '')
                if content:
                    preview = content[:500]
                    if len(content) > 500:
                        preview += '...'
                    f.write("**内容预览**:\n\n")
                    f.write("```\n")
                    f.write(preview)
                    f.write("\n```\n\n")

                f.write("---\n\n")

    print(f"\n报告已生成: {report_path}", file=sys.stderr)
    return report_path


def read_all_md_files(save_dir):
    """读取目录下所有md文件内容"""
    md_contents = {}

    if not save_dir or not os.path.exists(save_dir):
        return md_contents

    for filename in os.listdir(save_dir):
        if filename.endswith('.md') and not filename.startswith('搜索报告') and not filename.startswith('搜索总结'):
            filepath = os.path.join(save_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    md_contents[filename] = f.read()
            except Exception as e:
                print(f"读取文件失败 {filename}: {e}", file=sys.stderr)

    return md_contents


def generate_summary(query, results, md_contents, save_dir, session_id):
    """生成搜索结果总结"""
    summary_path = os.path.join(save_dir, f"搜索总结_{session_id}.md")

    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write(f"# 搜索总结：{query}\n\n")
        f.write(f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"> 会话ID：{session_id}\n\n")

        f.write("## 统计信息\n\n")
        f.write(f"- **搜索结果**: {len(results)} 条\n")
        f.write(f"- **抓取文件**: {len(md_contents)} 个\n")

        total_length = sum(len(content) for content in md_contents.values())
        f.write(f"- **总内容量**: {total_length:,} 字符\n\n")

        f.write("## 参考来源\n\n")
        for i, (filename, content) in enumerate(md_contents.items(), 1):
            import re
            title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            title = title_match.group(1) if title_match else filename
            f.write(f"{i}. {title} (`{filename}`)\n")
        f.write("\n")

        f.write("## 整合内容\n\n")
        f.write("---\n\n")

        for i, (filename, content) in enumerate(md_contents.items(), 1):
            import re
            title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            title = title_match.group(1) if title_match else filename

            f.write(f"### 来源 {i}: {title}\n\n")

            content_match = re.search(r'## 正文内容\s*\n([\s\S]+)$', content)
            if content_match:
                body = content_match.group(1).strip()
                if len(body) > 3000:
                    body = body[:3000] + '\n\n... (内容已截断)'
                f.write(body)
            else:
                f.write(content[:3000])

            f.write("\n\n---\n\n")

    print(f"总结已生成: {summary_path}", file=sys.stderr)
    return summary_path


def main():
    parser = argparse.ArgumentParser(description='百度搜索增强版')
    parser.add_argument('query', nargs='*', help='搜索词')
    parser.add_argument('-n', '--limit', type=int, default=20, help='搜索结果数量 (默认20)')
    parser.add_argument('-t', '--top-percent', type=float, default=35, help='按分数筛选前N%%的结果进行抓取 (默认35%%)')
    parser.add_argument('--min-score', type=float, default=1.0, help='最低分数阈值 (默认1.0)')
    parser.add_argument('-o', '--output', help='保存目录 (默认 ~/Downloads/baidu_search/<session_id>)')
    parser.add_argument('--session-id', help='指定会话ID')
    parser.add_argument('--json', action='store_true', help='JSON输出')
    parser.add_argument('--no-summarize', action='store_true', help='不生成总结报告')

    args = parser.parse_args()

    # 检查是否有搜索词
    if not args.query:
        parser.print_help()
        return

    query = ' '.join(args.query)

    # 创建会话目录
    session_dir, session_id = get_session_dir(args.output, args.session_id)
    print(f"搜索: {query}", file=sys.stderr)
    print(f"会话ID: {session_id}", file=sys.stderr)
    print(f"保存目录: {session_dir}", file=sys.stderr)

    # 搜索
    limit = max(args.limit, 20)  # 最小搜索数量 20
    results = search(query, limit)
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

    # 抓取网页（使用common模块）
    urls = [r['url'] for r in results[:fetch_count]]
    fetched = fetch_urls(urls, save_dir=session_dir)
    success_count = sum(1 for r in fetched if r.get('success'))
    print(f"抓取成功: {success_count}/{len(urls)}", file=sys.stderr)

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


if __name__ == '__main__':
    main()