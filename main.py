# -*- coding: utf-8 -*-

import os
import json
import re
import time
from datetime import datetime

import requests


# -*- coding: utf-8 -*-

from config import API_KEY

from ai_client import (
    ask_ai,
    build_system_prompt,
    refresh_system_prompt,
    trim_conversation_history,
)

from file_manager import (
    get_text_file_stats,
    list_text_files,
    process_batch_summaries,
    process_single_file_summary,
    search_text_files,
)

from logger import (
    backup_tool_logs,
    clear_tool_logs,
    export_tool_logs,
    restore_tool_logs,
    show_tool_log_stats,
    show_tool_logs,
)

from memory import (
    add_memory,
    auto_save_memories,
    backup_memory,
    deduplicate_memory,
    delete_memory,
    load_memory,
    manage_memory_with_ai,
    might_manage_memory,
    restore_memory,
    save_memory,
    update_memory,
)


def main():
    if not API_KEY:
        print("没有读取到 DEEPSEEK_API_KEY。")
        print("请先在 PowerShell 中配置 API Key。")
        return

    # 读取长期记忆
    try:
        memory = load_memory()
    except RuntimeError as e:
        print("AI：", e)
        print("请检查 memory.json 文件后重新启动程序。")
        return

    # memory_text = (
    #     "\n".join(f"- {item}" for item in memory)
    #     if memory
    #     else "暂时没有已保存的记忆。"
    # )

    # 初始化对话，并让 AI 了解已有记忆
    # 初始化对话，并让 AI 了解已有记忆
    messages = [
        {
        "role": "system",
        "content": build_system_prompt(memory)
        }
    ]
    continuous_mode = False
    max_history_rounds = 10
    max_history_chars = 50000

    print("=" * 36)
    print("AI Agent 已启动！")
    print("输入 help 查看帮助，输入 exit 退出。")
    print("=" * 36)

    while True:
        try:
            print("\n你（输入 /done 结束）：")
            lines = []

            while True:
                line = input()

                if line.strip() == "/done":
                    break

                lines.append(line)

            user_text = "\n".join(lines).strip()

            if not user_text:
                print("请输入内容后再提交。")
                continue

        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not user_text:
            continue

        # 退出程序
        if user_text.lower() == "exit":
            print("再见！")
            break
        
                # 查看 TXT 文件
        if user_text.lower() == "listtxt":
            print(list_text_files())
            continue
        
        
        # 搜索 TXT 文件
        if user_text.split(maxsplit=1)[0].lower() == "searchtxt":
            parts = user_text.split(maxsplit=1)

            if len(parts) < 2:
                print("AI：请输入搜索关键词。示例：searchtxt Python")
            else:
                print(search_text_files(parts[1]))

            continue
        
        
        # 统计 TXT 文件
        if user_text.lower() == "txtstats":
            print(get_text_file_stats())
            continue
        
        
        # 生成单个 TXT 文件摘要
        if user_text.lower() == "summary" or user_text.lower().startswith("summary "):
            filename = user_text[len("summary "):].strip()

            if not filename:
                print("AI：请输入 TXT 文件名。示例：summary agent_test.txt")
            else:
                print(process_single_file_summary(filename))

            continue
        
        
        # 批量生成 TXT 文件摘要
        if user_text.lower() == "batchsummary":
            print(process_batch_summaries())
            continue





        
                # 查看工具调用日志
        if user_text.lower() == "logs":
            show_tool_logs()
            continue
        
                # 查看工具调用统计
        if user_text.lower() == "logstats":
            show_tool_log_stats()
            continue
        
                # 清空工具调用日志
        if user_text.lower() == "clearlogs":
            clear_tool_logs()
            continue
        
                # 导出工具调用日志
        if user_text.lower() == "exportlogs":
            export_tool_logs()
            continue
        
                # 备份工具调用日志
        if user_text.lower() == "backuplogs":
            backup_tool_logs()
            continue
        
                # 恢复工具调用日志
        if user_text.lower() == "restorelogs":
            restore_tool_logs()
            continue

        # 恢复长期记忆
        if user_text == "恢复记忆":
            restore_memory()
            continue

        # 保存长期记忆
        if user_text.startswith("记住：") or user_text.startswith("记住:"):
            item = user_text[3:].strip()

            if not item:
                print("AI：请在“记住：”后面写上需要保存的信息。")
                continue

            try:
                memory = load_memory()
            except RuntimeError as e:
                print("AI：", e)
                continue

            if item in memory:
                print("AI：这条信息已经记住了。")
            else:
                memory.append(item)

                if save_memory(memory):
                    print("AI：好的，这条信息已经保存到长期记忆。")

            continue


        # 新增长期记忆
        if user_text.startswith("新增记忆：") or user_text.startswith("新增记忆:"):
            item = user_text[len("新增记忆："):].strip() if "：" in user_text else user_text[len("新增记忆:"):].strip()
            print("AI：", add_memory(item))
            continue

        # 更新长期记忆，例如：更新记忆 1：用户正在学习 Python
        if user_text.startswith("更新记忆 "):
            try:
                command = user_text[len("更新记忆 "):]
                number_text, new_item = command.split("：", 1) if "：" in command else command.split(":", 1)
                number = int(number_text.strip())
                if number < 1 or number > len(load_memory()):
                    print("AI：编号不存在，请先输入“查看记忆”。")
                    continue
                confirm = input("确认更新这条记忆吗？输入 yes 才会更新：")

                if confirm.strip().lower() == "yes":
                    if backup_memory():
                        print("AI：", update_memory(number, new_item))
                    else:
                        print("AI：备份失败，已取消更新，原记忆保持不变。")
                else:
                    print("AI：已取消更新。")
            except RuntimeError as e:
                print("AI：", e)
            except (ValueError, TypeError):
                print("AI：格式不正确。示例：更新记忆 1：用户正在学习 Python")
            continue

        # 删除长期记忆，例如：删除记忆 2
        if user_text.startswith("删除记忆 "):
            try:
                number = int(user_text[len("删除记忆 "):].strip())
                if number < 1 or number > len(load_memory()):
                    print("AI：编号不存在，请先输入“查看记忆”。")
                    continue
                confirm = input(f"确定删除第 {number} 条记忆吗？输入 yes 确认：")


                if confirm.strip().lower() == "yes":
                    if backup_memory():
                        print("AI：", delete_memory(number))
                        refresh_system_prompt(messages)
                    else:
                        print("AI：备份失败，已取消删除，原记忆保持不变。")
                else:
                    print("AI：已取消删除。")

            except RuntimeError as e:
                print("AI：", e)
            except ValueError:
                print("AI：格式不正确。示例：删除记忆 2")
            continue

        # 清理重复记忆
        if user_text == "记忆去重":     
            confirm = input("确认清理重复记忆吗？输入 yes 才会清理：")

            if confirm.strip().lower() == "yes":
                if backup_memory():
                    print("AI：", deduplicate_memory())
                else:
                    print("AI：备份失败，已取消清理，原记忆保持不变。")
            else:
                print("AI：已取消清理。")

            continue



        # 查看长期记忆
        if (
            "记忆" in user_text
            and any(keyword in user_text for keyword in ("查看", "显示", "列出", "读取"))
        ):
            try:
                memory = load_memory()
            except RuntimeError as e:
                print("AI：", e)
                continue

            if memory:
                print("\nAI 已保存的记忆：")
                for i, item in enumerate(memory, start=1):
                    print(f"{i}. {item}")
            else:
                print("目前还没有保存任何记忆。")

            continue

        # 清空长期记忆
        if user_text == "清空记忆":
            try:
                load_memory()
            except RuntimeError as e:
                print("AI：", e)
                print("AI：记忆文件读取失败，已取消清空操作。")
                continue
            confirm = input(
                "确定清空所有长期记忆吗？输入 yes 确认："
            )

            if confirm.strip().lower() == "yes":
                if backup_memory():
                    if save_memory([]):
                        print("AI：长期记忆已清空。")
                    else:
                        print("AI：清空失败，请检查文件权限。")
                else:
                    print("AI：备份失败，已取消清空，原记忆保持不变。")
            else:
                print("AI：已取消。")

            continue

        # 帮助命令
        if user_text.lower() == "help":
            print("\n可用命令：")
            print("1. 现在几点了？")
            print("2. 帮我安排 30 分钟的 Python 学习计划。")
            print("3. 记住：我正在学习 Python。")
            print("4. 查看记忆")
            print("5. 恢复记忆")
            print("6. 清空记忆")
            print("7. exit")          
            print("8. listtxt - 查看 TXT 文件")
            print("9. searchtxt 关键词 - 搜索 TXT 文件")
            print("10. txtstats - 统计 TXT 文件")
            print("11. summary 文件名 - 生成单个文件摘要")
            print("12. batchsummary - 批量生成文件摘要")
            print("13. logs - 查看工具调用日志")
            print("14. logstats - 查看日志统计")
            print("15. clearlogs - 清空工具调用日志")
            print("16. exportlogs - 导出工具调用日志")
            print("17. backuplogs - 备份工具调用日志")
            print("18. restorelogs - 恢复工具调用日志")
            print("19. mode - 查看当前对话模式")
            print("20. chat - 切换到连续对话模式")
            print("21. normal - 切换到普通对话模式")

            continue
        
        # 查看当前对话模式
        if user_text.lower() == "mode":
            if continuous_mode:
                print("AI：当前是连续对话模式。")
            else:
                print("AI：当前是普通模式。")
            continue

        
             # 第 8 课：先判断是不是记忆管理请求
                # 第 9 课：只有疑似记忆管理请求才调用 AI
                
        # 切换对话模式
        
        
        if user_text.lower() == "chat":
            continuous_mode = True
            print("AI：已切换到连续对话模式，将保留对话上下文。")
            print(f"[调试] 已切换连续模式，continuous_mode={continuous_mode}，messages 数量={len(messages)}")
            continue

        if user_text.lower() == "normal":
            continuous_mode = False
            print("AI：已切换到普通模式，每次新问题将清除上一轮对话。")
            continue
        
        if might_manage_memory(user_text):
            if manage_memory_with_ai(user_text):
                refresh_system_prompt(messages)
                continue
        
        # 普通问题交给 AI
        if not continuous_mode:
            messages = messages[:1]
        else:
            print(f"[调试] 调用裁剪前，messages 总数：{len(messages)}")
            print(f"[调试] 调用裁剪前，用户消息数：{sum(1 for m in messages if m.get('role') == 'user')}")

            messages = trim_conversation_history(
                messages,
                max_history_rounds,
                max_history_chars
            )

        messages.append({
            "role": "user",
            "content": user_text
        })
        ai_success = ask_ai(messages)

        print(f"[调试] AI 回答后，messages 总数：{len(messages)}")
        print(f"[调试] 当前消息角色：{[m.get('role') for m in messages]}")
        for i, message in enumerate(messages):
            print(
            f"[调试] 消息 {i}: "
            f"role={message.get('role')}, "
            f"tool_call_id={message.get('tool_call_id')}, "
            f"tool_calls={len(message.get('tool_calls') or [])}"
        )

        if ai_success:
            auto_save_memories(user_text)
            refresh_system_prompt(messages)


if __name__ == "__main__":
    main()