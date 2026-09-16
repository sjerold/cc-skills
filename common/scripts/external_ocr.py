"""
外部 LLM 图片识别脚本（支持批次处理）

通过 API 调用 kimi/qwen 模型识别图片，支持一次处理多张图片

用法:
    python external_ocr.py --images <图片1> <图片2> [--model <模型名>] [--token <API Key>]

参数:
    --images 图片路径（可传多个，最多3张）
    --model  模型名称（默认 xopkimik26，或通过环境变量 SP_MODEL）
    --token  API Token（或通过环境变量 SP_TOKEN）

返回:
    每张图片的识别结果，格式：
    === <图片名> ===
    [纯文字] 或 [混合] 或 [纯图形]
    OCR 文字内容...
    [需要原图引用]  (混合/纯图形类)
"""

import os
import sys
import base64
import json
import urllib.request
import urllib.error
import concurrent.futures

# Windows 下 sys.stdout 默认编码为 gbk，print 中文（重定向到文件时）会写成 GBK 字节，
# 被 UTF-8 读取即乱码。强制 stdout/stderr 用 UTF-8，保证 skill 产出的 markdown 可读。
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

# 默认提示词模板（内置，无需每次传入）
DEFAULT_PROMPT = """请识别这张图片，并按以下准则处理：

【图片来源】docx 文档中的截图/扫描件
【处理方式】
1. 判断图片类型：
   - 纯文字类：直接OCR识别所有文字，按从上到下、从左到右顺序输出
   - 混合类（文字+流程图）：OCR识别文字，最后输出[需要原图引用]
   - 纯图形类：返回[纯图形] + 图片描述

2. 图片分类二次确认：
   - 图形占比>50%才确认为含图形
   - 以文字/表格为主、只有少量装饰图标→归类为纯文字类

3. OCR跳过：页码(1,12,-3-)、版本号(V01xxx)、分隔线(---)、罗马数字(I,II,III)

【输出格式】
第一行：[纯文字] 或 [混合] 或 [纯图形]
第二行起：识别内容（混合类末尾加[需要原图引用])

【禁止】不要编写脚本，不要调用OCR库，只处理这张图片"""


def encode_image(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def get_mime_type(image_path):
    ext = os.path.splitext(image_path)[1].lower()
    return {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}.get(ext, "image/png")


def call_api(image_base64, mime_type, model, api_key, prompt):
    # 讯飞 MaaS OpenAI 兼容入口；可用 SP_API_BASE 环境变量覆盖
    api_base = os.environ.get("SP_API_BASE", "https://maas-coding-api.cn-huabei-1.xf-yun.com/v2")

    request_body = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_base64}"}},
                {"type": "text", "text": prompt},
            ],
        }],
        "max_tokens": 4096,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        # 部分网关(如 Cloudflare 保护)会拦截 urllib 默认 UA(Python-urllib/x.x, error 1010)
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    }

    url = f"{api_base}/chat/completions"
    req = urllib.request.Request(url, data=json.dumps(request_body).encode("utf-8"), headers=headers, method="POST")

    import time

    max_retries = 5
    for attempt in range(1, max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=300) as response:
                result = json.loads(response.read().decode("utf-8"))
                return result["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            code = e.code
            print(f"[重试 {attempt}/{max_retries}] HTTP {code}", file=sys.stderr)
            if code == 503:
                print("  503 Service Unavailable, 等待 5 秒后重试...", file=sys.stderr)
                time.sleep(5)
            elif code == 429:
                # 指数退避: 5s, 10s, 20s, 40s, 80s
                wait = min(5 * (2 ** (attempt - 1)), 80)
                print(f"  429 Too Many Requests, 等待 {wait} 秒后重试...", file=sys.stderr)
                time.sleep(wait)
            elif code >= 500:
                wait = min(5 * (2 ** (attempt - 1)), 60)
                print(f"  服务器错误, 等待 {wait} 秒后重试...", file=sys.stderr)
                time.sleep(wait)
            else:
                if attempt == max_retries:
                    raise
                wait = min(5 * (2 ** (attempt - 1)), 60)
                print(f"  等待 {wait} 秒后重试...", file=sys.stderr)
                time.sleep(wait)
        except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
            print(f"[重试 {attempt}/{max_retries}] 网络错误: {e}", file=sys.stderr)
            if attempt == max_retries:
                raise
            time.sleep(min(5 * (2 ** (attempt - 1)), 60))

    raise RuntimeError(f"API 调用在 {max_retries} 次重试后仍然失败")


def process_image(image_path, model, api_key, prompt):
    """处理单张图片"""
    image_base64 = encode_image(image_path)
    mime_type = get_mime_type(image_path)
    content = call_api(image_base64, mime_type, model, api_key, prompt)
    return image_path, content


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", nargs="+", required=True, help="图片路径（最多3张）")
    parser.add_argument("--model", default=None, help="模型名称（或通过环境变量 SP_MODEL，默认 xopkimik26）")
    parser.add_argument("--token", default=None, help="API Token")
    parser.add_argument("--prompt", default=None, help="提示词（可选，已内置默认模板）")
    parser.add_argument("--output", default=None, help="输出到指定文件（UTF-8），而非 stdout")
    args = parser.parse_args()

    api_key = args.token or os.environ.get("SP_TOKEN")
    if not api_key:
        print("错误: 需要 --token 或 SP_TOKEN 环境变量", file=sys.stderr)
        sys.exit(1)

    # 模型名称: --model 参数优先, 其次 SP_MODEL 环境变量, 最后默认 xopkimik26
    # 注: SP_MODEL 为空串时也回落默认(避免空模型名传给 API 触发 500)
    model = args.model or os.environ.get("SP_MODEL") or "xopkimik26"

    # 使用传入的 prompt 或默认模板
    prompt = args.prompt or DEFAULT_PROMPT

    # 验证图片存在
    for img in args.images:
        if not os.path.isfile(img):
            print(f"错误: 图片不存在 {img}", file=sys.stderr)
            sys.exit(1)

    # 并行处理（最多2张同时）
    max_workers = min(2, len(args.images))
    results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_image, img, model, api_key, prompt): img
            for img in args.images
        }

        for future in concurrent.futures.as_completed(futures):
            image_path, content = future.result()
            img_name = os.path.basename(image_path)
            results.append((img_name, content))

    # 按图片名排序保证顺序稳定
    results.sort(key=lambda x: x[0])

    # 构建输出文本
    lines = []
    for img_name, content in results:
        lines.append(f"=== {img_name} ===")
        lines.append(content)
        lines.append("")
    output_text = "\n".join(lines)

    if args.output:
        # 直接写 UTF-8 文件，绕过 PowerShell Set-Content 的 GBK 编码问题
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_text)
    else:
        print(output_text)


if __name__ == "__main__":
    main()