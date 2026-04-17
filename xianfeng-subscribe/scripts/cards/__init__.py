#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
卡片模板模块
"""

from .notification_card import build_notification_card
from .search_result_card import build_search_result_card

__all__ = [
    'build_notification_card',
    'build_search_result_card',
]