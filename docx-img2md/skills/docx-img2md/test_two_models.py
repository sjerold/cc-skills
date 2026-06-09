"""
同时测试两个模型的图片识别速度和效果

API: https://coding.dashscope.aliyuncs.com/v1
模型1: qwen3.7-plus
模型2: kimi-k2-5

用法:
    python test_two_models.py <图片路径>
"""

import os
import sys
import base64
import json
import urllib.request
import urllib.error
import threading
import time


def encode_image(image_path):
    """将图片编码为 base64"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def get_image_mime_type(image_path):
    ext = os.path.splitext(image_path)[1].lower()
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }
    return mime_map.get(ext, "image/png")


def call_model(image_base64, mime_type, model_name, api_base, api_key, prompt, results, index):
    """调用指定模型"""
    start_time = time.time()

    request_body = {
        "model": model_name,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_base64}"}},
                    {"type": "text", "text": prompt},
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

    try:
        req = urllib.request.Request(url, data=json.dumps(request_body).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=300) as response:
            result = json.loads(response.read().decode("utf-8"))
            elapsed = time.time() - start_time
            results[index] = {
                "model": model_name,
                "elapsed": round(elapsed, 2),
                "success": True,
                "content": result["choices"][0]["message"]["content"],
                "tokens": result.get("usage", {}),
            }
    except Exception as e:
        elapsed = time.time() - start_time
        results[index] = {"model": model_name, "elapsed": round(elapsed, 2), "success": False, "error": str(e)}


def main():
    if len(sys.argv) < 2:
        print("用法: python test_two_models.py <图片路径>")
        sys.exit(1)

    image_path = sys.argv[1]
    api_key = os.environ.get("SP_TOKEN")
    if not api_key:
        print("错误: 未设置 SP_TOKEN")
        sys.exit(1)

    image_base64 = encode_image(image_path)
    mime_type = get_image_mime_type(image_path)
    api_base = "https://coding.dashscope.aliyuncs.com/v1"
    prompt = "请识别这张图片中的所有文字内容，按从上到下、从左到右的顺序输出。跳过页码、版本号、日期等无关信息。"

    models = ["qwen3.7-plus", "kimi-k2-5"]
    results = {}

    print(f"图片: {image_path}")
    print(f"API: {api_base}")
    print(f"同时发送 {len(models)} 个请求...")
    print("---")

    # 并行发送
    threads = []
    for i, model in enumerate(models):
        t = threading.Thread(target=call_model, args=(image_base64, mime_type, model, api_base, api_key, prompt, results, i))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # 输出结果
    for i, model in enumerate(models):
        r = results.get(i, {})
        print(f"\n=== {model} ===")
        print(f"耗时: {r.get('elapsed', 0)} 秒")
        if r.get("success"):
            print(f"Tokens: {r.get('tokens', {})}")
            content = r.get("content", "")
            with open(f"{model}_content.txt", "w", encoding="utf-8") as f:
                f.write(content)
            print(f"内容已保存: {model}_content.txt ({len(content)} 字符)")
        else:
            print(f"失败: {r.get('error')}")

    print("\n完成")


if __name__ == "__main__":
    main()