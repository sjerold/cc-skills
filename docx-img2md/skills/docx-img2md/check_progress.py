"""
检查当前处理进度，判断是否需要触发自检

用法:
    python check_progress.py <md文件路径> [自检间隔]

返回:
    SELF_CHECK: required   - 需要触发自检
    SELF_CHECK: skip       - 不需要，继续处理

原理:
    统计 md 文件中已写入的图片引用数量（![image] 或 文字引用），
    基于文件系统状态而非模型记忆，避免计数偏差。
"""

import os
import sys
import re


def check_progress(md_path, interval=5):
    if not os.path.isfile(md_path):
        print("SELF_CHECK: skip (md file not exists yet)")
        return

    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 统计 md 中已写入的图片引用数量
    # 匹配 pic/image_xxx.png
    refs = re.findall(r'pic/image_\d+\.png', content)
    count = len(refs)

    if count > 0 and count % interval == 0:
        print(f"SELF_CHECK: required (已处理 {count} 张图片，达到 {interval} 的倍数)")
    else:
        next_check = ((count // interval) + 1) * interval
        print(f"SELF_CHECK: skip (已处理 {count} 张图片，下一次自检在第 {next_check} 张后)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python check_progress.py <md文件路径> [自检间隔]")
        sys.exit(1)

    md_path = sys.argv[1]
    interval = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    check_progress(md_path, interval)
