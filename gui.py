# -*- coding: utf-8 -*-
"""简易图形界面（Tkinter）。

命令行主程序见 main.py，本文件提供图形界面入口：
    python gui.py
"""

import io
import threading
from contextlib import redirect_stdout

import tkinter as tk
from tkinter import messagebox, scrolledtext

from config import API_KEY
from ai_client import (
    ask_ai,
    build_system_prompt,
    refresh_system_prompt,
)

from memory import (
    load_memory,
    auto_save_memories,
)


class AgentGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("DeepSeek AI Agent")
        self.root.geometry("760x600")

        self.chat = scrolledtext.ScrolledText(root, wrap=tk.WORD, state="disabled")
        self.chat.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 4))

        frame = tk.Frame(root)
        frame.pack(fill=tk.X, padx=8, pady=(0, 8))

        self.entry = tk.Text(frame, height=3, wrap=tk.WORD)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry.bind("<Control-Return>", lambda e: self.send())

        self.button = tk.Button(frame, text="发送", width=8, command=self.send)
        self.button.pack(side=tk.RIGHT, padx=(6, 0), fill=tk.Y)

        self.messages = []
        try:
            memory = load_memory()
        except RuntimeError as e:
            memory = []
            self.append(f"记忆读取失败：{e}")
        self.messages.append({"role": "system", "content": build_system_prompt(memory)})

        self.append("AI Agent 已启动，输入内容后按 Ctrl+Enter 或点“发送”。")

    def append(self, text):
        self.chat.configure(state="normal")
        self.chat.insert(tk.END, text + "\n\n")
        self.chat.see(tk.END)
        self.chat.configure(state="disabled")

    def send(self):
        user_text = self.entry.get("1.0", tk.END).strip()
        if not user_text:
            return
        self.entry.delete("1.0", tk.END)

        self.append("你：" + user_text)
        self.messages.append({"role": "user", "content": user_text})
        self.button.configure(state=tk.DISABLED)

        threading.Thread(target=self.worker, daemon=True).start()

    def worker(self):
        buffer = io.StringIO()

        # 先保存本轮用户输入
        user_text = self.messages[-1].get("content", "")

        try:
            with redirect_stdout(buffer):

                ai_success = ask_ai(self.messages)

                if ai_success:
                    # AI 成功后自动保存记忆
                    auto_save_memories(user_text)

                    # 更新系统提示词
                    refresh_system_prompt(self.messages)

        except Exception as e:  # noqa: BLE001
            buffer.write(f"\n出错：{e}")

        text = buffer.getvalue().strip() or "（没有输出）"

        self.root.after(0, lambda: self.finish(text))

    def finish(self, text):
        self.append(text)
        self.button.configure(state=tk.NORMAL)


def main():
    if not API_KEY:
        messagebox.showerror(
            "缺少 API Key",
            "没有读取到 DEEPSEEK_API_KEY。\n请先配置环境变量后重新启动。",
        )
        return
    root = tk.Tk()
    AgentGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
