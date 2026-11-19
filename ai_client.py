# -*- coding: utf-8 -*-

import os
import json
import re
import time
from datetime import datetime

import requests

from config import API_KEY, API_URL, MODEL
from logger import save_tool_log
from memory import load_memory
from task_manager import check_task_plan, execute_task_step, generate_task_plan
from tool_manager import TOOLS, run_tool



def build_system_prompt(memory):
    """根据长期记忆生成系统提示词。"""

    memory_text = (
        "\n".join(f"- {item}" for item in memory)
        if memory
        else "暂时没有已保存的记忆。"
    )

    return (
        "你是一个友好的中文 AI 助手。"
        "需要当前时间时，使用时间工具，不要猜测时间。"
        "用户明确要求制定学习计划但没有说明时长时，"
        "默认安排 30 分钟，不要追问时长。"
        "工具返回结果后，用自然、清晰的中文回答。"
        "当用户提出复杂任务时，先分析最终目标，"
        "再将任务拆分成清晰、合理、可执行的小步骤。"
        "按照步骤顺序制定计划，并说明每一步的目标。"
        "如果某一步需要调用已有工具，应根据工具说明决定是否调用。"
        "不要声称已经执行了实际上没有执行的任务。"
        "任务完成后，整理执行结果并向用户汇报。"
        "\n\n以下是从记忆文件读取的用户信息：\n"
        f"{memory_text}\n"
        "回答时可以参考这些信息，但不要把不确定的信息当成事实。"
        "用户提出具体的数值计算请求时，必须优先调用计算器工具。"
        "计算器返回结果后，才能给出计算答案；如果计算失败，必须如实说明。"
        "当计算工具返回错误时，直接向用户转述工具的错误信息，"
        "不要重复添加“计算失败”等前缀，也不要重复错误内容。"
        "不要绕过工具，直接编造或猜测精确计算结果。"
        "如果无法通过工具验证结果，应明确说明，不要声称结果准确。"
    )


def refresh_system_prompt(messages):
    """重新读取长期记忆，并更新当前对话的系统提示词。"""

    try:
        memory = load_memory()
    except RuntimeError as e:
        print("AI：更新系统提示词失败。", e)
        return False

    if (
        not isinstance(messages, list)
        or not messages
        or not isinstance(messages[0], dict)
        or messages[0].get("role") != "system"
    ):
        print("AI：系统提示词不存在或消息格式不正确，无法更新。")
        return False

    messages[0]["content"] = build_system_prompt(memory)

    return True


def trim_conversation_history(messages, max_rounds, max_chars=50000):
    """保留最近若干轮完整对话，并限制历史长度。"""

    if not isinstance(messages, list):
        return []

    if not all(isinstance(message, dict) for message in messages):
        print("[提示] 对话历史包含无效消息，已停止裁剪。")
        return messages

    if (
        not isinstance(max_rounds, int)
        or isinstance(max_rounds, bool)
        or max_rounds <= 0
    ):
        return messages

    if (
        not isinstance(max_chars, int)
        or isinstance(max_chars, bool)
        or max_chars <= 0
    ):
        return messages

    if not messages:
        return messages

    # 单独保留系统提示词
    system_messages = [
        message for message in messages
        if message.get("role") == "system"
    ]

    conversation = [
        message for message in messages
        if message.get("role") != "system"
    ]

    # 找到真实用户消息，排除内部任务总结请求
    user_rounds = [
        index
        for index, message in enumerate(conversation)
        if (
            message.get("role") == "user"
            and not (
                isinstance(message.get("content"), str)
                and message["content"].startswith("[内部任务总结请求]")
            )
        )
    ]

    # 没有真实用户消息时，不进行不安全的裁剪
    if not user_rounds:
        print("[提示] 没有找到真实用户消息，暂不裁剪。")
        return messages

    # 检查工具调用请求和结果是否完整配对
    
    
    def tool_calls_are_complete(items):
        """检查一组工具调用是否全部按顺序完成。"""

        pending_tool_ids = set()
        all_tool_ids = set()

        for message in items:

            role = message.get("role")

            if role == "assistant":

                # 上一组工具调用尚未完成，不允许开始新的 assistant 消息
                if pending_tool_ids:
                    return False

                tool_calls = message.get("tool_calls") or []

                if not isinstance(tool_calls, list):
                    return False

                for call in tool_calls:

                    if not isinstance(call, dict):
                        return False

                    call_id = call.get("id")

                    if not isinstance(call_id, str) or not call_id:
                        return False

                    if call_id in all_tool_ids:
                        return False

                    all_tool_ids.add(call_id)
                    pending_tool_ids.add(call_id)

            elif role == "tool":

                tool_call_id = message.get("tool_call_id")

                if (
                    not isinstance(tool_call_id, str)
                    or tool_call_id not in pending_tool_ids
                ):
                    return False

                pending_tool_ids.remove(tool_call_id)

            else:

                # 工具调用尚未完成时，不允许插入其他角色消息
                if pending_tool_ids:
                    return False

        return not pending_tool_ids


    try:
        def history_size(items):
            return len(
                json.dumps(items, ensure_ascii=False)
            )

        # 记录允许保留的最近若干轮起点
        first_allowed = max(
            0,
            len(user_rounds) - max_rounds
        )

        candidate_starts = user_rounds[first_allowed:]

        # 从保留轮数最多的候选开始检查
        for start_index in candidate_starts:

            candidate_conversation = conversation[start_index:]

            candidate_messages = (
                system_messages + candidate_conversation
            )

            # 先检查工具调用是否完整
            if not tool_calls_are_complete(candidate_conversation):
                continue

            # 再检查长度是否符合限制
            if history_size(candidate_messages) <= max_chars:
                return candidate_messages

        # 如果最近一轮工具调用不完整，保留原始历史
        latest_conversation = conversation[user_rounds[-1]:]

        if not tool_calls_are_complete(latest_conversation):
            print("[提示] 最近一轮工具调用不完整，已停止裁剪。")
            return messages

        # 最新一轮超过长度限制时，仍然保留最新一轮
        latest_messages = system_messages + latest_conversation

        print("[提示] 最近一轮对话超过长度限制，已保留最新一轮。")

        return latest_messages

    except (TypeError, ValueError) as e:
        print(f"[提示] 计算对话历史长度失败，已停止裁剪：{e}")
        return messages


def ask_ai(messages):
    tool_call_count = 0
    tool_failure_count = 0
    tool_success_count = 0

    force_calculator = False
    stop_tool_calls = False

    if not API_KEY:
        print("AI：没有配置 DEEPSEEK_API_KEY。")
        return False
    if not isinstance(messages, list) or not messages:
        print("AI：没有可处理的消息。")
        return False
    if not isinstance(messages[-1], dict):
        print("AI：最后一条消息格式不正确。")
        return False
    if not all(isinstance(item, dict) for item in messages):
        print("AI：对话历史包含无效消息。")
        return False

    user_text = messages[-1].get("content", "")
    if not isinstance(user_text, str):
        user_text = ""

    need_task_plan = any(
        word in user_text
        for word in ("制定计划", "帮我规划", "分步骤", "完成项目", "开发一个")
    )
    
    task_state = {
        "status": "running",
        "current_step": None,
        "completed_steps": [],
        "failed_steps": []
    }
    
    task_plan = {
        "goal": user_text,
        "status": "pending",
        "steps": []
    }
    previous_results = []

    if need_task_plan:
        task_plan = generate_task_plan(task_plan["goal"])
        
        if (
            isinstance(task_plan, dict)
            and isinstance(task_plan.get("steps"), list)
            and len(task_plan["steps"]) > 0
            and all(
                isinstance(step, dict)
                and isinstance(step.get("name"), str)
                and isinstance(step.get("status"), str)
                for step in task_plan["steps"]
            )
        ):
            print("\n[AI 自动生成的任务清单]")
            
            for index, step in enumerate(task_plan["steps"], start=1):
                print(f"{index}. {step['name']} [{step['status']}]")
            for step in task_plan["steps"]:
                if step["status"] != "pending":
                    continue

                task_state["current_step"] = step["name"]

                result = execute_task_step(step, previous_results)

                previous_results.append({
                    "step": step["name"],
                    "result": result
                })

                if step["status"] == "failed":
                    task_state["failed_steps"].append(step["name"])
                else:
                    task_state["completed_steps"].append(step["name"])

            task_state["current_step"] = None

            is_valid, problems = check_task_plan(task_plan)

            if not is_valid:
                task_plan["status"] = "completed_with_errors"

                print("\n[任务检查结果]")
                for problem in problems:
                    print(f"- {problem}")

            elif task_state["failed_steps"]:
                task_plan["status"] = "completed_with_errors"

            else:
                task_plan["status"] = "completed"
                print("\n[任务检查结果]")
                print("所有任务步骤检查通过！")
        
        else:
            task_plan = None
            task_state["status"] = "completed_with_errors"

            task_state["current_step"] = None
            task_state["failed_steps"].append("任务计划生成失败")

            print("\n[任务执行结果]")
            print("任务计划生成失败，无法执行任务。")


    if messages and messages[-1].get("role") == "user":
        user_text = messages[-1].get("content", "")

        if isinstance(user_text, str):
            
            calculation_keywords = (
                "计算", "算一下", "算出", "多少等于",
                "乘以", "除以", "加上", "减去"
            )

            if (
                any(word in user_text for word in calculation_keywords)
                and not any(word in user_text for word in ("计划", "总结", "然后", "再"))
):
                force_calculator = True
                
                
    if need_task_plan:
        plan_status = (
            task_plan.get("status", "未知")
            if isinstance(task_plan, dict)
            else "任务计划生成失败"
        )

        summary_prompt = (
            f"{'任务计划已经执行结束' if isinstance(task_plan, dict) else '任务计划生成失败，无法执行具体步骤'}。请根据以下真实执行记录，"
            "生成一份中文最终总结。\n\n"
            f"整体执行情况：{plan_status}\n"
            f"成功步骤：{task_state['completed_steps']}\n"
            f"失败步骤：{task_state['failed_steps']}\n"
            f"各步骤执行结果：{previous_results}\n\n"
            "总结必须包含：整体执行情况、成功步骤及结果、"
            "失败步骤及原因。不要编造执行结果。"
        )

        messages.append({
            "role": "user",
            "content": "[内部任务总结请求]\n" + summary_prompt
        })

    session = requests.Session()
    session.trust_env = False
    for _ in range(5):
        try:
            
            for attempt in range(3):
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
                            "tools": TOOLS,
                           "tool_choice": (
                                            "none"
                                            if need_task_plan
                                            else (
                                                {
                                                "type": "function",
                                                "function": {"name": "calculator"}
                                                }
                                                if force_calculator
                                                else "auto"
                                                )
                                            ),
                                                "stream": False
                        },
                        timeout=60
                    )
                    break

                except requests.RequestException as e:
                    if attempt == 2:
                        raise

                    print(
                        f"网络请求失败，准备重试 "
                        f"({attempt + 1}/2)：{e}"
                    )
                    wait_seconds = 2 ** (attempt + 1)
                    time.sleep(wait_seconds)

            if not response.ok:
                print("API 错误：", response.status_code)
                print(response.text[:1500])

                if need_task_plan:
                    task_state["status"] = "completed_with_errors"

                    if isinstance(task_plan, dict):
                        task_plan["status"] = "completed_with_errors"

                return False

            result = response.json()
            message = result["choices"][0]["message"]
            if not isinstance(message, dict):
                print("处理 API 返回内容时出错：assistant 消息格式不正确。")
                return False

            tool_calls = message.get("tool_calls") or []
            if not isinstance(tool_calls, list):
                print("处理 API 返回内容时出错：tool_calls 必须是列表。")
                return False
            tool_call_ids = set()
            for call in tool_calls:
                
                if call["id"] in tool_call_ids:
                    print("处理 API 返回内容时出错：工具调用 ID 重复。")
                    return False

                tool_call_ids.add(call["id"])
                if (
                    not isinstance(call, dict)
                    or not isinstance(call.get("id"), str)
                    or not call.get("id")
                    or not isinstance(call.get("function"), dict)
                    or not isinstance(call["function"].get("name"), str)
                    or not isinstance(call["function"].get("arguments"), str)
                ):
                    print("处理 API 返回内容时出错：工具调用结构不正确。")
                    return False

            # 如果 AI 不需要工具，直接回答
            
            
            
            if not tool_calls:
                task_state["current_step"] = None

                if (
                    task_state["failed_steps"]
                    or (
                        isinstance(task_plan, dict)
                        and task_plan.get("status") == "completed_with_errors"
                    )
                ):
                    task_state["status"] = "completed_with_errors"
                else:
                    task_state["status"] = "completed"
                answer = message.get("content")

                if not isinstance(answer, str) or not answer.strip():
                    if need_task_plan:
                        task_state["status"] = "completed_with_errors"
                        if isinstance(task_plan, dict):
                            task_plan["status"] = "completed_with_errors"
                        answer = "最终总结生成失败：AI 返回了空内容。"
                    else:
                        answer = "本轮没有文本回答。"
                
                print("\n[任务执行状态]")
                print(f"状态：{task_state['status']}")
                print(f"当前步骤：{task_state['current_step']}")
                print(f"已完成步骤：{task_state['completed_steps']}")
                print(f"失败步骤：{task_state['failed_steps']}")
                print("\nAI：", answer or "本轮没有文本回答。")

                messages.append({
                    "role": "assistant",
                    "content": answer or ""
                })
                
                print(f"工具调用总次数：{tool_call_count}")
                print(f"工具失败总次数：{tool_failure_count}")
                print(f"工具成功总次数：{tool_success_count}")

                if tool_call_count > 0:
                    success_rate = tool_success_count / tool_call_count * 100
                    print(f"工具成功率：{success_rate:.1f}%")
                else:
                    print("工具成功率：暂无数据")
                return True
            
            
            # 强制计算模式只允许调用一个计算器工具
            if force_calculator and (
                len(tool_calls) != 1
                or tool_calls[0]["function"]["name"] != "calculator"
            ):
                print("AI：计算器调用结构不正确，已停止本轮执行。")
                return False

            

            # 保存 AI 的工具调用请求
            messages.append(message)

            # 执行每一个工具调用
            for index, call in enumerate(tool_calls):
                if tool_call_count >= 10:
                    print("工具调用总次数已达上限（10 次），已停止执行。")
                    stop_tool_calls = True

                    for remaining_call in tool_calls[index:]:
                        messages.append({
                            "role": "tool",
                            "tool_call_id": remaining_call["id"],
                            "content": "工具调用失败：本轮工具调用次数已达到 10 次上限。"
                        })

                    break

                name = call["function"]["name"]
                tool_call_count += 1
                task_state["current_step"] = name
                
                tool_failed = False
                arguments = {}
                try:
                    arguments = json.loads(
                    call["function"]["arguments"]
                )

                    if not isinstance(arguments, dict):
                        tool_failed = True
                        tool_result = "工具参数格式错误，必须是对象。"
                    else:
                        tool_result = run_tool(name, arguments)
                        

                
                except ZeroDivisionError:
                    tool_failed = True 
                    tool_result = "计算失败：不能除以零。"
                
                
                except OverflowError:
                    tool_failed = True
                    tool_result = "计算失败：数值超出可计算范围。"
                
                except ValueError as e:
                    tool_failed = True
                    if name == "calculator":
                        tool_result = f"计算失败：{e}"
                    else:
                        tool_result = "工具参数不正确，无法执行。"

                except (KeyError, TypeError):
                    tool_failed = True
                    tool_result = "工具参数不正确，无法执行。"

                


                print(f"\n[AI 调用工具：{name}]")

                # 把工具结果交还给 AI
                
                print(f"\n[工具记录] 工具名称：{name}")
                status = (
                    "失败"
                    if (
                        tool_failed
                        or str(tool_result).startswith("错误：")
                        or str(tool_result).startswith("计算失败：")
                        or (
                            name == "process_batch_summaries"
                            and (
                            "错误：" in str(tool_result)
                            or "处理失败：" in str(tool_result)
                            )
                        )
                    )
                    else "成功"
                )
                if status == "失败":
                    tool_failure_count += 1
                else:
                    tool_success_count += 1
                    
                if status == "失败":
                    task_state["failed_steps"].append(name)
                else:
                    task_state["completed_steps"].append(name)

                print(f"[工具记录] 执行状态：{status}")
                print(f"[工具记录] 执行结果：{tool_result}")
                
                
                save_tool_log(name, arguments, status, tool_result)
                
                
                if isinstance(tool_result, str) and tool_result.startswith("错误："):
                    tool_result = tool_result.replace("错误：计算失败，不能除以零。", "计算失败，不能除以零。")
                

                
                messages.append({
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": str(tool_result)
                })
                
                if force_calculator and name == "calculator":
                    if tool_failed or str(tool_result).startswith("错误：") or str(tool_result).startswith("计算失败："):
                        error_text = str(tool_result)
                        if error_text.startswith("计算失败："):
                            print("\nAI：" + error_text)
                        elif error_text.startswith("错误：计算失败。"):
                            print("\nAI：计算失败，" + error_text.removeprefix("错误：计算失败。"))
                        else:
                            print("\nAI：计算失败，" + error_text)
                    else:
                        print("\nAI：计算结果是 " + str(tool_result))

                    return status == "成功"
                

            if stop_tool_calls:
                print("本轮工具调用已停止。")
                return False
        except requests.RequestException as e:
            print("网络请求失败：", e)
            return False

        except (KeyError, ValueError, IndexError, TypeError, AttributeError) as e:
            print("处理 API 返回内容时出错：", e)
            return False

    print("工具调用轮数已达上限，请尝试简化问题。")
    return False