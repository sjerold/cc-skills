#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试URL解析"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import parse_feishu_url

# 使用示例URL，实际测试时通过环境变量传入
test_url = os.environ.get('XIANFENG_TEST_URL', "https://example.feishu.cn/drive/folder/abc123")
result = parse_feishu_url(test_url)

print(f"输入: {test_url}")
print(f"域名: {result['domain']}")
print(f"类型: {result['type']}")
print(f"ID: {result['id']}")