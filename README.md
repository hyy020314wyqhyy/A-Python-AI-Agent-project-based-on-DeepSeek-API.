Python DeepSeek AI Agent

基于 Python + DeepSeek API 的命令行 AI Agent 示例项目，包含对话、工具调用、长期记忆、任务规划、文件摘要、日志统计等能力。

本项目由原来的单文件版本 day2-3.py 逐步模块化开发，并持续完善了长期记忆、网络连接、文件管理和部署功能。

一、目录结构

Python_DeepSeek_AI_Agent_36-55/
│
├── main.py              # 程序入口：命令行主循环与命令分发
├── config.py            # 全局配置：API Key、接口地址、模型、文件路径
├── ai_client.py         # AI 对话核心：ask_ai、系统提示词、对话历史裁剪
├── memory.py            # 长期记忆：增删改查、备份恢复、AI 自动记忆
├── task_manager.py      # 任务规划：生成任务计划、逐步执行、进度检查
├── file_manager.py      # 文件处理：TXT 读写、扫描搜索、摘要生成
├── knowledge_base.py    # 知识库/JSON：示例数据、JSON 校验与生成
├── tool_manager.py      # 工具管理：工具定义（Function Calling）与 run_tool
├── logger.py            # 日志：工具调用记录、脱敏、导出备份、统计
├── scheduler.py         # 调度/时间：获取当前时间、生成学习计划
├── gui.py               # 图形界面（Tkinter），可选入口
├── self_test.py         # 自测脚本：基础功能检查与可选 API 联网检查
├── requirements.txt     # 第三方依赖
└── README.md            # 本说明

二、各模块职责

模块

主要函数

作用

main.py

main()

启动程序、读取记忆、循环接收输入并分发命令

config.py

—

读取 DEEPSEEK_API_KEY，定义接口地址、模型、数据文件路径

ai_client.py

ask_ai、build_system_prompt、trim_conversation_history

组织消息、调用 DeepSeek、处理工具调用循环

memory.py

load_memory、save_memory、add_memory、auto_save_memories

长期记忆的读写与维护

task_manager.py

generate_task_plan、execute_task_step

把复杂目标拆成步骤并逐步执行

file_manager.py

read_text_file、write_text_file、process_batch_summaries

TXT 文件读写、搜索、摘要

knowledge_base.py

generate_json_data、validate_learning_plan

JSON 生成与校验

tool_manager.py

TOOLS、run_tool、calculator

工具声明与执行

logger.py

save_tool_log、show_tool_logs、show_tool_log_stats

工具日志记录与统计

scheduler.py

get_current_time、make_study_plan

时间与计划类工具

三、环境要求

Python 3.9 及以上

能访问 DeepSeek API

四、安装依赖

python -m pip install -r requirements.txt

五、配置 API Key

PowerShell：

$env:DEEPSEEK_API_KEY="你的DeepSeek_API_Key"

说明：以上命令只在当前 PowerShell 会话中设置环境变量。关闭窗口后，需要重新设置。如果希望长期使用，可以配置 Windows 用户级环境变量。

请勿将真实 API Key 上传到 GitHub 或其他公开平台。

六、运行

命令行版本：

python main.py

图形界面版本（可选）：

python gui.py

七、自测

运行：

python self_test.py

说明：基础检查可在本地运行；如果已配置 DEEPSEEK_API_KEY，还会额外执行 API 联网检查。

八、常用命令

命令

功能

help

查看帮助

exit

退出程序

chat / normal / mode

切换连续对话模式 / 普通模式 / 查看当前模式

记住：内容

保存一条长期记忆

查看记忆

查看已保存记忆

更新记忆 1：内容

更新第 1 条记忆

删除记忆 1

删除第 1 条记忆

记忆去重

清理重复记忆

恢复记忆

恢复长期记忆

logs

查看工具调用日志

logstats

查看工具调用统计

clearlogs

清空工具日志

exportlogs / backuplogs / restorelogs

导出 / 备份 / 恢复工具日志

listtxt

列出可处理的 TXT 文件

searchtxt 关键词

搜索 TXT 文件

txtstats

统计 TXT 文件

summary 文件名

生成单个文件摘要

batchsummary

批量生成摘要

输入时以 /done 结束多行内容。

九、运行中生成的数据文件

文件

用途

memory.json

长期记忆

tool_logs.json

工具调用日志

memory_backup_*.json

记忆备份

tool_logs_backup_*.json

日志备份

*_summary.txt

文件摘要

这些文件与程序所在目录一致，请不要随意删除。

十、项目说明

本项目基于原 day2-3.py 逐步模块化开发，并持续完善各项功能。

原程序中 main() 调用了未定义的 show_tool_log_stats()，后来已在 logger.py 中补齐，logstats 命令可以正常使用。

项目使用环境变量读取 DeepSeek API Key，不需要在源代码中直接填写密钥。

项目包含 PyInstaller 打包支持，可以生成 Windows EXE 程序。

项目仍在持续学习和完善中，欢迎交流与改进。