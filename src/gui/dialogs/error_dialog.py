import tkinter as tk
from tkinter import ttk, messagebox
import os
import subprocess

# 导入设置窗口图标的函数
from ...utils.file_utils import set_window_icon


def show_file_error_dialog(root, file_path, error_message):
    """Display file error handling dialog"""
    error_window = tk.Toplevel(root)
    error_window.title("文件读取失败")
    error_window.geometry("700x500")
    set_window_icon(error_window)
    
    # Main frame
    main_frame = ttk.Frame(error_window, padding="20")
    main_frame.pack(fill='both', expand=True)
    
    # Error message
    error_label = ttk.Label(main_frame, text="⚠️ 文件读取失败", font=('微软雅黑', 14, 'bold'), foreground='red')
    error_label.pack(pady=(0, 10))
    
    file_label = ttk.Label(main_frame, text=f"文件: {file_path}", font=('微软雅黑', 10))
    file_label.pack(pady=(0, 10))
    
    # Error details
    detail_frame = ttk.LabelFrame(main_frame, text="错误详情", padding="10")
    detail_frame.pack(fill='x', pady=(0, 20))
    
    error_text = tk.Text(detail_frame, height=4, wrap='word', font=('Consolas', 9))
    error_text.pack(fill='x')
    error_text.insert('1.0', error_message)
    error_text.config(state='disabled')
    
    # Suggested solutions
    suggestion_frame = ttk.LabelFrame(main_frame, text="解决方案建议", padding="10")
    suggestion_frame.pack(fill='both', expand=True, pady=(0, 20))
    
    suggestions = """📋 推荐的解决方案（按优先级排序）:

🔧 立即尝试:
  1. 在Excel中打开文件，选择"是"修复文件，然后另存为新文件
  2. 尝试用WPS Office或LibreOffice打开文件并重新保存

💡 其他方法:
  3. 检查文件是否实际为CSV格式，用记事本打开查看
  4. 如果文件来自网络下载，重新下载原始文件
  5. 检查文件是否被防病毒软件隔离或修改

🚨 文件分析:
  • 错误类型: 文件格式损坏
  • 常见原因: 传输中断、软件异常、病毒感染

⚡ 如果是紧急情况:
  • 可以尝试跳过此文件，使用其他可用文件
  • 联系文件提供方获取新文件"""
    
    suggestion_text = tk.Text(suggestion_frame, wrap='word', font=('微软雅黑', 10), bg='#f8f9fa', fg='#333')
    suggestion_text.pack(fill='both', expand=True)
    suggestion_text.insert('1.0', suggestions)
    suggestion_text.config(state='disabled')
    
    # Button frame
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill='x')
    
    def skip_file():
        error_window.destroy()
        # 这里应该有一个日志函数，但为了避免循环导入，暂时不直接调用GUI的log_message
        # log_message(f"用户选择跳过文件: {file_path}")
    
    def open_file_location():
        try:
            subprocess.Popen(f'explorer /select,""{file_path}""' # Fix: escaped quotes for file path
)
        except Exception:
            dir_path = os.path.dirname(file_path)
            subprocess.Popen(f'explorer ""{dir_path}""' # Fix: escaped quotes for directory path
)
    
    # Buttons
    ttk.Button(button_frame, text="📁 打开文件位置", command=open_file_location).pack(side='left', padx=5)
    ttk.Button(button_frame, text="⏭️ 跳过此文件", command=skip_file).pack(side='left', padx=5)
    ttk.Button(button_frame, text="❌ 关闭", command=error_window.destroy).pack(side='right', padx=5)
    
    # Set window to modal
    error_window.transient(root)
    error_window.grab_set()
    
    # Center display
    error_window.update_idletasks()
    x = (error_window.winfo_screenwidth() // 2) - (error_window.winfo_width() // 2)
    y = (error_window.winfo_screenheight() // 2) - (error_window.winfo_height() // 2)
    error_window.geometry(f"+{x}+{y}") 