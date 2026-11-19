# -*- coding: utf-8 -*-

import os
import json
import re
import time
from datetime import datetime

import requests

from config import API_KEY, API_URL, MODEL



def create_task_step(name):
    return {
        "name": name,
        "status": "pending",
        "result": None
    }


def generate_task_plan(goal):
    """根据用户目标生成并验证任务清单。"""
    if not isinstance(goal, str) or not goal.strip():
        print("任务计划生成失败：任务目标不能为空。")
        return None
    if not API_KEY:
        print("任务计划生成失败：没有配置 DEEPSEEK_API_KEY。")
        return None

    print("\n正在分析任务目标...")
    prompt = (
        "你是一个任务规划助手。请将用户目标拆分成清晰、具体、按顺序执行的步骤。"
        "每个步骤简短明确、可以独立完成。只返回 JSON 对象，格式为："
        '{"steps": ["第一步任务", "第二步任务"]}。'
    )
    prompt += f"\n\n用户的任务目标：{goal.strip()}"

    try:
        response = requests.post(
            API_URL,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": goal.strip()}
                ],
                "stream": False
            },
            timeout=60
        )
        response.raise_for_status()
        result = response.json()["choices"][0]["message"].get("content", "")
    except requests.RequestException as e:
        print(f"任务计划生成失败：{e}")
        return None
    except (ValueError, KeyError, IndexError, TypeError, AttributeError) as e:
        print(f"任务计划返回数据异常：{e}")
        return None

    if not isinstance(result, str) or not result.strip():
        print("任务计划生成失败：AI 返回内容为空或格式不正确。")
        return None

    try:
        plan_data = json.loads(result)
    except json.JSONDecodeError as e:
        print(f"任务计划 JSON 解析失败：{e}")
        return None

    if not isinstance(plan_data, dict):
        print("任务计划格式错误：返回内容必须是 JSON 对象。")
        return None

    steps = plan_data.get("steps")
    if not isinstance(steps, list) or not 1 <= len(steps) <= 20:
        print("任务计划格式错误：步骤数量必须为1到20步。")
        return None
    if any(not isinstance(step, str) or not step.strip() or len(step) > 500 for step in steps):
        print("任务计划格式错误：每个步骤必须是1到500字符的非空文本。")
        return None

    return {
        "goal": goal.strip(),
        "status": "pending",
        "steps": [create_task_step(step.strip()) for step in steps]
    }


def execute_task_step(step, previous_results=None):
    """使用 AI 执行一个任务步骤，并验证返回状态。"""

    if not isinstance(step, dict):
        return "错误：任务步骤必须是字典。"

    if not isinstance(step.get("name"), str) or not step["name"].strip():
        return "错误：任务步骤名称不能为空。"

    if step.get("status") == "completed":
        return "提示：该任务步骤已经完成，无需重复执行。"

    if step.get("status") not in ("pending", "failed"):
        return "错误：任务步骤状态无效。"

    if previous_results is None:
        previous_results = []

    if not isinstance(previous_results, list):
        return "错误：之前步骤的执行结果必须是列表。"

    if not API_KEY:
        error_message = "错误：没有配置 DEEPSEEK_API_KEY。"
        step["status"] = "failed"
        step["result"] = error_message
        return error_message

    print(f"\n正在执行任务：{step['name']}")

    step["status"] = "pending"
    step["result"] = None

    messages = [
        {
            "role": "system",
            "content": (
                "你是一个严谨的任务执行助手。"
                "请认真完成用户指定的任务步骤。"
                "如果有之前步骤的执行结果，请参考这些结果。"
                "必须根据实际完成情况判断状态。"
                "只有提供了具体、有效的执行结果，才能标记为 completed。"
                "如果无法完成、缺少必要信息、没有执行实际操作，"
                "或者只能描述计划而没有实际结果，必须标记为 failed。"
                "不得声称执行了实际上没有执行的操作。"
                "只返回 JSON 对象，不要添加 Markdown 代码块。"
                '格式为：{"status":"completed","result":"具体执行结果"}'
                "或"
                '{"status":"failed","result":"失败原因"}。'
            )
        },
        {
            "role": "user",
            "content": (
                f"之前步骤的执行结果：{previous_results}\n\n"
                f"请完成当前任务步骤：{step['name']}"
            )
        }
    ]

    try:
        response = requests.post(
            API_URL,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": MODEL,
                "messages": messages,
                "stream": False
            },
            timeout=60
        )

        response.raise_for_status()

    except requests.RequestException as e:
        error_message = f"任务步骤执行失败：{e}"
        print(error_message)

        step["status"] = "failed"
        step["result"] = error_message

        return error_message

    try:
        result = response.json()["choices"][0]["message"]["content"]

        if not isinstance(result, str) or not result.strip():
            raise ValueError("AI 返回内容为空。")

        task_result = json.loads(result)

        if not isinstance(task_result, dict):
            raise ValueError("AI 返回内容必须是 JSON 对象。")

        status = task_result.get("status")
        detail = task_result.get("result")

        if status not in ("completed", "failed"):
            raise ValueError("任务状态必须是 completed 或 failed。")

        if not isinstance(detail, str) or not detail.strip():
            raise ValueError("任务执行结果不能为空。")

    except (ValueError, KeyError, IndexError, TypeError) as e:
        error_message = f"任务步骤返回数据异常：{e}"
        print(error_message)

        step["status"] = "failed"
        step["result"] = error_message

        return error_message

    step["result"] = detail.strip()
    step["status"] = status

    print("\n[任务步骤执行结果]")
    print(step["result"])

    if status == "failed":
        print("任务步骤未完成。")
        return "任务步骤未完成：" + step["result"]

    print("任务步骤已完成。")
    return step["result"]


def check_task_plan(task_plan):
    """检查任务计划中的每个步骤是否有有效结果。"""

    if not isinstance(task_plan, dict) or not isinstance(task_plan.get("steps"), list):
        return False, ["任务计划不存在或格式不正确"]

    problems = []

    for index, step in enumerate(task_plan["steps"], start=1):

        if not isinstance(step, dict):
            problems.append(f"第 {index} 步的数据格式不正确")
            continue

        if step.get("status") != "completed":
            problems.append(f"第 {index} 步尚未完成")

        result = step.get("result")

        if not isinstance(result, str) or not result.strip():
            problems.append(f"第 {index} 步没有有效的执行结果")

    return len(problems) == 0, problems