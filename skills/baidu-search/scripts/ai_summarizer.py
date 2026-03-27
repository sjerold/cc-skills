#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 内容总结脚本
读取本地文件或直接输入文本，调用 LLM 生成总结
"""

import sys
import json
import io
import argparse
import os
import re
import glob

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

try:
    import requests
except ImportError:
    print(json.dumps({'error': '请安装 requests: pip install requests'}, ensure_ascii=False))
    sys.exit(1)


def get_api_config():
    """获取 LLM API 配置"""
    api_key = os.environ.get('LLM_API_KEY') or os.environ.get('OPENAI_API_KEY') or os.environ.get('ANTHROPIC_API_KEY')
    api_base = os.environ.get('LLM_API_BASE') or os.environ.get('OPENAI_API_BASE') or 'https://api.openai.com/v1'
    model = os.environ.get('LLM_MODEL') or os.environ.get('OPENAI_MODEL') or 'gpt-3.5-turbo'

    return api_key, api_base, model


def read_file(filepath):
    """读取文件内容"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return None, str(e)


def read_directory(dir_path, pattern='*.txt'):
    """读取目录下的所有文件"""
    files = glob.glob(os.path.join(dir_path, pattern))
    contents = []

    for filepath in files:
        content = read_file(filepath)
        if content:
            # 提取文件中的元信息
            title = ''
            url = ''
            lines = content.split('\n')
            for line in lines[:10]:
                if line.startswith('标题:'):
                    title = line.replace('标题:', '').strip()
                elif line.startswith('URL:'):
                    url = line.replace('URL:', '').strip()

            contents.append({
                'filepath': filepath,
                'filename': os.path.basename(filepath),
                'title': title or os.path.basename(filepath),
                'url': url,
                'content': content,
                'length': len(content)
            })

    return contents


def call_llm(prompt, api_key, api_base, model, temperature=0.5, max_tokens=2000):
    """调用 LLM API"""
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }

    data = {
        'model': model,
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': temperature,
        'max_tokens': max_tokens
    }

    try:
        response = requests.post(
            f'{api_base.rstrip("/")}/chat/completions',
            headers=headers,
            json=data,
            timeout=120
        )

        if response.status_code != 200:
            return None, f'API 调用失败: {response.status_code} - {response.text}'

        result = response.json()
        return result['choices'][0]['message']['content'], None

    except Exception as e:
        return None, str(e)


def summarize_contents(query, contents, api_key, api_base, model, style='comprehensive'):
    """总结多个内容"""

    # 构建内容文本
    content_parts = []
    total_length = 0
    max_length = 15000  # 控制总输入长度

    for i, c in enumerate(contents):
        if total_length >= max_length:
            break

        # 截取部分内容
        text = c['content'][:3000]
        total_length += len(text)

        content_parts.append(f"""【来源 {i+1}】{c['title']}
文件: {c['filename']}
URL: {c.get('url', 'N/A')}
---
{text}
""")

    combined = "\n".join(content_parts)

    # 根据风格选择提示词模板
    if style == 'comprehensive':
        prompt = f"""你是一个专业的信息分析助手。用户搜索了「{query}」，以下是抓取到的网页内容。

请完成以下任务：
1. **内容总结**: 总结这些内容的核心信息（200-500字）
2. **关键发现**: 列出3-5个最重要的发现
3. **观点对比**: 如果有不同观点，请对比分析
4. **建议**: 基于信息给出实用建议（如适用）

网页内容：
{combined}

请用 Markdown 格式输出，包含参考资料链接。
"""
    elif style == 'brief':
        prompt = f"""用户搜索「{query}」，请用100-200字总结以下内容的核心要点：

{combined}

简洁输出，不要多余格式。
"""
    elif style == 'extract':
        prompt = f"""用户搜索「{query}」，请从以下内容中提取关键信息：

{combined}

请提取：
- 主要观点（3-5条）
- 重要数据/事实
- 相关链接

用简洁的列表格式输出。
"""
    else:
        prompt = f"""请总结以下内容（用户搜索: {query}）：

{combined}
"""

    return call_llm(prompt, api_key, api_base, model)


def analyze_topic(query, contents, api_key, api_base, model):
    """深度分析主题"""

    # 先生成总结
    summary, err = summarize_contents(query, contents, api_key, api_base, model, 'comprehensive')
    if err:
        return None, err

    # 再生成延伸问题
    questions_prompt = f"""基于用户对「{query}」的搜索结果，请生成3-5个用户可能感兴趣的延伸问题：
{summary}
"""
    questions, _ = call_llm(questions_prompt, api_key, api_base, model, temperature=0.7)

    return {
        'summary': summary,
        'followup_questions': questions
    }, None


def main():
    parser = argparse.ArgumentParser(description='AI 内容总结工具')
    parser.add_argument('query', help='搜索关键词/主题')
    parser.add_argument('-i', '--input', type=str, help='输入文件或目录路径')
    parser.add_argument('-t', '--text', type=str, help='直接输入文本内容')
    parser.add_argument('-s', '--style', choices=['comprehensive', 'brief', 'extract'], default='comprehensive',
                        help='总结风格: comprehensive(全面), brief(简洁), extract(提取)')
    parser.add_argument('--analyze', action='store_true', help='深度分析模式')
    parser.add_argument('-o', '--output', type=str, help='输出文件路径')
    parser.add_argument('--json', action='store_true', help='输出JSON格式')

    args = parser.parse_args()

    # 检查 API 配置
    api_key, api_base, model = get_api_config()
    if not api_key:
        print(json.dumps({'error': '未配置 LLM API。请设置环境变量 LLM_API_KEY 和 LLM_API_BASE'}, ensure_ascii=False))
        sys.exit(1)

    # 获取内容
    contents = []

    if args.input:
        input_path = os.path.expanduser(args.input)
        if os.path.isdir(input_path):
            contents = read_directory(input_path)
        elif os.path.isfile(input_path):
            content = read_file(input_path)
            if content:
                contents = [{
                    'filepath': input_path,
                    'filename': os.path.basename(input_path),
                    'title': os.path.basename(input_path),
                    'url': '',
                    'content': content,
                    'length': len(content)
                }]
    elif args.text:
        contents = [{
            'filepath': '',
            'filename': 'direct_input',
            'title': '直接输入',
            'url': '',
            'content': args.text,
            'length': len(args.text)
        }]
    else:
        print(json.dumps({'error': '请指定输入文件(-i)或直接输入文本(-t)'}, ensure_ascii=False))
        sys.exit(1)

    if not contents:
        print(json.dumps({'error': '未能读取到任何内容'}, ensure_ascii=False))
        sys.exit(1)

    print(f"已读取 {len(contents)} 个文件，共 {sum(c['length'] for c in contents)} 字符", file=sys.stderr)

    # 生成总结
    if args.analyze:
        result, err = analyze_topic(args.query, contents, api_key, api_base, model)
    else:
        summary, err = summarize_contents(args.query, contents, api_key, api_base, model, args.style)
        result = {'summary': summary}

    if err:
        print(json.dumps({'error': err}, ensure_ascii=False))
        sys.exit(1)

    # 添加来源信息
    result['sources'] = [{
        'title': c['title'],
        'url': c.get('url', ''),
        'file': c['filepath']
    } for c in contents]

    result['model'] = model
    result['query'] = args.query

    # 输出
    if args.output:
        output_path = os.path.expanduser(args.output)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"# {args.query} - 内容总结\n\n")
            f.write(result.get('summary', ''))
            if result.get('followup_questions'):
                f.write("\n\n## 延伸问题\n")
                f.write(result['followup_questions'])
            f.write("\n\n---\n")
            f.write(f"生成时间: {__import__('datetime').datetime.now().isoformat()}\n")
            f.write(f"模型: {model}\n")
        result['output_file'] = output_path
        print(f"总结已保存到: {output_path}", file=sys.stderr)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("\n" + "=" * 60)
        print(result.get('summary', ''))
        if result.get('followup_questions'):
            print("\n" + "=" * 60)
            print("延伸问题:")
            print(result['followup_questions'])
        print("=" * 60)


if __name__ == '__main__':
    main()