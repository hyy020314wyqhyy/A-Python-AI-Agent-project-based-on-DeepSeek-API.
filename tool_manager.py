# -*- coding: utf-8 -*-

import os
import json
import re
import time
from datetime import datetime

import requests

from file_manager import (
    generate_text_summary,
    get_text_file_stats,
    list_text_files,
    prepare_text_file_summary,
    process_batch_summaries,
    read_text_file,
    save_text_summary,
    search_text_files,
    write_text_file,
)
from knowledge_base import generate_json_data, read_json_file, save_json_file
from scheduler import get_current_time, make_study_plan



# ==============================
# 工具定义（Function Calling Schema）
# ==============================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "仅当用户询问现在的具体时间、今天的日期或当前日期信息时调用。不要用于计算未来或过去的时间，也不要用于普通聊天。",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",

"function": {
    "name": "make_study_plan",
    "description": "当用户明确要求制定、安排或生成 Python 学习计划时调用。如果用户提供了学习时长，使用用户指定的时长；如果用户没有提供学习时长，默认使用 30 分钟，不要仅因为缺少时长而追问。用户只是询问 Python 知识或一般学习建议时，优先直接回答。该工具用于生成 Python 学习计划，不用于数学计算或查询时间。",    "parameters": {
        "type": "object",
        "properties": {
            "minutes": {
                "type": "integer",
                "description": "学习计划的总时长，单位为分钟，必须是 1 到 600 之间的整数。"
            }
        },
        "required": []
    }
}

    },
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "当用户要求计算数学表达式或明确询问数学算式的结果时调用，包括加减乘除、整除、取余和乘方。将用户的问题转换成安全的数学表达式，通过此工具计算，不要自行猜测计算结果。普通聊天、制定学习计划或询问时间时不要调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "要计算的数学表达式，例如 125 * 36"
                    }
                },
                "required": ["expression"]
            }
        }
        },
    {
        "type": "function",
        "function": {
            "name": "read_text_file",
            "description": "当用户明确要求读取本地 TXT 文件内容时调用。只能读取程序所在目录中的 TXT 文件，不要用于读取其他类型的文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "要读取的 TXT 文件名，例如 agent_test.txt"
                    }
                },
                "required": ["filename"]
            }
        }
        
    },    {
        "type": "function",
        "function": {
            "name": "write_text_file",
            "description": "在程序所在目录创建 TXT 文件，不覆盖已有文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "要创建的 TXT 文件名，例如 note.txt"
                    },
                    "content": {
                        "type": "string",
                        "description": "要写入文件的文本内容"
                    }
                },
                "required": ["filename", "content"]
            }
        }
    },
        {
        "type": "function",
        "function": {
            "name": "list_text_files",
            "description": "列出程序所在目录中的所有 TXT 文件。",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
        {
        "type": "function",
        "function": {
            "name": "search_text_files",
            "description": "在程序所在目录的 TXT 文件中搜索关键词，并返回匹配的文件名、行号和内容。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "要搜索的关键词"
                    }
                },
                "required": ["keyword"]
            }
        }
    },
        {
        "type": "function",
        "function": {
            "name": "get_text_file_stats",
            "description": "统计程序所在目录中所有 TXT 文件的大小、行数和字符数。",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
        {
        "type": "function",
        "function": {
            "name": "summarize_text_file",
            "description": "当用户明确要求总结或摘要本地 TXT 文件时调用。只能总结程序所在目录中的 TXT 文件。不要修改原始文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "需要生成摘要的 TXT 文件名，例如 multiline_test.txt"
                    }
                },
                "required": ["filename"]
            }
        }
    },
            {
        "type": "function",
        "function": {
            "name": "save_text_summary",
            "description": "当用户明确要求保存已经生成的文件摘要时调用。将摘要保存为原文件名加_summary.txt的新文件。只能在程序所在目录创建TXT文件，不得覆盖已有文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "原始 TXT 文件名，例如 multiline_test.txt"
                    },
                    "summary": {
                        "type": "string",
                        "description": "需要保存的摘要内容"
                    },
                    "output_filename": {
                        "type": "string",
                        "description": "用户指定的摘要文件名，例如 multiline_test_summary_v2.txt；如果用户没有指定，则不传此参数"
                    }
    },
    "required": ["filename", "summary"]
            }
        }
    },
    {
    "type": "function",
    "function": {
        "name": "process_batch_summaries",
        "description": "批量为当前目录中尚未生成摘要的 TXT 文件生成摘要，并保存为新文件。",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
},
        {
        "type": "function",
        "function": {
            "name": "generate_json_data",
            "description": "当用户明确要求生成结构化 JSON 学习计划时调用。生成的数据必须包含 title、duration 和 tasks 字段，并经过完整验证。",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "用户对 JSON 学习计划的具体要求。"
                    }
                },
                "required": ["prompt"]
            }
        }
    },
        {
        "type": "function",
        "function": {
            "name": "save_json_file",
            "description": "将已经生成并验证通过的 JSON 学习计划保存到文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "data": {
                        "type": "object",
                        "description": "需要保存的 JSON 学习计划数据。"
                    },
                    "filename": {
                        "type": "string",
                        "description": "保存文件名，默认 learning_plan.json。"
                    }
                },
                "required": ["data"]
            }
        }
    },
        {
        "type": "function",
        "function": {
            "name": "read_json_file",
            "description": "读取已经保存的 JSON 学习计划文件，并返回文件内容。",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "需要读取的 JSON 文件名，默认 learning_plan.json。"
                    }
                },
                "required": []
            }
        }
    },
]


def run_tool(name, arguments):
    if not isinstance(arguments, dict):
        return "错误：工具参数必须是字典。"

    if name == "get_current_time":
        return get_current_time()

    if name == "make_study_plan":
        minutes = arguments.get("minutes", 30)
        if not isinstance(minutes, int) or isinstance(minutes, bool):
            return "错误：minutes 参数必须是整数。"
        if minutes <= 0:
            return "错误：minutes 必须大于 0。"
        if minutes > 600:
            return "错误：minutes 不能超过 600。"
        return make_study_plan(minutes)

    
    if name == "calculator":
        if "expression" not in arguments:
            return "错误：缺少 expression 参数。"
        if not isinstance(arguments["expression"], str):
            return "错误：expression 参数必须是字符串。"
        
        try:
            return calculator(arguments["expression"])
        except ZeroDivisionError:
            return "错误：计算失败，不能除以零。"
        except (ValueError, OverflowError) as e:
            return f"错误：计算失败。{e}"


    if name == "read_text_file":
        if "filename" not in arguments:
            return "错误：缺少 filename 参数。"

        if not isinstance(arguments["filename"], str):
            return "错误：filename 参数必须是字符串。"

        return read_text_file(arguments["filename"])
    
    
    if name == "write_text_file":
        if "filename" not in arguments:
            return "错误：缺少 filename 参数。"

        
        if "content" not in arguments:
            return "错误：缺少 content 参数。"

        return write_text_file(
            arguments["filename"],
            arguments["content"]
        )
    
    if name == "list_text_files":
        return list_text_files()
    
    if name == "search_text_files":
        if "keyword" not in arguments:
            return "错误：缺少 keyword 参数。"

        return search_text_files(arguments["keyword"])
    
    if name == "get_text_file_stats":
        return get_text_file_stats()
    
    
    if name == "summarize_text_file":
        if "filename" not in arguments:
            return "错误：缺少 filename 参数。"

        prompt = prepare_text_file_summary(arguments["filename"])

        if prompt.startswith("错误："):
            return prompt

        return generate_text_summary(prompt)
    
    if name == "save_text_summary":
        if "filename" not in arguments:
            return "错误：缺少 filename 参数。"

        if "summary" not in arguments:
            return "错误：缺少 summary 参数。"

        return save_text_summary(
            arguments["filename"],
            arguments["summary"],
            arguments.get("output_filename")
        )
    if name == "process_batch_summaries":
        return process_batch_summaries()
    
    if name == "generate_json_data":
        if "prompt" not in arguments:
            return "错误：缺少 prompt 参数。"
        if not isinstance(arguments["prompt"], str):
            return "错误：prompt 参数必须是字符串。"
        return generate_json_data(arguments["prompt"])

    if name == "save_json_file":
        if "data" not in arguments:
            return "错误：缺少 data 参数。"

        if not isinstance(arguments["data"], dict):
            return "错误：data 参数必须是字典。"

        return save_json_file(
            arguments["data"],
            arguments.get("filename", "learning_plan.json")
        )
        
    if name == "read_json_file":
        return read_json_file(
            arguments.get("filename", "learning_plan.json")
        )

    return "错误：不支持这个工具。"


def calculator(expression):
    """安全地计算简单的数学表达式。"""
    import ast
    import operator
    import math

    operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    
    def calculate(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            if isinstance(node.value, float) and not math.isfinite(node.value):
                raise ValueError("输入数值不是有限数值")
            return node.value


        if isinstance(node, ast.BinOp) and type(node.op) in operators:
            left = calculate(node.left)
            right = calculate(node.right)

            
            if isinstance(node.op, ast.Pow):
                if abs(right) > 100:
                    raise ValueError("指数太大")

                if abs(left) > 10**10 and right > 2:
                    raise ValueError("乘方计算量太大")

            

            result = operators[type(node.op)](left, right)


            if isinstance(result, complex):
                raise ValueError("不支持复数结果")
            if isinstance(result, int):
                if abs(result) > 10**100:
                    raise ValueError("计算结果太大")

            elif isinstance(result, float):
                if not math.isfinite(result):
                    raise ValueError("计算结果不是有限数值")

                if abs(result) > 10**100:
                    raise ValueError("计算结果太大")

            return result

        if isinstance(node, ast.UnaryOp) and type(node.op) in operators:
            result = operators[type(node.op)](calculate(node.operand))

            if isinstance(result, int):
                if abs(result) > 10**100:
                    raise ValueError("计算结果太大")

            elif isinstance(result, float):
                if not math.isfinite(result):
                    raise ValueError("计算结果不是有限数值")

                if abs(result) > 10**100:
                    raise ValueError("计算结果太大")

            return result

        raise ValueError("不支持这个数学表达式")

    if not isinstance(expression, str) or not expression.strip():
        raise ValueError("请输入有效的数学表达式")
    if len(expression) > 200:
        raise ValueError("数学表达式太长，最多允许 200 个字符")

    
    try:
        tree = ast.parse(expression, mode="eval")
        return calculate(tree.body)
    except SyntaxError:
        raise ValueError("数学表达式格式不正确")
    except RecursionError:
        raise ValueError("数学表达式结构过于复杂")