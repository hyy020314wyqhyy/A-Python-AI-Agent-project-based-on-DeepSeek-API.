# -*- coding: utf-8 -*-

import os
import json
import re
import time
from datetime import datetime

import requests

from config import BASE_DIR, TOOL_LOG_FILE



def sanitize_sensitive_data(data):
    """对日志中的常见敏感信息进行脱敏。"""
    import re

    sensitive_names = (
        "api_key",
        "apikey",
        "authorization",
        "access_token",
        "refresh_token",
        "password",
        "secret"
    )

    if isinstance(data, dict):
        sanitized_data = {}

        for key, value in data.items():
            if isinstance(key, str) and any(
                name in key.lower() for name in sensitive_names
            ):
                sanitized_data[key] = "[已脱敏]"
            else:
                sanitized_data[key] = sanitize_sensitive_data(value)

        return sanitized_data

    if isinstance(data, list):
        return [
            sanitize_sensitive_data(item)
            for item in data
        ]

    if isinstance(data, str):
        # 保护 Bearer Token
        data = re.sub(
            r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+",
            "Bearer [已脱敏]",
            data
        )

        # 保护常见 sk- 开头的 API Key
        data = re.sub(
            r"\bsk-[A-Za-z0-9_-]{8,}\b",
            "[已脱敏]",
            data
        )

        # 保护带有敏感字段名称的内容
        data = re.sub(
            r"""(?i)(api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret)\s*[:=]\s*["']?([^\s,"']+)""",
            r"\1=[已脱敏]",
            data
        )

        return data

    return data


def save_tool_log(name, arguments, status, result):
    """脱敏并限制大小后安全追加工具日志。"""

    safe_arguments = sanitize_sensitive_data(arguments)

    # 不记录可能包含个人内容的参数
    if isinstance(safe_arguments, dict):
        safe_arguments = safe_arguments.copy()

        private_fields = (
            "content",
            "summary",
            "keyword"
        )

        for key in safe_arguments:
            if key.lower() in private_fields:
                safe_arguments[key] = "[内容未记录]"

    # 这些工具的结果可能包含文件全文或个人内容
    private_tools = (
        "read_text_file",
        "search_text_files",
        "write_text_file",
        "summarize_text_file",
        "save_text_summary",
        "process_batch_summaries"
    )

    if name in private_tools:
        safe_result = "[结果内容未记录，可能包含文件内容]"
    else:
        safe_result = sanitize_sensitive_data(str(result))

        # 限制普通工具结果的日志长度
        if len(safe_result) > 2000:
            safe_result = safe_result[:2000] + "...[内容已截断]"

    log = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tool": str(name),
        "arguments": safe_arguments if isinstance(safe_arguments, dict) else {},
        "status": str(status),
        "result": safe_result
    }

    logs = []
    temp_file = TOOL_LOG_FILE + ".save.tmp"
    created_temp_file = False

    max_log_size = 5 * 1024 * 1024

    try:
        if os.path.lexists(TOOL_LOG_FILE):
            if os.path.islink(TOOL_LOG_FILE) or not os.path.isfile(TOOL_LOG_FILE):
                print("工具日志保存失败：日志路径不是安全的普通文件。")
                return

            if os.path.getsize(TOOL_LOG_FILE) > max_log_size:
                print("工具日志保存失败：现有日志超过5MB。")
                return

            with open(TOOL_LOG_FILE, "r", encoding="utf-8") as f:
                logs = json.load(f)

            if not isinstance(logs, list) or not all(
                isinstance(item, dict) for item in logs
            ):
                print("工具日志保存失败：现有日志格式不正确，未覆盖原文件。")
                return

        if os.path.lexists(temp_file):
            print("工具日志保存失败：日志保存临时文件已经存在，请先检查。")
            return

        logs.append(log)

        # 先生成完整 JSON，再检查最终文件大小
        json_data = json.dumps(
            logs,
            ensure_ascii=False,
            indent=4
        )

        if len(json_data.encode("utf-8")) > max_log_size:
            print("工具日志保存失败：追加后日志将超过5MB，未保存。")
            return

        with open(temp_file, "x", encoding="utf-8") as f:
            created_temp_file = True
            f.write(json_data)
            f.flush()
            os.fsync(f.fileno())

        os.replace(temp_file, TOOL_LOG_FILE)
        created_temp_file = False

    except (
        OSError,
        json.JSONDecodeError,
        UnicodeDecodeError,
        UnicodeEncodeError,
        TypeError,
        ValueError
    ) as e:

        if created_temp_file and os.path.lexists(temp_file):
            try:
                os.remove(temp_file)
            except OSError:
                pass

        print(f"工具日志保存失败：{e}")


def sanitize_csv_value(value):
    """防止 CSV 内容被电子表格误识别为公式。"""
    value = str(value)

    check_value = value.lstrip()
    check_value = check_value.lstrip("\ufeff").lstrip()

    if check_value.startswith(("=", "+", "-", "@")):
        return "'" + value

    return value


def clear_tool_logs():
    if os.path.islink(TOOL_LOG_FILE):
        print("AI：工具日志不能是符号链接，已拒绝清空。")
        return
    if not os.path.exists(TOOL_LOG_FILE):
        print("AI：目前没有需要清空的日志。")
        return
    if not os.path.isfile(TOOL_LOG_FILE):
        print("AI：工具日志路径不是普通文件，已拒绝清空。")
        return

    confirm = input("确定要清空所有工具日志吗？请输入 yes 确认：").strip().lower()
    if confirm != "yes":
        print("AI：已取消清空操作。")
        return

    temp_file = TOOL_LOG_FILE + ".clear.tmp"
    created_temp_file = False
    try:
        if os.path.lexists(temp_file):
            print("AI：日志清空临时文件已经存在，请先检查。")
            return
        with open(temp_file, "x", encoding="utf-8") as f:
            created_temp_file = True
            json.dump([], f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_file, TOOL_LOG_FILE)
        created_temp_file = False
        print("AI：工具日志已经清空。")
    except (OSError, UnicodeEncodeError, TypeError) as e:
        print(f"AI：清空工具日志失败：{e}")
    finally:
        if created_temp_file and os.path.lexists(temp_file):
            try:
                os.remove(temp_file)
            except OSError:
                pass


def show_tool_logs():
    if os.path.islink(TOOL_LOG_FILE):
        print("AI：工具日志不能是符号链接，无法显示。")
        return
    if not os.path.exists(TOOL_LOG_FILE):
        print("AI：目前还没有工具调用记录。")
        return
    try:
        if not os.path.isfile(TOOL_LOG_FILE):
            print("AI：工具日志路径不是普通文件，无法显示。")
            return
        if os.path.getsize(TOOL_LOG_FILE) > 5 * 1024 * 1024:
            print("AI：工具日志超过5MB，无法显示。")
            return
        with open(TOOL_LOG_FILE, "r", encoding="utf-8") as f:
            logs = json.load(f)
        if not isinstance(logs, list) or not logs:
            print("AI：目前还没有工具调用记录。")
            return
        if not all(isinstance(log, dict) for log in logs):
            print("AI：工具日志格式不正确，无法显示。")
            return
        print("\n===== 最近 10 条工具调用记录 =====")
        for log in logs[-10:]:
            print(f"\n时间：{log.get('time', '未知')}")
            print(f"工具：{log.get('tool', '未知')}")
            print(f"状态：{log.get('status', '未知')}")
            print(f"参数：{log.get('arguments', {})}")
            print(f"结果：{log.get('result', '未知')}")
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
        print(f"AI：读取工具日志失败：{e}")


def export_tool_logs():
    import csv

    if not os.path.isdir(BASE_DIR):
        print("AI：导出目录不存在或不是有效目录。")
        return

    if not os.access(BASE_DIR, os.W_OK):
        print("AI：导出目录没有写入权限，无法导出。")
        return

    if os.path.islink(TOOL_LOG_FILE):
        print("AI：原始日志文件不能是符号链接，无法导出。")
        return

    if os.path.exists(TOOL_LOG_FILE) and not os.path.isfile(TOOL_LOG_FILE):
        print("AI：原始日志路径不是普通文件，无法导出。")
        return

    if os.path.dirname(os.path.realpath(TOOL_LOG_FILE)) != os.path.realpath(BASE_DIR):
        print("AI：原始日志文件路径不安全，无法导出。")
        return

    if not os.path.exists(TOOL_LOG_FILE):
        print("AI：目前没有可以导出的工具日志。")
        return

    if not os.access(TOOL_LOG_FILE, os.R_OK):
        print("AI：原始日志文件没有读取权限，无法导出。")
        return

    temp_file = None
    created_temp_file = False

    try:
        if os.path.getsize(TOOL_LOG_FILE) > 5 * 1024 * 1024:
            print("AI：工具日志文件超过5MB，无法导出。")
            return

        with open(TOOL_LOG_FILE, "r", encoding="utf-8") as f:
            logs = json.load(f)

        if not isinstance(logs, list) or not logs:
            print("AI：目前没有可以导出的工具日志。")
            return

        if not all(isinstance(log, dict) for log in logs):
            print("AI：工具日志格式不正确，无法导出。")
            return

        required_fields = {
            "time",
            "tool",
            "arguments",
            "status",
            "result"
        }

        if not all(required_fields.issubset(log.keys()) for log in logs):
            print("AI：工具日志缺少必要字段，无法导出。")
            return

        if not all(
            isinstance(log.get("time"), str)
            and isinstance(log.get("tool"), str)
            and isinstance(log.get("arguments"), dict)
            and isinstance(log.get("status"), str)
            and isinstance(log.get("result"), str)
            for log in logs
        ):
            print("AI：工具日志字段类型不正确，无法导出。")
            return

        export_file = os.path.join(BASE_DIR, "tool_logs_export.csv")

        protected_files = {
            os.path.abspath(TOOL_LOG_FILE + ".save.tmp"),
            os.path.abspath(TOOL_LOG_FILE + ".restore.tmp")
        }

        if os.path.abspath(export_file) in protected_files:
            print("AI：导出文件与系统临时文件冲突，无法导出。")
            return

        if os.path.islink(export_file):
            print("AI：导出路径不能是符号链接，无法导出。")
            return

        if os.path.dirname(os.path.realpath(export_file)) != os.path.realpath(BASE_DIR):
            print("AI：导出文件路径不安全，无法导出。")
            return

        if os.path.exists(export_file) and not os.path.isfile(export_file):
            print("AI：导出路径不是普通文件，无法导出。")
            return

        if os.path.exists(export_file) and not os.access(export_file, os.W_OK):
            print("AI：现有导出文件没有写入权限，无法导出。")
            return

        if os.path.abspath(export_file) == os.path.abspath(TOOL_LOG_FILE):
            print("AI：导出文件不能与原始日志文件相同。")
            return

        if os.path.exists(export_file) and os.path.getsize(export_file) > 5 * 1024 * 1024:
            print("AI：现有导出文件超过5MB，无法覆盖。")
            return

        temp_file = export_file + ".tmp"

        protected_temp_files = {
            os.path.abspath(TOOL_LOG_FILE + ".save.tmp"),
            os.path.abspath(TOOL_LOG_FILE + ".restore.tmp")
        }

        if os.path.abspath(temp_file) in protected_temp_files:
            print("AI：导出临时文件与系统临时文件冲突，无法导出。")
            return

        if os.path.abspath(temp_file) == os.path.abspath(export_file):
            print("AI：临时文件不能与正式导出文件相同。")
            return

        if os.path.dirname(os.path.realpath(temp_file)) != os.path.realpath(BASE_DIR):
            print("AI：导出临时文件路径不安全，无法导出。")
            return

        if os.path.islink(temp_file):
            print("AI：导出临时文件不能是符号链接，无法导出。")
            return

        if os.path.exists(temp_file) and not os.path.isfile(temp_file):
            print("AI：导出临时路径不是普通文件，无法导出。")
            return

        if os.path.exists(temp_file) and not os.access(temp_file, os.W_OK):
            print("AI：导出临时文件没有写入权限，无法导出。")
            return

        if os.path.exists(temp_file) and not os.access(temp_file, os.R_OK):
            print("AI：导出临时文件没有读取权限，无法导出。")
            return

        # 临时文件已经存在时，停止导出，不覆盖原文件
        if os.path.lexists(temp_file):
            print("AI：导出临时文件已经存在，请先检查并处理该文件。")
            return

        # 使用 x 模式创建新文件，避免覆盖已有文件
        with open(temp_file, "x", newline="", encoding="utf-8-sig") as f:
            created_temp_file = True

            writer = csv.writer(f)

            writer.writerow(["时间", "工具", "状态", "参数", "结果"])

            for log in logs:
                writer.writerow([
                    sanitize_csv_value(log.get("time", "")),
                    sanitize_csv_value(log.get("tool", "")),
                    sanitize_csv_value(log.get("status", "")),
                    sanitize_csv_value(
                        json.dumps(
                            sanitize_sensitive_data(log.get("arguments", {})),
                            ensure_ascii=False
                        )
                    ),
                    sanitize_csv_value(
                        sanitize_sensitive_data(log.get("result", ""))
                    )
                ])

                f.flush()

                if os.path.getsize(temp_file) > 5 * 1024 * 1024:
                    raise OSError("导出的 CSV 文件超过5MB。")

        os.replace(temp_file, export_file)
        created_temp_file = False

        print(f"AI：日志导出成功！文件位置：{export_file}")

    except (
        json.JSONDecodeError,
        OSError,
        UnicodeDecodeError,
        UnicodeEncodeError,
        csv.Error
    ) as e:

        # 只清理本次导出创建的临时文件
        if created_temp_file and os.path.lexists(temp_file):
            try:
                os.remove(temp_file)
            except OSError:
                pass

        print(f"AI：导出工具日志失败：{e}")


def backup_tool_logs():
    if os.path.islink(TOOL_LOG_FILE):
        print("AI：工具日志不能是符号链接，无法备份。")
        return
    if not os.path.exists(TOOL_LOG_FILE):
        print("AI：目前没有可以备份的工具日志。")
        return

    try:
        import shutil
        if not os.path.isfile(TOOL_LOG_FILE):
            print("AI：工具日志路径不是普通文件，无法备份。")
            return
        if os.path.getsize(TOOL_LOG_FILE) > 5 * 1024 * 1024:
            print("AI：工具日志超过5MB，无法备份。")
            return
        with open(TOOL_LOG_FILE, "r", encoding="utf-8") as f:
            logs = json.load(f)
        required_fields = {"time", "tool", "arguments", "status", "result"}
        if not isinstance(logs, list) or not all(isinstance(log, dict) for log in logs):
            print("AI：工具日志格式不正确，无法备份。")
            return
        if not all(required_fields.issubset(log.keys()) for log in logs):
            print("AI：工具日志缺少必要字段，无法备份。")
            return
        if not all(
            isinstance(log.get("time"), str)
            and isinstance(log.get("tool"), str)
            and isinstance(log.get("arguments"), dict)
            and isinstance(log.get("status"), str)
            and isinstance(log.get("result"), str)
            for log in logs
        ):
            print("AI：工具日志字段类型不正确，无法备份。")
            return

        backup_time = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup_file = os.path.join(BASE_DIR, f"tool_logs_backup_{backup_time}.json")
        if os.path.lexists(backup_file):
            print("AI：备份目标已经存在，已停止备份。")
            return
        shutil.copy2(TOOL_LOG_FILE, backup_file)
        print("AI：日志备份成功！")
        print(f"备份位置：{backup_file}")
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as e:
        print(f"AI：日志备份失败：{e}")


def restore_tool_logs():
    if not os.path.isdir(BASE_DIR):
        print("AI：日志备份目录不存在或不是有效目录。")
        return

    if not os.access(BASE_DIR, os.W_OK):
        print("AI：导出目录没有写入权限，无法恢复。")
        return

    try:
        backup_files = [
            name for name in os.listdir(BASE_DIR)
            if name.startswith("tool_logs_backup_") and name.endswith(".json")
        ]
    except OSError as e:
        print(f"AI：读取日志备份目录失败：{e}")
        return

    if not backup_files:
        print("AI：没有找到日志备份文件。")
        return

    backup_files.sort(reverse=True)

    temp_file = TOOL_LOG_FILE + ".restore.tmp"

    if os.path.dirname(os.path.realpath(temp_file)) != os.path.realpath(BASE_DIR):
        print("AI：恢复临时文件路径不安全，无法继续恢复。")
        return

    if os.path.lexists(temp_file):
        try:
            if os.path.islink(temp_file):
                print("AI：恢复临时文件是符号链接，无法继续恢复。")
                return

            if not os.path.isfile(temp_file):
                print("AI：恢复临时路径不是有效文件，无法继续恢复。")
                return

            if os.path.getsize(temp_file) > 5 * 1024 * 1024:
                print("AI：恢复临时文件超过5MB，无法继续恢复。")
                return

            print("AI：恢复临时文件已经存在，请先检查并处理该文件。")
            return

        except OSError as e:
            print(f"AI：检查恢复临时文件失败：{e}")
            return

    for backup_name in backup_files:
        backup_file = os.path.join(BASE_DIR, backup_name)

        if os.path.abspath(backup_file) == os.path.abspath(TOOL_LOG_FILE):
            print("AI：目标日志文件不能作为备份文件恢复，尝试其他备份。")
            continue

        if os.path.islink(backup_file):
            print("AI：备份文件是符号链接，尝试其他备份。")
            continue

        if os.path.dirname(os.path.realpath(backup_file)) != os.path.realpath(BASE_DIR):
            print("AI：备份文件路径不安全，尝试其他备份。")
            continue

        if not os.path.isfile(backup_file):
            print("AI：备份路径不是有效文件，尝试其他备份。")
            continue

        try:
            if os.path.getsize(backup_file) > 5 * 1024 * 1024:
                print("AI：备份文件超过5MB，尝试其他备份。")
                continue

        except OSError as e:
            print(f"AI：检查备份文件大小失败，尝试其他备份：{e}")
            continue

        created_temp_file = False

        try:
            with open(backup_file, "r", encoding="utf-8") as f:
                logs = json.load(f)

            if not isinstance(logs, list):
                print("AI：备份文件格式不正确，尝试其他备份。")
                continue

            if not all(isinstance(log, dict) for log in logs):
                print("AI：备份文件记录格式不正确，尝试其他备份。")
                continue

            required_fields = {
                "time",
                "tool",
                "arguments",
                "status",
                "result"
            }

            if not all(required_fields.issubset(log.keys()) for log in logs):
                print("AI：备份文件缺少必要字段，尝试其他备份。")
                continue

            if not all(
                isinstance(log.get("time"), str)
                and isinstance(log.get("tool"), str)
                and isinstance(log.get("arguments"), dict)
                and isinstance(log.get("status"), str)
                and isinstance(log.get("result"), str)
                for log in logs
            ):
                print("AI：备份文件字段类型不正确，尝试其他备份。")
                continue

            confirm = input(
                f"即将从 {backup_name} 恢复日志，"
                "当前日志将被覆盖。输入 yes 确认："
            ).strip().lower()

            if confirm != "yes":
                print("AI：已取消恢复操作。")
                return

            # 恢复历史日志前，再次进行敏感信息脱敏
            logs = sanitize_sensitive_data(logs)

            # 使用 x 模式，避免覆盖已有临时文件
            with open(temp_file, "x", encoding="utf-8") as f:
                created_temp_file = True
                json.dump(logs, f, ensure_ascii=False, indent=4)

            os.replace(temp_file, TOOL_LOG_FILE)
            created_temp_file = False

            print(f"AI：日志恢复成功，共恢复 {len(logs)} 条记录。")
            return

        except FileExistsError:
            if created_temp_file and os.path.lexists(temp_file):
                try:
                    os.remove(temp_file)
                except OSError:
                    pass

            print("AI：恢复临时文件已经存在，无法继续恢复。")
            return

        except (
            json.JSONDecodeError,
            OSError,
            UnicodeDecodeError,
            UnicodeEncodeError,
            TypeError
        ) as e:

            if created_temp_file and os.path.lexists(temp_file):
                try:
                    os.remove(temp_file)
                except OSError:
                    pass

            print(f"AI：恢复日志失败，尝试其他备份：{e}")
            continue

    print("AI：所有日志备份均无法恢复。")


def show_tool_log_stats():
    """统计工具调用日志：按工具名和状态汇总。"""
    if not os.path.exists(TOOL_LOG_FILE):
        print("还没有工具调用日志。")
        return

    try:
        with open(TOOL_LOG_FILE, "r", encoding="utf-8") as f:
            logs = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"日志读取失败：{e}")
        return

    if not isinstance(logs, list) or not logs:
        print("还没有工具调用日志。")
        return

    total = len(logs)
    by_tool = {}
    by_status = {}
    for log in logs:
        if not isinstance(log, dict):
            continue
        tool = str(log.get("tool", "未知"))
        status = str(log.get("status", "未知"))
        by_tool[tool] = by_tool.get(tool, 0) + 1
        by_status[status] = by_status.get(status, 0) + 1

    print(f"工具调用总次数：{total}")

    print("\n按工具统计：")
    for name, count in sorted(by_tool.items(), key=lambda x: -x[1]):
        print(f"  {name}: {count} 次")

    print("\n按状态统计：")
    for status, count in sorted(by_status.items(), key=lambda x: -x[1]):
        print(f"  {status}: {count} 次")