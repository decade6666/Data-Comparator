import tkinter as tk
from tkinter import ttk
from ...frontend.window_utils import set_window_icon
# from ..components.scrollable_frame import ScrollableFrame


def show_help(root):
    """Display help information"""
    help_window = tk.Toplevel(root)
    help_window.title("使用帮助")
    help_window.geometry("800x600")
    set_window_icon(help_window)
    
    # 使用容器 + Text + Scrollbar，文本自身滚动，容器固定填满窗口
    container = ttk.Frame(help_window, padding=(10, 10))
    container.pack(fill='both', expand=True)
    container.grid_rowconfigure(0, weight=1)
    container.grid_columnconfigure(0, weight=1)
    
    help_content = """
🔧 比对程序 V1.6.3 使用帮助

🚀 使用步骤：
1. 选择旧版本文件、新版本文件和输出目录
2. 设置结构参数：锚点行号、表头行号、合并删除数据
3. 设置标记颜色：更新、删除、新增
4. 设置比对参数：排除列、排除 sheet、默认锚点、sheet 锚点
5. 点击“开始比对”
        
🧰 配置管理：
• 新建：创建新配置
• 删除：删除选中配置
• 重命名：修改选中配置名称
• 导入：从JSON格式文件导入配置，导入时配置名称默认为文件名称，可按需求修改
• 导出：以JSON格式导出选中配置到指定位置

🔧 参数设置：
• 旧版本文件/新版本文件：待比较 Excel 文件的完整路径
• 输出目录：结果保存位置
• 锚点行号：锚点及删除列数据所在行的行号
• 表头行号：输出文件表头所在行的行号
• 合并删除数据：若不勾选，被删除的表单、行和列将不会输出到文件
• 删除列：不需要对比(和呈现)的列
• 排除表单：不需要对比(和呈现)的 Sheet 名称
• 默认锚点：所有表单的通用锚点（锚点用于定位数据行位置，合并后是唯一的）
• 指定表单锚点：指定表单的锚点，优先级高于默认锚点
• 颜色：更新/新增/删除内容的标记颜色
        更新：标记有差异的单元格和sheet
        删除：标记在旧版本文件存在但新版本不存在的 sheet和列
        新增：标记在旧版本文件不存在但新版本存在的 sheet和列

🎛 高级设置：
• 最大线程数：控制同时处理sheet数量，默认为 CPU 核心数-1，建议不超过 CPU 核心数的2倍
• 深色模式：切换界面主题

📝 日志记录：
• 程序会在输出目录自动生成详细的日志文件
• 日志文件名格式：比对日志-YYYY-MM-DDTHH-MM-SS.txt
• 日志文件包含完整的处理过程和错误信息，可用于问题排查

作者：Decade 
联系方式：jian.tan@zzmedicine.cn
项目主页：https://gitee.com/decadeTJ/py_DataCompare

    """
    
    help_text = tk.Text(
        container,
        wrap='word',
        bg='#f8f9fa',
        fg='#333',
        relief='flat',
        padx=20,
        pady=20,
    )
    vbar = ttk.Scrollbar(container, orient='vertical', command=help_text.yview)
    help_text.configure(yscrollcommand=vbar.set)

    help_text.grid(row=0, column=0, sticky='nsew')
    vbar.grid(row=0, column=1, sticky='ns')

    help_text.insert('1.0', help_content)
    help_text.config(state='disabled') 
