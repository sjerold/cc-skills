"""
执行 OCR 任务 - 图片 1-10
"""
import os
import sys

# 设置环境变量
os.environ['SP_TOKEN'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMDI0IiwiZXhwIjoxODA0MjM3ODAwfQ.oqSpBND9s3yPqkFdHvzE3LvAkkWXq6gNlZ8qqVn9_Y8'

# 导入 batch_ocr
sys.path.insert(0, r'C:\Users\admin\.claude\plugins\docx-img2md\skills\docx-img2md')
from batch_ocr import process_and_save, DEFAULT_PROMPT
from external_ocr import encode_image, get_mime_type, call_api

# 路径配置
input_dir = r'C:\Users\admin\Downloads\文字版\智能合约模板接口 第4部分：公积金委托收款合约模板20251110\pic'
output_dir = r'C:\Users\admin\Downloads\文字版\智能合约模板接口 第4部分：公积金委托收款合约模板20251110\txt'
model = 'kimi-k2-5'
api_key = os.environ.get('SP_TOKEN')

# 确保输出目录存在
os.makedirs(output_dir, exist_ok=True)

# 处理图片 1-10
for i in range(1, 11):
    img_name = f'image_{i:03d}.png'
    img_path = os.path.join(input_dir, img_name)
    output_path = os.path.join(output_dir, f'image_{i:03d}.txt')

    if not os.path.isfile(img_path):
        print(f"跳过: {img_name} (不存在)")
        continue

    print(f"处理: {img_name}...")
    try:
        img_path, success, msg = process_and_save(img_path, output_path, model, api_key, DEFAULT_PROMPT)
        status = "完成" if success else "失败"
        print(f"  [{status}] {msg}")
    except Exception as e:
        print(f"  [失败] {str(e)}")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"OCR 失败: {str(e)}")

print("\n全部完成!")