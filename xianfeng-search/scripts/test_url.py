#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试URL解析"""

import sys
sys.path.insert(0, '.')

from config import parse_feishu_url

test_url = "https://fsdvaugca1.phenixfin.com/drive/folder/OiM4fY7ielUUBEdoDFmvX4AQmQo"
result = parse_feishu_url(test_url)

print(f"输入: {test_url}")
print(f"域名: {result['domain']}")
print(f"类型: {result['type']}")
print(f"ID: {result['id']}")