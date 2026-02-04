import tkinter as tk
from tkinter import scrolledtext, messagebox
import subprocess
import threading


class NanobotUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Nanobot Assistant (Native UI)")
        self.root.geometry("600x700")

        # 1. 聊天显示区域
        self.chat_area = scrolledtext.ScrolledText(root, wrap=tk.WORD, state='disabled', font=("Microsoft YaHei", 10))
        self.chat_area.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        # 2. 输入区域
        self.input_frame = tk.Frame(root)
        self.input_frame.pack(padx=10, pady=5, fill=tk.X)

        self.user_input = tk.Entry(self.input_frame, font=("Microsoft YaHei", 11))
        self.user_input.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5)
        self.user_input.bind("<Return>", lambda e: self.send_message())

        self.send_btn = tk.Button(self.input_frame, text="发送", command=self.send_message, bg="#0078D4", fg="white",
                                  padx=15)
        self.send_btn.pack(side=tk.RIGHT, padx=5)

    def append_message(self, role, text):
        self.chat_area.config(state='normal')
        self.chat_area.insert(tk.END, f"{role}: {text}\n\n")
        self.chat_area.config(state='disabled')
        self.chat_area.see(tk.END)

    def send_message(self):
        prompt = self.user_input.get().strip()
        if not prompt: return

        self.append_message("用户", prompt)
        self.user_input.delete(0, tk.END)

        # 在后台线程运行命令，防止界面卡死
        threading.Thread(target=self.call_nanobot, args=(prompt,), daemon=True).start()

    def call_nanobot(self, prompt):
        try:
            # 关键：我们不再让它在控制台打印，而是直接抓取输出字符串
            # 这样就不会触发控制台的 GBK 编码报错
            process = subprocess.run(
                ["nanobot", "agent", "-m", prompt],
                capture_output=True,
                text=True,
                shell=True,
                errors='ignore'
            )

            answer = process.stdout.strip() or process.stderr.strip()

            if answer:
                self.root.after(0, self.append_message, "Nanobot", answer)
            else:
                self.root.after(0, self.append_message, "系统", "Agent 执行完毕，但无输出。")
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("错误", f"启动失败: {str(e)}"))


if __name__ == "__main__":
    root = tk.Tk()
    app = NanobotUI(root)
    root.mainloop()