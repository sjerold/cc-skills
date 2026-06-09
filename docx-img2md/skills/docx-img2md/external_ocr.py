"""
外部 LLM 图片识别脚本

通过 API 调用 kimi/qwen 模型识别图片，提示词从 SKILL.md 提取或通过参数传入

用法:
    python external_ocr.py --image <图片路径> [--model <模型名>] [--token <API Key>] [--prompt <提示词文件>]

参数:
    --image  图片路径（必须）
    --model  模型名称（默认 kimi-k2-5）
    --token  API Token（或通过环境变量 SP_TOKEN）
    --prompt 提示词内容（必须传入，从 SKILL.md 提取）

返回:
    第一行: 图片类型 [纯文字] 或 [混合] 或 [纯图形]
    后续行: OCR 文字内容
    最后: [需要原图引用]（混合/纯图形类）
"""

import os
import sys
import base64
import json
import urllib.request
import urllib.error


def encode_image(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def get_mime_type(image_path):
    ext = os.path.splitext(image_path)[1].lower()
    return {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}.get(ext, "image/png")


def call_api(image_base64, mime_type, model, api_key, prompt):
    api_base = "https://coding.dashscope.aliyuncs.com/v1"

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
    }

    url = f"{api_base}/chat/completions"

    req = urllib.request.Request(url, data=json.dumps(request_body).encode("utf-8"), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=300) as response:
        result = json.loads(response.read().decode("utf-8"))
        return result["choices"][0]["message"]["content"]


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True, help="图片路径")
    parser.add_argument("--model", default="kimi-k2-5", help="模型名称")
    parser.add_argument("--token", default=None, help="API Token")
    parser.add_argument("--prompt", required=True, help="提示词内容（从 SKILL.md 传入）")
    args = parser.parse_args()

    api_key = args.token or os.environ.get("SP_TOKEN")
    if not api_key:
        print("错误: 需要 --token 或 SP_TOKEN 环境变量")
        sys.exit(1)

    if not os.path.isfile(args.image):
        print(f"错误: 图片不存在 {args.image}")
        sys.exit(1)

    if not args.prompt:
        print("错误: 需要传入 --prompt 提示词")
        sys.exit(1)

    image_base64 = encode_image(args.image)
    mime_type = get_mime_type(args.image)

    content = call_api(image_base64, mime_type, args.model, api_key, args.prompt)
    print(content)


if __name__ == "__main__":
    main()