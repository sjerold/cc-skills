"""
测试调用 Qwen VL 模型识别图片

API: OpenAI 兼容协议
Endpoint: https://coding.dashscope.aliyuncs.com/v1
模型: qwen-plus (视觉模型)
Token: 从环境变量 SP_TOKEN 获取

用法:
    python test_qwen_vl.py <图片路径>
"""

import os
import sys
import base64
import json
import urllib.request
import urllib.error


def encode_image(image_path):
    """将图片编码为 base64"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def get_image_mime_type(image_path):
    """根据文件扩展名获取 MIME 类型"""
    ext = os.path.splitext(image_path)[1].lower()
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    return mime_map.get(ext, "image/png")


def call_qwen_vl(image_path):
    """调用 Qwen VL API"""
    api_key = os.environ.get("SP_TOKEN")
    if not api_key:
        print("错误: 未设置 SP_TOKEN 环境变量", file=sys.stderr)
        sys.exit(1)

    api_base = "https://coding.dashscope.aliyuncs.com/v1"
    model = "qwen3.7-plus"  # Qwen 视觉模型（用户指定）

    image_base64 = encode_image(image_path)
    mime_type = get_image_mime_type(image_path)

    # 构建 OpenAI 兼容格式的请求
    request_body = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{image_base64}"
                        },
                    },
                    {
                        "type": "text",
                        "text": "请识别这张图片中的所有文字内容，按从上到下、从左到右的顺序输出。跳过页码、版本号、日期等无关信息。",
                    },
                ],
            }
        ],
        "max_tokens": 4096,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    url = f"{api_base}/chat/completions"

    print(f"API URL: {url}")
    print(f"Model: {model}")
    print(f"Image: {image_path}")
    print("---")

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(request_body).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        print(f"发送请求... (超时 300 秒)")
        with urllib.request.urlopen(req, timeout=300) as response:
            result = json.loads(response.read().decode("utf-8"))

            # 保存结果到文件
            output_file = "qwen_result.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"结果已保存到: {output_file}")

            print("=== 识别内容 ===")
            content = result["choices"][0]["message"]["content"]
            # 保存纯文本内容
            with open("qwen_content.txt", "w", encoding="utf-8") as f:
                f.write(content)
            print(f"内容已保存到: qwen_content.txt")

    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"API 错误 {e.code}: {error_body}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"请求失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python test_qwen_vl.py <图片路径>")
        print("环境变量: SP_TOKEN (必须)")
        sys.exit(1)

    image_path = sys.argv[1]
    if not os.path.isfile(image_path):
        print(f"错误: 图片文件不存在 {image_path}", file=sys.stderr)
        sys.exit(1)

    call_qwen_vl(image_path)