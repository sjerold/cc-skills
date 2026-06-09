"""
通用图片识别测试脚本

用法:
    python test_ocr.py --image <图片路径> --model <模型名> --token <API Key> --prompt <提示词文件或内容>

参数:
    --image  图片路径（必须）
    --model  模型名称（默认 kimi-k2-5）
    --token  API Token（或通过环境变量 SP_TOKEN）
    --prompt 提示词（可直接传入或从 SKILL.md 提取）
"""

import os
import sys
import base64
import json
import urllib.request
import urllib.error
import time
import argparse


def encode_image(image_path):
    """将图片编码为 base64"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def get_image_mime_type(image_path):
    ext = os.path.splitext(image_path)[1].lower()
    mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
    return mime_map.get(ext, "image/png")


def call_api(image_base64, mime_type, model, api_key, prompt):
    """调用 API"""
    api_base = "https://coding.dashscope.aliyuncs.com/v1"

    request_body = {
        "model": model,
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
    start_time = time.time()

    try:
        req = urllib.request.Request(url, data=json.dumps(request_body).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=300) as response:
            result = json.loads(response.read().decode("utf-8"))
            elapsed = time.time() - start_time
            return {
                "success": True,
                "elapsed": round(elapsed, 2),
                "model": model,
                "tokens": result.get("usage", {}),
                "content": result["choices"][0]["message"]["content"],
            }
    except Exception as e:
        elapsed = time.time() - start_time
        return {"success": False, "elapsed": round(elapsed, 2), "error": str(e)}


# SKILL.md 中的子 Agent 提示词模板
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
- 只处理这一张图片，不要读取其他图片"""


def main():
    parser = argparse.ArgumentParser(description="图片识别测试")
    parser.add_argument("--image", required=True, help="图片路径")
    parser.add_argument("--model", default="kimi-k2-5", help="模型名称")
    parser.add_argument("--token", default=None, help="API Token")
    parser.add_argument("--prompt", default=None, help="提示词（不传则使用 SKILL 默认提示词）")
    args = parser.parse_args()

    # 获取 Token
    api_key = args.token or os.environ.get("SP_TOKEN")
    if not api_key:
        print("错误: 需要传入 --token 或设置环境变量 SP_TOKEN")
        sys.exit(1)

    # 获取提示词
    prompt = args.prompt or SKILL_PROMPT

    # 读取图片
    if not os.path.isfile(args.image):
        print(f"错误: 图片不存在 {args.image}")
        sys.exit(1)

    image_base64 = encode_image(args.image)
    mime_type = get_image_mime_type(args.image)

    print(f"图片: {args.image}")
    print(f"模型: {args.model}")
    print(f"提示词长度: {len(prompt)} 字符")
    print("---")

    result = call_api(image_base64, mime_type, args.model, api_key, prompt)

    if result["success"]:
        print(f"耗时: {result['elapsed']} 秒")
        print(f"Tokens: {result['tokens']}")

        # 保存结果
        output_file = f"{args.model}_result.txt"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result["content"])
        print(f"已保存到: {output_file}")
    else:
        print(f"失败: {result['error']}")


if __name__ == "__main__":
    main()