# -*- coding: utf-8 -*-

import os
import json
import re
import time
from datetime import datetime

import requests

from config import API_KEY, API_URL, BASE_DIR, MODEL



def create_sample_json():
    """创建示例 JSON 数据。"""

    data = {
        "title": "Python 学习计划",
        "duration": 30,
        "tasks": [
            "学习 Python 基础",
            "练习 AI API",
            "开发自动化工具"
        ]
    }

    return json.dumps(data, ensure_ascii=False, indent=4)


def parse_sample_json():
    """将 JSON 字符串转换为 Python 字典。"""

    json_text = create_sample_json()

    data = json.loads(json_text)

    return data


def read_sample_json_fields():
    """读取 JSON 字典中的指定字段。"""

    data = parse_sample_json()

    title = data["title"]
    duration = data["duration"]
    tasks = data["tasks"]

    print("学习计划：", title)
    print("学习时间：", duration, "分钟")
    print("学习任务：")

    for task in tasks:
        print("-", task)


def parse_json_text(json_text):
    """安全解析 JSON 字符串。"""

    try:
        return json.loads(json_text)

    except json.JSONDecodeError:
        return "错误：JSON 格式不正确。"


def serialize_json_data(data):
    """将 Python 数据转换为 JSON 字符串。"""

    try:
        return json.dumps(
            data,
            ensure_ascii=False,
            indent=4
        )

    except (TypeError, ValueError, RecursionError) as e:
        return f"错误：JSON 序列化失败。{e}"


def generate_json_response(messages):
    """调用 DeepSeek API 生成 JSON 格式的数据。"""

    if not API_KEY:
        return "错误：没有配置 DEEPSEEK_API_KEY。"
    session = requests.Session()
    session.trust_env = False
    try:
        response = session.post(
            API_URL,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": MODEL,
                "messages": messages,
                "stream": False,
                "response_format": {
                    "type": "json_object"
                }
            },
            timeout=60
        )

        response.raise_for_status()

        result = response.json()
        answer = result["choices"][0]["message"].get("content", "")

        if not isinstance(answer, str) or not answer.strip():
            return "错误：AI 没有返回 JSON 内容。"

        return answer.strip()

    except requests.RequestException as e:
        return f"错误：DeepSeek API 请求失败。{e}"

    except (KeyError, ValueError, IndexError, TypeError, AttributeError) as e:
        return f"错误：处理 AI 返回内容失败。{e}"


def generate_json_data(prompt):
    """调用 DeepSeek API 生成 JSON 数据。"""

    messages = [
        {
            "role": "system",
            "content": (
                "你是一个 JSON 数据生成助手。"
                "请严格按照以下结构生成 JSON："
                '{"title": "学习计划标题", "duration": 30, "tasks": ["任务1", "任务2"]}。'
                "title 必须是字符串，duration 必须是正整数，tasks 必须是非空字符串列表。"
                "只返回 JSON，不要添加 Markdown 代码块或解释。"
            )
        },
        {
            "role": "user",
            "content": prompt
        }
    ]

    answer = generate_json_response(messages)

    if answer.startswith("错误："):
        return answer

    data = parse_json_text(answer)

    if isinstance(data, str):
        return data

    validation_result = validate_learning_plan(data)

    if validation_result != "学习计划 JSON 验证全部通过。":
        return validation_result

    return data


def save_json_file(data, filename="learning_plan.json"):
    from pathlib import Path

    if not isinstance(filename, str) or not filename.strip():
        return "错误：JSON文件名必须是非空字符串。"

    if Path(filename).name != filename or Path(filename).suffix.lower() != ".json":
        return "错误：只能在程序所在目录保存 .json 文件。"

    if not isinstance(data, dict):
        return "错误：保存内容必须是 JSON 对象。"

    validation_result = validate_learning_plan(data)
    if validation_result != "学习计划 JSON 验证全部通过。":
        return validation_result

    # 保存前先生成 JSON，并检查 UTF-8 编码后的实际大小
    try:
        json_data = json.dumps(
            data,
            ensure_ascii=False,
            indent=4
        )

        if len(json_data.encode("utf-8")) > 5 * 1024 * 1024:
            return "错误：JSON 文件超过5MB，无法保存。"

    except (TypeError, ValueError, RecursionError, UnicodeEncodeError) as e:
        return f"错误：JSON 数据序列化失败。{e}"

    file_path = Path(BASE_DIR) / filename
    temp_file = Path(str(file_path) + ".tmp")
    created_temp_file = False

    try:
        if file_path.is_symlink():
            return "错误：JSON文件不能是符号链接。"
        if file_path.exists():
            return "错误：JSON文件已经存在，为保护原文件，本次不覆盖。"
        if os.path.lexists(temp_file):
            return "错误：JSON保存临时文件已经存在，请先检查。"

        with temp_file.open("x", encoding="utf-8") as f:
            created_temp_file = True
            f.write(json_data)
            f.flush()
            os.fsync(f.fileno())

        os.replace(temp_file, file_path)
        created_temp_file = False
        return "JSON文件保存成功。"

    except (OSError, TypeError, ValueError, UnicodeEncodeError) as e:
        if created_temp_file and os.path.lexists(temp_file):
            try:
                temp_file.unlink()
            except OSError:
                pass
        return f"JSON文件保存失败：{e}"


def read_json_file(filename="learning_plan.json"):
    from pathlib import Path

    if not isinstance(filename, str) or not filename.strip():
        return "错误：JSON文件名必须是非空字符串。"

    if Path(filename).name != filename or Path(filename).suffix.lower() != ".json":
        return "错误：只能读取程序所在目录中的 .json 文件。"

    file_path = Path(BASE_DIR) / filename

    try:
        if file_path.is_symlink():
            return "错误：JSON文件不能是符号链接。"
        if not file_path.exists():
            return "错误：JSON文件不存在。"
        if not file_path.is_file():
            return "错误：JSON路径不是普通文件。"
        if file_path.stat().st_size > 5 * 1024 * 1024:
            return "错误：JSON文件超过5MB，无法读取。"

        with file_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    except json.JSONDecodeError:
        return "错误：JSON文件格式不正确。"
    except (OSError, UnicodeDecodeError) as e:
        return f"错误：JSON文件读取失败：{e}"


def validate_json_fields(data, required_fields):
    """检查 JSON 数据是否包含所有必需字段。"""

    if not isinstance(data, dict):
        return "错误：JSON 数据必须是字典。"

    missing_fields = [
        field
        for field in required_fields
        if field not in data
    ]

    if missing_fields:
        return f"错误：缺少字段 {missing_fields}"

    return "JSON 必需字段检查通过。"


def validate_json_types(data):
    """检查 JSON 数据中指定字段的数据类型。"""

    if not isinstance(data, dict):
        return "错误：JSON 数据必须是字典。"

    if not isinstance(data.get("title"), str):
        return "错误：title 必须是字符串。"

    if type(data.get("duration")) is not int:
        return "错误：duration 必须是整数。"

    if not data["title"].strip():
        return "错误：学习计划标题不能为空。"
    
    if not isinstance(data.get("tasks"), list):
        return "错误：tasks 必须是列表。"

    return "JSON 数据类型检查通过。"


def validate_learning_plan(data):
    """完整验证学习计划 JSON 数据。"""

    required_fields = ["title", "duration", "tasks"]

    field_result = validate_json_fields(data, required_fields)

    if field_result != "JSON 必需字段检查通过。":
        return field_result
    
    
        
    
    type_result = validate_json_types(data)

    if type_result != "JSON 数据类型检查通过。":
        return type_result

    if data["duration"] <= 0:
        return "错误：学习时间必须大于 0。"
    
    if not data["tasks"]:
        return "错误：学习任务列表不能为空。"
    
    if not all(isinstance(task, str) for task in data["tasks"]):
        return "错误：每个学习任务都必须是字符串。"
    
    if not all(task.strip() for task in data["tasks"]):
        return "错误：学习任务内容不能为空。"

    return "学习计划 JSON 验证全部通过。"