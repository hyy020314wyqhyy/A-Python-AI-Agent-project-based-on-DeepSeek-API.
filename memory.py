# -*- coding: utf-8 -*-

import os
import json
import re
import time
from datetime import datetime

import requests

from config import API_KEY, API_URL, MEMORY_FILE, MODEL



def load_memory():
    """读取并验证长期记忆。"""
    if os.path.islink(MEMORY_FILE):
        raise RuntimeError("记忆文件不能是符号链接，已停止记忆操作。")

    if not os.path.exists(MEMORY_FILE):
        return []

    try:
        if not os.path.isfile(MEMORY_FILE):
            raise RuntimeError("记忆路径不是普通文件，已停止记忆操作。")
        if os.path.getsize(MEMORY_FILE) > 1024 * 1024:
            raise RuntimeError("记忆文件超过1MB，已停止记忆操作。")

        with open(MEMORY_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, list):
            raise RuntimeError("记忆文件格式不正确，预期内容是列表。")
        if not all(isinstance(item, str) for item in data):
            raise RuntimeError("记忆文件包含非文本数据，已停止记忆操作。")
        return data

    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
        raise RuntimeError("读取记忆文件失败，已停止记忆操作。") from e


def save_memory(memory):
    """检查记忆文件大小后，使用独占临时文件安全保存长期记忆。"""

    if not isinstance(memory, list):
        print("保存记忆失败：记忆内容必须是列表。")
        return False

    if not all(isinstance(item, str) for item in memory):
        print("保存记忆失败：每条记忆都必须是文本。")
        return False

    temp_file = MEMORY_FILE + ".save.tmp"
    created_temp_file = False

    max_memory_size = 1024 * 1024

    try:
        if os.path.islink(MEMORY_FILE):
            print("保存记忆失败：记忆文件不能是符号链接。")
            return False

        if os.path.lexists(temp_file):
            print("保存记忆失败：记忆临时文件已经存在，请先检查。")
            return False

        # 先生成完整 JSON 内容
        json_data = json.dumps(
            memory,
            ensure_ascii=False,
            indent=2
        )

        # 检查 UTF-8 编码后的实际字节数
        memory_size = len(json_data.encode("utf-8"))

        if memory_size > max_memory_size:
            print("保存记忆失败：记忆文件不能超过1MB。")
            return False

        # 使用独占方式创建临时文件，避免覆盖已有文件
        with open(temp_file, "x", encoding="utf-8") as file:
            created_temp_file = True
            file.write(json_data)
            file.flush()
            os.fsync(file.fileno())

        # 原子替换正式记忆文件
        os.replace(temp_file, MEMORY_FILE)
        created_temp_file = False

        return True

    except (OSError, TypeError, ValueError, UnicodeEncodeError) as e:
        print("保存记忆失败：", e)

        if created_temp_file and os.path.lexists(temp_file):
            try:
                os.remove(temp_file)
            except OSError:
                pass

        return False


def backup_memory():
    """在修改记忆前备份长期记忆文件。"""
    import os
    import shutil
    from datetime import datetime

    memory_file = MEMORY_FILE

    if os.path.islink(memory_file):
        print("备份记忆失败：记忆文件不能是符号链接。")
        return False
    if not os.path.exists(memory_file):
        print("备份提示：没有找到记忆文件：", os.path.abspath(memory_file))
        return False
    if not os.path.isfile(memory_file) or os.path.getsize(memory_file) > 1024 * 1024:
        print("备份记忆失败：记忆文件不是普通文件或超过1MB。")
        return False

    backup_file = (
        os.path.splitext(memory_file)[0]
        + "_backup_"
        + datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        + ".json"
    )

    try:
        shutil.copy2(memory_file, backup_file)

        with open(backup_file, "r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, list):
            print("备份验证失败：记忆文件格式不正确。")
            return False

        if not all(isinstance(item, str) for item in data):
            print("备份验证失败：记忆文件包含非文本数据。")
            return False

        print("记忆备份已保存并验证：", os.path.abspath(backup_file))
        return True

    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as e:
        print("记忆备份失败或验证失败：", e)
        return False


def restore_memory():
    """从已验证的长期记忆备份中安全恢复记忆。"""
    backup_dir = os.path.dirname(os.path.abspath(MEMORY_FILE))
    memory_prefix = os.path.splitext(os.path.basename(MEMORY_FILE))[0] + "_backup_"

    try:
        backup_files = [
            name for name in os.listdir(backup_dir)
            if name.startswith(memory_prefix) and name.endswith(".json")
        ]
    except OSError as e:
        print("AI：读取记忆备份目录失败：", e)
        return

    if not backup_files:
        print("AI：没有找到长期记忆备份文件。")
        return

    backup_files.sort(reverse=True)
    print("\n===== 可用的长期记忆备份 =====")
    for index, backup_name in enumerate(backup_files, start=1):
        print(f"{index}. {backup_name}")

    choice = input("请输入要恢复的备份编号（输入其他内容取消）：").strip()
    try:
        backup_number = int(choice)
    except ValueError:
        print("AI：已取消恢复操作。")
        return

    if backup_number < 1 or backup_number > len(backup_files):
        print("AI：备份编号不存在，已取消恢复操作。")
        return

    backup_file = os.path.join(backup_dir, backup_files[backup_number - 1])
    temp_file = MEMORY_FILE + ".restore.tmp"
    created_temp_file = False

    try:
        if os.path.islink(MEMORY_FILE):
            print("AI：当前记忆文件是符号链接，已取消恢复操作。")
            return
        if os.path.lexists(temp_file):
            print("AI：记忆恢复临时文件已经存在，请先检查并处理。")
            return
        if os.path.islink(backup_file):
            print("AI：备份文件不能是符号链接，已取消恢复操作。")
            return
        if os.path.dirname(os.path.realpath(backup_file)) != os.path.realpath(backup_dir):
            print("AI：备份文件路径不安全，已取消恢复操作。")
            return
        if not os.path.isfile(backup_file):
            print("AI：备份文件不存在或不是普通文件，已取消恢复操作。")
            return
        if os.path.getsize(backup_file) > 1024 * 1024:
            print("AI：备份文件超过1MB，无法恢复。")
            return

        with open(backup_file, "r", encoding="utf-8") as file:
            restored_memory = json.load(file)

        if not isinstance(restored_memory, list) or not all(
            isinstance(item, str) for item in restored_memory
        ):
            print("AI：备份文件格式不正确，无法恢复。")
            return

        print(f"\n准备从备份恢复 {len(restored_memory)} 条记忆：")
        for index, item in enumerate(restored_memory, start=1):
            print(f"{index}. {item}")

        confirm = input("恢复后将覆盖当前长期记忆，输入 yes 确认：").strip().lower()
        if confirm != "yes":
            print("AI：已取消恢复操作。")
            return

        if os.path.exists(MEMORY_FILE) and not backup_memory():
            print("AI：当前记忆备份失败，已取消恢复，原记忆保持不变。")
            return

        with open(temp_file, "x", encoding="utf-8") as file:
            created_temp_file = True
            json.dump(restored_memory, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())

        with open(temp_file, "r", encoding="utf-8") as file:
            checked_memory = json.load(file)
        if checked_memory != restored_memory:
            print("AI：恢复文件验证失败，原记忆保持不变。")
            return

        os.replace(temp_file, MEMORY_FILE)
        created_temp_file = False
        print(f"AI：长期记忆恢复成功，共恢复 {len(restored_memory)} 条记忆。")

    except (OSError, json.JSONDecodeError, UnicodeDecodeError, UnicodeEncodeError, TypeError) as e:
        print("AI：恢复长期记忆失败，原记忆未主动覆盖：", e)
    finally:
        if created_temp_file and os.path.lexists(temp_file):
            try:
                os.remove(temp_file)
            except OSError:
                pass


def add_memory(item):
    """新增一条记忆。"""
    
    if not isinstance(item, str):
        return "记忆内容必须是文本。"
    
    item = item.strip()

    if not item:
        return "记忆内容不能为空。"

    try:
        memory = load_memory()
    except RuntimeError as e:
        return str(e)

    # 忽略首尾空格，并且不区分大小写地检查重复
    for old_item in memory:
        if old_item.strip().casefold() == item.casefold():
            return "这条记忆已经存在，不需要重复添加。"

    memory.append(item)

    if save_memory(memory):
        return f"已新增记忆：{item}"

    return "保存失败，请检查文件权限。"


def update_memory(number, new_item):
    """按照编号更新一条记忆。"""
    
    if not isinstance(number, int) or isinstance(number, bool):
        return "编号必须是整数。"
    try:
        memory = load_memory()
    except RuntimeError as e:
        return str(e)

    if not isinstance(new_item, str):
        return "新的记忆内容必须是文本。"
    new_item = new_item.strip()

    if not new_item:
        return "新的记忆内容不能为空。"


    if number < 1 or number > len(memory):
        return "编号不存在，请先输入“查看记忆”。"

    # 检查新内容是否与其他记忆重复
    for i, old_item in enumerate(memory):
        if i != number - 1:
            if old_item.strip().casefold() == new_item.casefold():
                return "更新失败：其他位置已经有相同记忆。"

    old_item = memory[number - 1]
    memory[number - 1] = new_item

    if save_memory(memory):
        return f"已更新记忆：\n原内容：{old_item}\n新内容：{new_item}"

    return "保存失败，请检查文件权限。"


def delete_memory(number):
    """按照编号删除一条记忆。"""
    if not isinstance(number, int) or isinstance(number, bool):
        return "编号必须是整数。"
    try:
        memory = load_memory()
    except RuntimeError as e:
        return str(e)

    if number < 1 or number > len(memory):
        return "编号不存在，请先输入“查看记忆”。"

    removed = memory.pop(number - 1)

    if save_memory(memory):
        return f"已删除记忆：{removed}"

    return "保存失败，请检查文件权限。"


def deduplicate_memory():
    """清除重复记忆，保留第一次出现的内容。"""
    try:
        memory = load_memory()
    except RuntimeError as e:
        return str(e)

    unique_memory = []
    seen = set()

    for item in memory:
        key = item.strip().casefold()

        for prefix in ("用户", "我"):
            if key.startswith(prefix):
                key = key[len(prefix):]
                break

        key = re.sub(r"[^\w]", "", key)

        if key and key not in seen:
            unique_memory.append(item.strip())
            seen.add(key)

    removed_count = len(memory) - len(unique_memory)

    if save_memory(unique_memory):
        return f"去重完成，清除了 {removed_count} 条重复或空白记忆。"

    return "保存失败，请检查文件权限。"


def might_manage_memory(user_text):
    """初步判断用户是否可能在管理长期记忆。"""

    keywords = [
        "记住",
        "记忆",
        "长期记忆",
        "新增记忆",
        "添加记忆",
        "更新记忆",
        "修改记忆",
        "删除记忆",
        "清理记忆",
        "去重"
    ]

    return any(keyword in user_text for keyword in keywords)


def manage_memory_with_ai(user_text):
    """理解自然语言，并安全地管理长期记忆。"""

    if not API_KEY:
        print("AI：没有配置 DEEPSEEK_API_KEY，无法识别记忆管理指令。")
        return True
    if not isinstance(user_text, str) or not user_text.strip():
        print("AI：记忆管理指令不能为空。")
        return True

    prompt = """
        你是一个长期记忆管理助手。
        请判断用户是否明确要求管理长期记忆。

        只返回合法 JSON，不要添加其他文字。

        新增记忆：
        {"action":"add","item":"要保存的完整记忆"}

        更新记忆：
        {"action":"update","number":1,"item":"更新后的完整记忆"}

        删除记忆：
        {"action":"delete","number":1}

        清理重复记忆：
        {"action":"deduplicate"}

        不是记忆管理请求：
        {"action":"none"}

        规则：
        1. 只处理明确的记忆新增、更新、删除或去重请求。
        2. 用户明确要求删除、移除或忘记某条记忆时，必须返回 action 为 delete，不能返回 update。
        3. 用户明确要求修改、更新或替换某条记忆，并提供新内容时，才返回 action 为 update。
        4. 删除操作只需要 number，不需要 item；更新操作必须同时提供 number 和 item。
        5. 不要猜测记忆编号。用户没有提供编号时，更新或删除操作返回 none。
        6. 更新操作必须包含明确的新内容。
        7. 不要把普通问题误判为记忆管理请求。
        8. 不要执行操作，只负责识别用户意图并返回 JSON。
        """

    try:
        
        session = requests.Session()
        session.trust_env = False
        response = session.post(
            API_URL,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_text}
                ],
                "stream": False
            },
            timeout=60
        )

        if not response.ok:
            print("记忆意图识别失败：", response.status_code)
            return False

        result = response.json()
        content = result["choices"][0]["message"].get("content", "")
        if not isinstance(content, str) or not content.strip():
            print("AI：记忆管理识别结果为空，未执行任何操作。")
            return True

        command = json.loads(content)
        if not isinstance(command, dict):
            print("AI：记忆管理识别结果格式不正确，未执行任何操作。")
            return True

        action = command.get("action")
        if not isinstance(action, str):
            print("AI：记忆管理操作类型无效，未执行任何操作。")
            return True

        # 不是记忆管理请求，交回原来的聊天程序
        if action == "none":
            return False

        # 新增记忆
        
        # 新增记忆
        if action == "add":
            item = command.get("item")

            if not isinstance(item, str) or not item.strip():
                print("AI：没有识别到有效的记忆内容。")
                return True

            try:
                memory = load_memory()
            except RuntimeError as e:
                print("AI：", e)
                return True

            if item.strip() in [old_item.strip() for old_item in memory]:
                print("AI：这条记忆已经存在，不重复添加。")
                return True

            print("AI：", add_memory(item))
            return True


        # 更新记忆

        if action == "update":
            number = command.get("number")
            item = command.get("item")

            if (
                not isinstance(number, int)
                or isinstance(number, bool)
                or not isinstance(item, str)
                or not item.strip()
            ):
                print("AI：更新信息不完整，请明确记忆编号和新内容。")
                return True

            try:
                memory = load_memory()
            except RuntimeError as e:
                print("AI：", e)
                return True

            if number < 1 or number > len(memory):
                print("AI：这个编号不存在，请先输入“查看记忆”。")
                return True

            old_item = memory[number - 1]

            print("原来的记忆：", old_item)
            print("准备更新为：", item)

            confirm = input("确认更新吗？输入 yes 才会更新：")

            if confirm.strip().lower() == "yes":
                if backup_memory():
                    print("AI：", update_memory(number, item))
                else:
                    print("AI：备份失败，已取消更新，原记忆保持不变。")
            else:
                print("AI：已取消更新。")

            return True


    # 删除记忆：必须经过用户确认
        if action == "delete":
            number = command.get("number")

            if (
                not isinstance(number, int)
                or isinstance(number, bool)
                or number < 1
            ):
                print("AI：请明确要删除的记忆编号。")
                return True

            try:
                memory = load_memory()
            except RuntimeError as e:
                print("AI：", e)
                return True

            if number > len(memory):
                print("AI：这个编号不存在，请先输入“查看记忆”。")
                return True

            print(f"准备删除第 {number} 条记忆：{memory[number - 1]}")
            confirm = input("确认删除吗？输入 yes 才会删除：")


            if confirm.strip().lower() == "yes":
                if backup_memory():
                    print("AI：", delete_memory(number))
                else:
                    print("AI：备份失败，已取消删除，原记忆保持不变。")
            else:
                print("AI：已取消删除。")


            return True

        # 清理重复记忆
        if action == "deduplicate":
            confirm = input("确认清理重复记忆吗？输入 yes 才会清理：")

            if confirm.strip().lower() == "yes":
                if backup_memory():
                    print("AI：", deduplicate_memory())
                else:
                    print("AI：备份失败，已取消清理，原记忆保持不变。")
            else:
                print("AI：已取消清理。")

            return True

        print("AI：没有识别出有效的记忆操作。")
        return True

    except (requests.RequestException, KeyError, ValueError, TypeError, IndexError, AttributeError) as e:
        print("记忆管理过程中发生问题：", e)
        return False


def extract_memories(user_text):
    """让 DeepSeek 从用户的话中提取值得长期保存的记忆。"""
    if not API_KEY:
        print("自动提取记忆失败：没有配置 DEEPSEEK_API_KEY。")
        return None
    if not isinstance(user_text, str) or not user_text.strip():
        return []

    
    prompt = """
你是一个长期记忆提取助手。
请认真分析用户刚才说的话，提取明确、真实、值得长期保存的信息。

以下情况应该提取：
1. 用户正在学习的技能、编程语言或知识领域。
2. 用户长期坚持的学习目标或项目。
3. 用户明确表达的回答风格和交流偏好。
4. 用户长期使用的工作方式或稳定习惯。

特别注意：
用户即使没有说“请记住”，只要表达了明确的长期学习目标或稳定偏好，也应该提取。
例如：
“我最近开始学习 Python 的文件操作，希望以后能够自己编写文件读写程序。”
应该提取为：
“用户正在学习 Python 文件操作，希望以后能够自己编写文件读写程序。”

以下情况不要提取：
1. 一次性问题和临时安排。
2. 密码、API Key、银行卡等机密信息。
3. 健康、政治观点、宗教、性取向等敏感个人信息。
4. 无法从用户原话中确认的推测信息。

只返回合法 JSON 数组，不要添加其他文字。
没有值得保存的信息时，返回 []。
"""


    try:
        existing_memory = load_memory()
    except RuntimeError as e:
        print("读取已有记忆失败，跳过本次提取：", e)
        return None

    prompt += (
        "\n用户已经保存的记忆如下：\n"
        + json.dumps(existing_memory, ensure_ascii=False)
        + "\n如果信息已经被已有记忆表达，不要重复提取；不要改写旧记忆。"
    )
    
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
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_text}
                ],
                "stream": False
            },
            timeout=60
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"].get("content", "")
        if not isinstance(content, str) or not content.strip():
            return None
        memories = json.loads(content)
        if not isinstance(memories, list):
            return []
        result = []

        for item in memories:
            if isinstance(item, str) and item.strip():
                result.append(item.strip())
            elif isinstance(item, dict):
                memory_text = item.get("记忆") or item.get("content", "")
                if isinstance(memory_text, str) and memory_text.strip():
                    result.append(memory_text.strip())


        return result
    except (requests.RequestException, KeyError, ValueError, IndexError, TypeError, AttributeError) as e:
        print("自动提取记忆时发生问题：", e)
        return None


def auto_save_memories(user_text):
    """提取记忆，并把新的记忆保存到文件。"""

    new_memories = extract_memories(user_text)

    if new_memories is None:
        print("[提示] 记忆提取失败，本次跳过保存。")
        return

    if not new_memories:
        return

    try:
        memory = load_memory()
    except RuntimeError as e:
        print("\nAI：自动保存记忆失败。", e)
        return

    added = []
    existing_keys = {
        item.strip().casefold()
        for item in memory
        if isinstance(item, str)
    }

    for item in new_memories:
        item_key = item.strip().casefold()

        if item_key and item_key not in existing_keys:
            memory.append(item.strip())
            added.append(item.strip())
            existing_keys.add(item_key)

    if added and save_memory(memory):
        print("\n[已自动保存长期记忆]")
        for item in added:
            print("-", item)