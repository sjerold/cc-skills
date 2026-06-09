"""
外部 LLM 图片识别脚本

通过 API 调用 kimi/qwen 模型识别图片，遵循 SKILL 提示词规范

用法:
    python external_ocr.py --image <图片路径> [--model <模型名>] [--token <API Key>]

参数:
    --image  图片路径（必须）
    --model  模型名称（默认 kimi-k2-5）
    --token  API Token（或通过环境变量 SP_TOKEN）

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
import time


def encode_image(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def get_mime_type(image_path):
    ext = os.path.splitext(image_path)[1].lower()
    return {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}.get(ext, "image/png")


# SKILL 提示词模板
SKILL_PROMPT = """请识别这张图片，并按以下准则处理：

【图片来源】docx 文档中的截图/扫描件
【处理方式】
1. 判断图片类型：
   - 纯文字类（截图/扫描件/文档正文）：直接 OCR 识别所有文字，按从上到下、从左到右顺序输出
   - 混合类（文字 + 流程图/图表）：OCR 识别文字，同时保留原图引用
   - 纯图形类（纯流程图/架构图，无实质文字）：仅返回 "![image](pic/<图片文件名>)"

2. 图片分类必须经过二次确认：
   - 如果初步判断含图形元素，必须确认图形占比是否 > 50%
   - 以文字/表格为主、只有少量装饰图标的 → 归类为纯文字类

3. OCR 文字识别时跳过：
   - 纯数字页码：1, 12, - 3 -
   - 版本号：V01xxxxx_20251124
   - 分隔线：---, ———
   - 罗马数字页码：I, II, III
   - 日期格式：2025-11-24

4. 跨页表格处理：
   - 如果表格被截断（底部无完整边框线），只识别当前页的数据行
   - 不要重复表头

【输出格式】
第一行输出图片类型：[纯文字] 或 [混合] 或 [纯图形]
第二行开始输出识别内容：
- 纯文字类：直接输出识别到的文字内容
- 混合类：先输出文字内容，最后单独一行输出 [需要原图引用]
- 纯图形类：只输出 [纯图形]

【禁止行为】
- 不要编写任何脚本
- 不要调用 OCR 库
- 只处理这一张图片"""


def call_api(image_base64, mime_type, model, api_key):
    api_base = "https://coding.dashscope.aliyuncs.com/v1"

    request_body = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_base64}"}},
                {"type": "text", "text": SKILL_PROMPT},
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
    parser.add_argument("--image", required=True)
    parser.add_argument("--model", default="kimi-k2-5")
    parser.add_argument("--token", default=None)
    args = parser.parse_args()

    api_key = args.token or os.environ.get("SP_TOKEN")
    if not api_key:
        print("错误: 需要 --token 或 SP_TOKEN 环境变量")
        sys.exit(1)

    if not os.path.isfile(args.image):
        print(f"错误: 图片不存在 {args.image}")
        sys.exit(1)

    image_base64 = encode_image(args.image)
    mime_type = get_mime_type(args.image)

    content = call_api(image_base64, mime_type, args.model, api_key)
    print(content)


if __name__ == "__main__":
    main()