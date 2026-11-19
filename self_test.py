# -*- coding: utf-8 -*-
"""自测脚本：不调用 API 也能跑基础校验。"""

import os
import json

from config import API_KEY
from knowledge_base import (
    create_sample_json,
    parse_json_text,
    parse_sample_json,
    validate_learning_plan,
    validate_json_fields,
    validate_json_types,
    serialize_json_data,
    generate_json_data,
)


def check_sample_json_types():
    """检查 JSON 数据转换后的 Python 类型。"""

    data = parse_sample_json()

    print("title 类型：", type(data["title"]))
    print("duration 类型：", type(data["duration"]))
    print("tasks 类型：", type(data["tasks"]))


def test_invalid_json():
    """测试错误 JSON 的异常处理。"""

    invalid_text = '{"title": "Python 学习计划",}'

    try:
        data = json.loads(invalid_text)
        return data
    except json.JSONDecodeError:
        return "错误：JSON 格式不正确。"


def check_generated_json(prompt):
    """检查 AI 生成的 JSON 数据类型。"""

    data = generate_json_data(prompt)

    if not isinstance(data, dict):
        print("AI 生成 JSON 失败：", data)
        return False

    print("标题：", data.get("title"))
    print("学习时间：", type(data.get("duration")))
    print("任务列表：", type(data.get("tasks")))

    return True


def run_self_test():
    """运行基础自测，返回是否全部通过。"""
    print("=" * 40)
    print("开始自测")
    print("=" * 40)

    passed = 0
    failed = 0

    def check(name, condition, detail=""):
        nonlocal passed, failed
        if condition:
            passed += 1
            print(f"[通过] {name}")
        else:
            failed += 1
            print(f"[失败] {name} {detail}")

    # 1. 模块导入检查
    modules = [
        "config", "logger", "memory", "knowledge_base", "scheduler",
        "file_manager", "task_manager", "tool_manager", "ai_client",
    ]
    for mod in modules:
        try:
            __import__(mod)
            check(f"导入模块 {mod}", True)
        except Exception as e:  # noqa: BLE001
            check(f"导入模块 {mod}", False, str(e))

    # 2. 示例数据校验
    sample_text = create_sample_json()
    check("示例数据是 JSON 字符串", isinstance(sample_text, str))

    data = parse_sample_json()
    check("示例数据解析为 dict", isinstance(data, dict))
    check("示例数据字段完整", validate_json_fields(
        data, ["title", "duration", "tasks"]) == "JSON 必需字段检查通过。")
    check("示例数据通过整体校验", validate_learning_plan(data) == "学习计划 JSON 验证全部通过。")

    # 3. JSON 字符串解析
    text = serialize_json_data(data)
    parsed = parse_json_text(text)
    check("JSON 解析还原一致", parsed == data)

    # 4. 类型校验
    check("类型校验通过", validate_json_types(data) == "JSON 数据类型检查通过。")

    # 5. 非法 JSON 被正确拦截
    invalid_result = test_invalid_json()
    check("非法 JSON 被拒绝",
          isinstance(invalid_result, str) and invalid_result.startswith("错误："))

    # 6. 需要 API 的检查（没有 Key 则跳过）
    if API_KEY:
        print("[提示] 检测到 DEEPSEEK_API_KEY，执行联网检查……")
        check("AI 生成 JSON 可用", check_generated_json("制定一个 30 分钟 Python 学习计划") is True)
    else:
        print("[跳过] 未配置 DEEPSEEK_API_KEY，跳过联网检查。")

    print("-" * 40)
    print(f"结果：通过 {passed} 项，失败 {failed} 项")
    print("=" * 40)
    return failed == 0


if __name__ == "__main__":
    raise SystemExit(0 if run_self_test() else 1)
