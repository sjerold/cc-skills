# -*- coding: utf-8 -*-
"""批量 OCR 处理脚本"""
import os
import sys
import subprocess

# 设置环境变量
os.environ['SP_TOKEN'] = 'sk-sp-6bd44c19cfdf4f75b675db894ff2178f'
os.environ['PYTHONIOENCODING'] = 'utf-8'

# 图片和输出目录
base_dir = r'C:\Users\admin\Downloads\文字版\智能合约模板接口 第6部分：企业贷款合约模板20250626'
pic_dir = os.path.join(base_dir, 'pic')
txt_dir = os.path.join(base_dir, 'txt')

# 确保 txt 目录存在
os.makedirs(txt_dir, exist_ok=True)

# 处理图片 13-24
images_to_process = [f'image_{i:03d}.png' for i in range(13, 25)]

ocr_script = r'C:\Users\admin\.claude\plugins\docx-img2md\skills\docx-img2md\external_ocr.py'

for img_name in images_to_process:
    img_path = os.path.join(pic_dir, img_name)
    txt_path = os.path.join(txt_dir, img_name.replace('.png', '.txt'))

    if not os.path.exists(img_path):
        print(f"跳过: {img_name} 不存在")
        continue

    print(f"处理: {img_name}")

    # 运行 OCR
    result = subprocess.run(
        [sys.executable, ocr_script, '--images', img_path],
        capture_output=True,
        text=True,
        encoding='utf-8'
    )

    # 写入输出文件
    with open(txt_path, 'w', encoding='utf-8') as f:
        if result.stdout:
            f.write(result.stdout)
        if result.stderr:
            f.write(f"\n[错误]\n{result.stderr}")

    print(f"完成: {img_name} -> {txt_path}")
    print()

print("全部完成!")