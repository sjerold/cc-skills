#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置模块
"""

import os

# 插件目录
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(SCRIPTS_DIR)
PLUGINS_DIR = os.path.dirname(PLUGIN_DIR)

# 配置目录
CONFIG_DIR = os.path.join(PLUGIN_DIR, "config")
WEBHOOKS_FILE = os.path.join(CONFIG_DIR, "webhooks.json")

# common模块路径
COMMON_PATH = os.path.join(PLUGINS_DIR, "common", "scripts")