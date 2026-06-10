"""
循环后校验脚本

用法:
    python check_progress.py <md文件路径>

返回:
    已处理图片数量 + 校验提示

原理:
    统计 md 文件中已写入的图片引用数量，
    用于循环后校验：确认本轮只处理1张、写入成功。
"""

import os
import sys
import re


def check_progress(md_path):
    if not os.path.isfile(md_path):
        print("CHECK_RESULT: md文件不存在（首张图片处理前）")
        print("NEXT_ACTION: 写入后再次调用本脚本校验")
        return

    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 统计 md 中已写入的图片引用数量
    refs = re.findall(r'pic/image_\d+\.png', content)
    count = len(refs)

    print(f"CHECK_RESULT: 已处理 {count} 张图片")
    print("循环后校验清单：")
    print("- [ ] 本轮只处理了1张图片？")
    print("- [ ] 已写入md（Edit成功）？")
    print(f"- [ ] md文件图片引用数量={count}（预期增加1）？")
    print("")
    print("校验通过后，继续处理下一张图片")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python check_progress.py <md文件路径>")
        sys.exit(1)

    md_path = sys.argv[1]
    check_progress(md_path)
