#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
百度搜索脚本 - 增强版
支持大规模搜索、智能分数筛选、内容抓取、AI总结
"""

import sys
import json
import urllib.parse
import re
import io
import random
import argparse
import os
import time
import hashlib
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# 确保 UTF-8 编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

try:
    import requests
except ImportError:
    print(json.dumps({'error': '请安装 requests: pip install requests'}, ensure_ascii=False))
    sys.exit(1)

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False


# ============ 工具函数 ============

def get_display_path(path):
    """将路径转换为适合当前系统的显示格式"""
    if not path:
        return path

    # Windows 系统
    if sys.platform == 'win32':
        # 处理 Git Bash 的 /tmp 映射
        if path.startswith('/tmp/'):
            import tempfile
            # 获取 Windows 临时目录
            win_temp = tempfile.gettempdir()
            path = path.replace('/tmp/', win_temp.replace('\\', '/') + '/')

        # 将 Unix 风格路径转换为 Windows 风格
        path = path.replace('/', '\\')

    return path


# ============ 配置 ============

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
]

# 质量评分配置
QUALITY_SITES = {
    # 技术权威
    'github.com': 2.5,
    'stackoverflow.com': 2.3,
    'python.org': 2.5,
    'pypi.org': 2.2,
    'npmjs.com': 2.2,
    'readthedocs.io': 2.3,
    'mdn.mozilla.org': 2.3,
    'dev.mysql.com': 2.3,
    'docs.microsoft.com': 2.2,
    'openai.com': 2.3,
    'anthropic.com': 2.3,
    # 中文技术
    'runoob.com': 1.8,
    'csdn.net': 1.4,
    'juejin.cn': 1.5,
    'zhihu.com': 1.3,
    'segmentfault.com': 1.5,
    'cnblogs.com': 1.3,
    'jianshu.com': 1.2,
    'oschina.net': 1.5,
    'infoq.cn': 1.6,
    # 官方/权威
    'edu.cn': 1.8,
    'gov.cn': 1.8,
    'wikipedia.org': 1.7,
    'baike.baidu.com': 1.2,
    'zh.wikipedia.org': 1.7,
    # 新闻/资讯
    'sina.com.cn': 1.2,
    'sohu.com': 1.1,
    '163.com': 1.1,
    'qq.com': 1.1,
    'eastmoney.com': 1.4,
    # 企业官网
    'suzhoubank.com': 2.0,
}

# 低质量站点降权
LOW_QUALITY_SITES = {
    'wenku.baidu.com': 0.4,
    'zhidao.baidu.com': 0.5,
    'tieba.baidu.com': 0.3,
    'baike.sogou.com': 0.5,
    'wenda.so.com': 0.5,
}


# ============ 搜索函数 ============

def calculate_quality_score(title, url, abstract):
    """计算结果质量分数"""
    score = 1.0

    # 高质量站点加分
    for site, bonus in QUALITY_SITES.items():
        if site in url:
            score *= bonus
            break

    # 低质量站点降权
    for site, penalty in LOW_QUALITY_SITES.items():
        if site in url:
            score *= penalty
            break

    # 标题相关性加分
    if abstract and len(abstract) > 50:
        score *= 1.1  # 有摘要且内容丰富

    return round(score, 2)


def search_single_page(query, page_num):
    """搜索单页结果"""
    encoded_query = urllib.parse.quote(query)
    # 百度每页约10条，pn=0, 10, 20, ...
    pn = (page_num - 1) * 10
    url = f"https://www.baidu.com/s?wd={encoded_query}&ie=utf-8&pn={pn}&rn=50"

    headers = {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Referer': 'https://www.baidu.com/',
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.encoding is None or response.encoding.lower() == 'iso-8859-1':
            response.encoding = 'utf-8'

        html = response.text
        results = []

        h3_matches = re.findall(r'<h3[^>]*>(.*?)</h3>', html, re.DOTALL)

        for h3 in h3_matches:
            link_match = re.search(r'href="(https?://(?:www\.)?baidu\.com/link\?url=[^"]+)"', h3)
            if not link_match:
                continue

            result_url = link_match.group(1)
            title = re.sub(r'<[^>]+>', '', h3)
            title = re.sub(r'\s+', ' ', title).strip()

            if len(title) < 2:
                continue

            if any(kw in title.lower() for kw in ['推广', '广告', 'sponsored', '企业认证']):
                continue

            results.append({
                'title': title,
                'url': result_url,
                'abstract': ''
            })

        # 提取摘要
        abstract_pattern = r'<div[^>]*class="c-abstract[^"]*"[^>]*>(.*?)</div>'
        abstract_matches = re.findall(abstract_pattern, html, re.DOTALL)

        for i, abstract in enumerate(abstract_matches):
            if i < len(results):
                abstract_text = re.sub(r'<[^>]+>', '', abstract)
                abstract_text = re.sub(r'\s+', ' ', abstract_text).strip()
                results[i]['abstract'] = abstract_text[:300]

        return results

    except Exception as e:
        return {'error': str(e)}


def search(query, total_results=100):
    """执行大规模百度搜索"""
    # 计算需要的页数（每页约10条有效结果）
    pages_needed = (total_results // 8) + 1

    all_results = []

    for page in range(1, pages_needed + 1):
        results = search_single_page(query, page)
        if isinstance(results, dict) and 'error' in results:
            continue
        all_results.extend(results)

        # 去重
        seen_urls = set()
        unique_results = []
        for r in all_results:
            if r['url'] not in seen_urls:
                seen_urls.add(r['url'])
                unique_results.append(r)
        all_results = unique_results

        if len(all_results) >= total_results:
            break

        time.sleep(0.5)  # 避免请求过快

    # 计算质量分数
    for r in all_results:
        r['score'] = calculate_quality_score(r['title'], r['url'], r.get('abstract', ''))

    return all_results[:total_results]


def filter_by_score(results, top_percent=20, min_score=1.0):
    """按分数筛选结果"""
    if not results:
        return [], 0

    # 按分数排序
    sorted_results = sorted(results, key=lambda x: x.get('score', 1), reverse=True)

    # 计算阈值
    scores = [r['score'] for r in sorted_results]
    avg_score = sum(scores) / len(scores)
    threshold = max(min_score, avg_score)

    # 筛选
    filtered = [r for r in sorted_results if r['score'] >= threshold]

    # 或者取前 top_percent
    top_count = max(1, int(len(sorted_results) * top_percent / 100))
    if len(filtered) < top_count:
        filtered = sorted_results[:top_count]

    return filtered, threshold


# ============ 网页抓取函数 ============

def fetch_url_content(url, timeout=15):
    """抓取网页内容"""
    headers = {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    }

    try:
        response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)

        # 处理编码
        if response.encoding is None or response.encoding.lower() == 'iso-8859-1':
            content_type = response.headers.get('content-type', '')
            if 'charset=' in content_type:
                response.encoding = content_type.split('charset=')[-1].split(';')[0].strip()
            else:
                response.encoding = 'utf-8'

        html = response.text

        # 解析内容
        if HAS_BS4:
            soup = BeautifulSoup(html, 'html.parser')

            # 移除无关元素
            for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'iframe', 'noscript']):
                tag.decompose()

            # 提取正文
            # 尝试常见的内容容器
            content_selectors = [
                'article', 'main', '.content', '.article', '.post', '.entry',
                '#content', '#article', '.main-content', '.post-content',
                'body'
            ]

            content = None
            for selector in content_selectors:
                elements = soup.select(selector)
                if elements:
                    content = elements[0]
                    break

            if content:
                text = content.get_text(separator='\n', strip=True)
            else:
                text = soup.get_text(separator='\n', strip=True)

            # 提取标题
            title_tag = soup.find('title')
            title = title_tag.get_text(strip=True) if title_tag else ''

            # 提取 meta description
            desc_tag = soup.find('meta', attrs={'name': 'description'})
            description = desc_tag.get('content', '') if desc_tag else ''

        else:
            # 简单正则提取
            title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
            title = title_match.group(1).strip() if title_match else ''

            # 移除脚本和样式
            text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
            description = ''

        # 清理文本
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        text = '\n'.join(lines)

        # 截断过长内容
        if len(text) > 10000:
            text = text[:10000] + '\n... (内容已截断)'

        return {
            'success': True,
            'title': title,
            'description': description,
            'content': text,
            'url': response.url,  # 最终URL（可能有重定向）
            'length': len(text)
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'url': url
        }


def resolve_baidu_link(baidu_url, timeout=10):
    """解析百度跳转链接，获取真实URL"""
    headers = {
        'User-Agent': random.choice(USER_AGENTS),
    }

    try:
        # 发送 HEAD 请求获取重定向后的 URL
        response = requests.head(baidu_url, headers=headers, timeout=timeout, allow_redirects=True)
        return response.url
    except:
        pass

    try:
        # 如果 HEAD 失败，尝试 GET
        response = requests.get(baidu_url, headers=headers, timeout=timeout, allow_redirects=True, stream=True)
        return response.url
    except:
        return baidu_url


def fetch_multiple_urls(urls, max_workers=5, save_dir=None):
    """批量抓取多个URL"""
    results = []

    def fetch_one(url_info):
        idx, baidu_url, title = url_info

        # 解析真实URL
        real_url = resolve_baidu_link(baidu_url)

        # 抓取内容
        content_result = fetch_url_content(real_url)
        content_result['original_url'] = baidu_url
        content_result['search_title'] = title
        content_result['real_url'] = real_url

        # 保存到文件
        if save_dir and content_result['success']:
            os.makedirs(save_dir, exist_ok=True)
            url_hash = hashlib.md5(real_url.encode()).hexdigest()[:8]
            filename = f"{url_hash}.txt"
            filepath = os.path.join(save_dir, filename)

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"标题: {content_result['title']}\n")
                f.write(f"URL: {real_url}\n")
                f.write(f"抓取时间: {datetime.now().isoformat()}\n")
                f.write("=" * 50 + "\n\n")
                f.write(content_result['content'])

            # 返回适合当前系统的路径格式
            content_result['local_file'] = get_display_path(filepath)

        return content_result

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        url_list = [(i, r['url'], r['title']) for i, r in enumerate(urls)]
        futures = {executor.submit(fetch_one, url_info): url_info for url_info in url_list}

        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                results.append({
                    'success': False,
                    'error': str(e)
                })

    return results


# ============ AI 总结函数 ============

def summarize_content(query, contents, api_key=None, api_base=None, model=None):
    """使用 LLM 总结内容"""

    # 获取 API 配置
    api_key = api_key or os.environ.get('LLM_API_KEY') or os.environ.get('OPENAI_API_KEY')
    api_base = api_base or os.environ.get('LLM_API_BASE') or os.environ.get('OPENAI_API_BASE') or 'https://api.openai.com/v1'
    model = model or os.environ.get('LLM_MODEL') or os.environ.get('OPENAI_MODEL') or 'gpt-3.5-turbo'

    if not api_key:
        return {
            'success': False,
            'error': '未配置 LLM API。请设置环境变量 LLM_API_KEY 和 LLM_API_BASE'
        }

    # 构建内容摘要
    content_texts = []
    for i, c in enumerate(contents[:10]):  # 最多处理10条
        if c.get('success') and c.get('content'):
            text = c['content'][:2000]  # 每条最多2000字
            content_texts.append(f"【来源 {i+1}】{c['title']}\nURL: {c['real_url']}\n内容:\n{text}\n")

    combined_content = "\n---\n".join(content_texts)

    prompt = f"""你是一个专业的信息分析助手。用户搜索了「{query}」，以下是抓取到的网页内容。

请完成以下任务：
1. 总结这些内容的核心信息（200-500字）
2. 列出关键发现（3-5条）
3. 如果有矛盾或不一致的地方，请指出
4. 给出参考建议（如适用）

网页内容：
{combined_content}

请按以下格式输出：

## 内容总结
[总结内容]

## 关键发现
1. [发现1]
2. [发现2]
...

## 参考资料
- [标题1](URL1)
- [标题2](URL2)
...
"""

    try:
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }

        data = {
            'model': model,
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0.5,
            'max_tokens': 2000
        }

        response = requests.post(
            f'{api_base.rstrip("/")}/chat/completions',
            headers=headers,
            json=data,
            timeout=60
        )

        if response.status_code != 200:
            return {
                'success': False,
                'error': f'LLM API 调用失败: {response.status_code}'
            }

        content = response.json()['choices'][0]['message']['content']

        return {
            'success': True,
            'summary': content,
            'model': model,
            'sources_count': len(contents)
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


# ============ 主函数 ============

def main():
    parser = argparse.ArgumentParser(description='百度搜索 - 增强版')
    parser.add_argument('query', nargs='+', help='搜索关键词')
    parser.add_argument('-n', '--limit', type=int, default=100, help='搜索结果数量 (默认100)')
    parser.add_argument('-t', '--top-percent', type=int, default=20, help='按分数筛选前N%% (默认20)')
    parser.add_argument('--min-score', type=float, default=1.0, help='最低分数阈值 (默认1.0)')
    parser.add_argument('-f', '--fetch', type=int, default=0, help='抓取前N个结果的内容 (0=不抓取)')
    parser.add_argument('-s', '--summarize', action='store_true', help='调用AI总结内容')
    parser.add_argument('-o', '--output', type=str, default=None, help='保存内容的目录路径')
    parser.add_argument('--max-workers', type=int, default=5, help='并发抓取数 (默认5)')
    parser.add_argument('--json', action='store_true', help='输出JSON格式')

    args = parser.parse_args()
    query = ' '.join(args.query)

    output = {
        'query': query,
        'timestamp': datetime.now().isoformat()
    }

    # 1. 搜索
    print(f"正在搜索: {query}", file=sys.stderr)
    all_results = search(query, total_results=args.limit)
    output['total_found'] = len(all_results)

    # 2. 分数筛选
    filtered_results, threshold = filter_by_score(all_results, args.top_percent, args.min_score)
    output['score_threshold'] = threshold
    output['filtered_count'] = len(filtered_results)
    output['filtered_results'] = filtered_results

    print(f"找到 {len(all_results)} 条结果，筛选后 {len(filtered_results)} 条 (阈值: {threshold:.2f})", file=sys.stderr)

    # 3. 抓取内容
    if args.fetch > 0 and filtered_results:
        fetch_count = min(args.fetch, len(filtered_results))
        print(f"正在抓取前 {fetch_count} 条结果...", file=sys.stderr)

        save_dir = args.output
        if save_dir:
            save_dir = os.path.expanduser(save_dir)
            os.makedirs(save_dir, exist_ok=True)

        fetch_results = fetch_multiple_urls(
            filtered_results[:fetch_count],
            max_workers=args.max_workers,
            save_dir=save_dir
        )
        output['fetched_results'] = fetch_results
        output['save_dir'] = get_display_path(save_dir) if save_dir else None

        success_count = sum(1 for r in fetch_results if r.get('success'))
        print(f"成功抓取 {success_count}/{fetch_count} 条", file=sys.stderr)

        # 显示保存位置
        if save_dir and success_count > 0:
            print(f"文件保存到: {get_display_path(save_dir)}", file=sys.stderr)

        # 4. AI 总结
        if args.summarize and fetch_results:
            print("正在生成总结...", file=sys.stderr)
            summary_result = summarize_content(query, fetch_results)
            output['summary'] = summary_result

            if summary_result['success']:
                if not args.json:
                    print("\n" + "=" * 60)
                    print(summary_result['summary'])
                    print("=" * 60)
            else:
                print(f"总结失败: {summary_result['error']}", file=sys.stderr)

    # 输出结果
    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        # 友好的文本输出
        print("\n" + "=" * 60)
        print(f"搜索: {query}")
        print(f"共找到 {output['total_found']} 条，筛选后 {output['filtered_count']} 条")
        print("=" * 60)

        for i, r in enumerate(filtered_results[:20], 1):
            print(f"\n{i}. [{r['score']:.1f}] {r['title']}")
            print(f"   {r['url']}")
            if r.get('abstract'):
                print(f"   {r['abstract'][:100]}...")


if __name__ == '__main__':
    main()