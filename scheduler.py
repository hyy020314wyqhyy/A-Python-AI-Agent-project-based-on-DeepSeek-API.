# -*- coding: utf-8 -*-

import os
import json
import re
import time
from datetime import datetime

import requests



def get_current_time():
    """获取电脑当前的日期和时间。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def make_study_plan(minutes):
    """生成 Python 学习计划。"""
    
    if isinstance(minutes, bool):
        return "错误：学习时长必须是整数。"

    
    

    if isinstance(minutes, float) and not minutes.is_integer():
        return "错误：学习时长不能是小数。"

    try:
        minutes = int(minutes)
    except (ValueError, TypeError, OverflowError):
        return "错误：学习时长必须是有效的整数。"



    if not 1 <= minutes <= 600:
        return "学习时长需要在 1 到 600 分钟之间。"

    python_minutes = minutes // 2
    practice_minutes = minutes - python_minutes

    return (
        f"总时长：{minutes} 分钟\n"
        f"1. 学习 Python 基础：{python_minutes} 分钟\n"
        f"2. 动手编程练习：{practice_minutes} 分钟"
    )