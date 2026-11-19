# -*- coding: utf-8 -*-

import os
import json
import re
import time
from datetime import datetime

import requests

from config import API_KEY, API_URL, MODEL



def read_text_file(filename):
    """安全地读取程序所在目录中的普通 TXT 文件。"""
    from pathlib import Path

    if not isinstance(filename, str):
        return "错误：文件名必须是字符串。"
    if not filename.lower().endswith(".txt"):
        return "错误：目前只允许读取 TXT 文件。"
    if Path(filename).name != filename or filename in (".", ".."):
        return "错误：只能读取程序所在目录中的文件。"

    file_path = Path(__file__).resolve().parent / filename
    try:
        if file_path.is_symlink():
            return "错误：不能通过符号链接读取文件。"
        if not file_path.exists():
            return "错误：文件不存在。"
        if not file_path.is_file():
            return "错误：目标路径不是普通文件。"
        if file_path.stat().st_size > 100 * 1024:
            return "错误：文件不能超过 100 KB。"
        return file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return f"错误：读取文件失败。{e}"


def write_text_file(filename, content):
    """安全地创建 TXT 文件，不覆盖已有文件。"""
    from pathlib import Path

    if not isinstance(filename, str):
        return "错误：文件名必须是字符串。"

    
    if not filename.lower().endswith(".txt"):
        return "错误：目前只允许创建 TXT 文件。"


    if Path(filename).name != filename:
        return "错误：只能在程序所在目录创建文件。"

    if not isinstance(content, str):
        return "错误：文件内容必须是字符串。"

    try:
        content_size = len(content.encode("utf-8"))
    except UnicodeEncodeError:
        return "错误：文件内容包含无法使用 UTF-8 编码的字符。"

    if content_size > 100 * 1024:
        return "错误：文件内容不能超过 100 KB。"

    file_path = Path(__file__).resolve().parent / filename

    try:
        with file_path.open("x", encoding="utf-8") as file:
            file.write(content)

        return f"文件创建成功：{filename}"

    except FileExistsError:
        return "错误：文件已经存在，不能覆盖。"

    except OSError as e:
        return f"错误：文件创建失败。{e}"


def list_text_files():
    """列出程序所在目录中的所有 TXT 文件。"""
    from pathlib import Path

    folder = Path(__file__).resolve().parent

    try:
        files = [
            file.name
            for file in folder.iterdir()
            if not file.is_symlink() and file.is_file() and file.suffix.lower() == ".txt"
        ]

        files.sort()

        if not files:
            return "当前目录中没有 TXT 文件。"

        result = "当前目录中的 TXT 文件：\n"

        for index, filename in enumerate(files, start=1):
            result += f"{index}. {filename}\n"

        return result

    except OSError as e:
        return f"错误：无法列出文件。{e}"


def get_text_file_names():
    """获取当前目录下所有 TXT 文件名。"""
    from pathlib import Path

    files = [
        path.name
        for path in Path(__file__).resolve().parent.iterdir()
        if not path.is_symlink() and path.is_file() and path.suffix.lower() == ".txt"
    ]

    return sorted(files)


def get_files_needing_summary():
    
    """获取尚未生成摘要的 TXT 文件。"""
    from pathlib import Path
    filenames = get_text_file_names()

    files_to_process = []

    for filename in filenames:
        if "summary" in filename.lower():
            continue
        
        try:
            file_size = (
            Path(__file__).resolve().parent / filename
            ).stat().st_size
        except OSError:
            continue

        if file_size > 100 * 1024:
            continue

        if summary_exists(filename):
            continue

        files_to_process.append(filename)

    return files_to_process


def search_text_files(keyword):
    """在程序所在目录的 TXT 文件中搜索关键词。"""
    from pathlib import Path

    if not isinstance(keyword, str):
        return "错误：关键词必须是字符串。"

    keyword = keyword.strip()

    if not keyword:
        return "错误：关键词不能为空。"

    folder = Path(__file__).resolve().parent
    results = []

    try:
        for file_path in folder.iterdir():
            if file_path.is_symlink() or not file_path.is_file():
                continue

            if file_path.suffix.lower() != ".txt":
                continue

            try:
                if file_path.stat().st_size > 100 * 1024:
                    continue
            except OSError:
                continue

            try:
                content = file_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            for line_number, line in enumerate(content.splitlines(), start=1):
                if keyword.casefold() in line.casefold():
                    results.append(
                        f"{file_path.name} 第 {line_number} 行：{line}"
                    )

        if not results:
            return f"没有找到关键词：{keyword}"

        return "搜索结果：\n" + "\n".join(results)

    except OSError as e:
        return f"错误：搜索文件失败。{e}"


def get_text_file_stats():
    """统计程序所在目录中 TXT 文件的大小、行数和字符数。"""
    from pathlib import Path

    folder = Path(__file__).resolve().parent
    results = []

    try:
        files = sorted(
            file for file in folder.iterdir()
            if not file.is_symlink() and file.is_file() and file.suffix.lower() == ".txt"
        )

        if not files:
            return "当前目录中没有 TXT 文件。"

        for file_path in files:
            try:
                size = file_path.stat().st_size

                if size > 100 * 1024:
                    results.append(
                        f"{file_path.name}：文件超过 100 KB，跳过统计。"
                    )
                    continue

                content = file_path.read_text(encoding="utf-8")

                line_count = len(content.splitlines())
                char_count = len(content)

                results.append(
                    f"{file_path.name}："
                    f"大小 {size} 字节，"
                    f"行数 {line_count}，"
                    f"字符数 {char_count}。"
                )

            except (OSError, UnicodeDecodeError) as e:
                results.append(
                    f"{file_path.name}：读取失败，{e}"
                )

        return "TXT 文件统计结果：\n" + "\n".join(results)

    except OSError as e:
        return f"错误：无法统计文件。{e}"


def build_summary_prompt(content):
    """生成文件摘要任务提示词。"""

    return (
        "请总结下面的 TXT 文件内容。\n"
        "要求：\n"
        "1. 使用中文回答。\n"
        "2. 提炼最重要的信息。\n"
        "3. 保留关键事实，不要编造内容。\n"
        "4. 摘要长度控制在 100～200 字左右。\n\n"
        "文件内容：\n"
        f"{content}"
    )


def prepare_text_file_summary(filename):
    """安全读取 TXT 文件并准备摘要提示词。"""
    content = read_text_file(filename)

    if content.startswith("错误："):
        return content

    if not content.strip():
        return "错误：文件内容为空，无法生成摘要。"

    return build_summary_prompt(content)


def generate_text_summary(prompt):
    """调用 DeepSeek API 生成文件摘要。"""
    if not isinstance(prompt, str):
        return "错误：摘要提示词必须是字符串。"

    if not prompt.strip():
        return "错误：摘要提示词不能为空。"
    if not API_KEY:
        return "错误：没有配置 DEEPSEEK_API_KEY。"

    messages = [
        {
            "role": "system",
            "content": "你是一个严谨的文件摘要助手。"
        },
        {
            "role": "user",
            "content": prompt
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

        result = response.json()
        answer = result["choices"][0]["message"].get("content", "")

        if not isinstance(answer, str) or not answer.strip():
            return "错误：AI 没有返回有效的摘要内容。"

        return answer.strip()

    except requests.RequestException as e:
        return f"错误：DeepSeek API 请求失败。{e}"

    except (KeyError, ValueError, IndexError, TypeError, AttributeError) as e:
        return f"错误：处理 AI 返回内容失败。{e}"


def make_summary_filename(filename):
    """根据原始文件名生成摘要文件名。"""
    from pathlib import Path

    original_name = Path(filename).stem

    return f"{original_name}_summary.txt"


def summary_exists(filename):
    """检查对应的摘要文件是否已经存在。"""
    from pathlib import Path

    summary_filename = make_summary_filename(filename)

    return (Path(__file__).resolve().parent / summary_filename).exists()


def save_text_summary(filename, summary, output_filename=None):
    """将文件摘要保存为新的 TXT 文件。"""
    if output_filename is not None and not isinstance(output_filename, str):
        return "错误：摘要文件名必须是字符串。"
    
    if output_filename:
        from pathlib import Path

        output_path = Path(output_filename)

        if output_path.name != output_filename:
            return "错误：只能使用文件名，不能包含路径。"

        if output_path.suffix.lower() != ".txt":
            return "错误：摘要文件必须使用 .txt 扩展名。"

        summary_filename = output_filename
    else:
        summary_filename = make_summary_filename(filename)

    return write_text_file(summary_filename, summary)


def process_single_file_summary(filename):
    """生成并保存单个 TXT 文件的摘要。"""

    prompt = prepare_text_file_summary(filename)

    if prompt.startswith("错误："):
        return prompt

    summary = generate_text_summary(prompt)

    if summary.startswith("错误："):
        return summary

    result = save_text_summary(filename, summary)

    return result


def process_batch_summaries():
    """批量生成当前目录中 TXT 文件的摘要。"""

    try:
        filenames = get_files_needing_summary()
    except OSError as e:
        return f"错误：读取 TXT 文件目录失败。{e}"

    if not filenames:
        return "当前没有需要生成摘要的 TXT 文件。"
    results = []

    for filename in filenames:
        try:
            result = process_single_file_summary(filename)
        except Exception as e:
            result = f"处理失败：{e}"

        results.append(f"{filename}：{result}")

    return "\n".join(results)