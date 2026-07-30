"""
外部 LLM 图片识别脚本 —— 薄 wrapper

实际实现已迁移到 common/scripts/external_ocr.py(通用基础设施)。
本文件保留以兼容 docx-img2md skill.md 里的现有调用方式:
    python external_ocr.py --images <图1> <图2> [--model ...] [--output ...]
直接转发到 common 版,参数/行为完全一致。
"""
import sys, os

_HERE = os.path.dirname(os.path.abspath(__file__))
_COMMON = os.path.join(_HERE, '..', '..', '..', 'common', 'scripts')
sys.path.insert(0, _COMMON)

from external_ocr import main  # noqa: E402

if __name__ == "__main__":
    main()
