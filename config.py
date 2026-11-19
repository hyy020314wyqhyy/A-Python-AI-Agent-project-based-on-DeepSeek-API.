# -*- coding: utf-8 -*-
"""全局配置：API 与文件路径。"""
import os
import sys

# 从系统环境变量读取 API Key
API_KEY = os.environ.get("DEEPSEEK_API_KEY")

# DeepSeek API 请求地址
API_URL = "https://api.deepseek.com/chat/completions"

# 使用的 AI 模型
MODEL = "deepseek-chat"

# 获取主程序所在文件夹（本文件所在目录）
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))



# 记忆文件路径
MEMORY_FILE = os.path.join(BASE_DIR, "memory.json")



# 工具日志文件路径
TOOL_LOG_FILE = os.path.join(BASE_DIR, "tool_logs.json")