"""
外部 LLM 图片识别脚本 —— 薄 wrapper

实际实现已迁移到 common/scripts/external_ocr.py(通用基础设施)。
本文件保留以兼容 docx-img2md skill.md 里的现有调用方式:
    python external_ocr.py --images <图1> <图2> [--model ...] [--output ...]
直接转发到 common 版,参数/行为完全一致。
"""
import sys, os, importlib.util

_HERE = os.path.dirname(os.path.abspath(__file__))
_COMMON = os.path.normpath(os.path.join(_HERE, '..', '..', '..', 'common', 'scripts'))
_TARGET = os.path.join(_COMMON, 'external_ocr.py')

# Use importlib to load the module by file path, avoiding circular import
# caused by sharing the same module name "external_ocr".
spec = importlib.util.spec_from_file_location("_common_ocr", _TARGET)
common_ocr = importlib.util.module_from_spec(spec)
sys.modules["_common_ocr"] = common_ocr
spec.loader.exec_module(common_ocr)

if __name__ == "__main__":
    common_ocr.main()