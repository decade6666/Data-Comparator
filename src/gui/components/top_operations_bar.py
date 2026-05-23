import tkinter as tk
import ttkbootstrap as ttk

class TopOperationsBar(ttk.Frame):
    """
    应用程序顶部操作栏的UI组件。
    包含开始/停止比对等主要操作按钮。
    """
    def __init__(self, parent, callbacks, **kwargs):
        """
        初始化顶部操作栏。

        Args:
            parent: 父级Tkinter组件。
            callbacks (dict): 一个包含按钮回调函数的字典。
        """
        super().__init__(parent, **kwargs)
        self.callbacks = callbacks

        self._create_widgets()

    def _create_widgets(self):
        """创建并布局此组件中的所有UI元素。"""
        self.configure(padding=(8, 6))

        # 居中容器，使用grid两侧留空实现居中
        center = ttk.Frame(self)
        center.pack(fill=tk.X)
        center.grid_columnconfigure(0, weight=1)
        # 第3列作为右侧弹性空白，第4列放置“使用帮助”按钮，第5列放置“高级设置”按钮
        center.grid_columnconfigure(3, weight=1)
        center.grid_columnconfigure(4, weight=0)
        center.grid_columnconfigure(5, weight=0)

        self.run_btn = ttk.Button(center, text="▶ 开始比对", bootstyle="success", command=self.callbacks.get('start'))
        self.run_btn.grid(row=0, column=1, padx=8, pady=2)

        self.stop_btn = ttk.Button(center, text="■ 停止比对", bootstyle="danger-outline", command=self.callbacks.get('stop'), state=tk.DISABLED)
        self.stop_btn.grid(row=0, column=2, padx=8, pady=2)

        # 新增：右侧的“使用帮助”按钮，位于“高级设置”左侧
        self.help_btn = ttk.Button(center, text="使用帮助", bootstyle="info-outline", command=self.callbacks.get('help'))
        self.help_btn.grid(row=0, column=4, padx=8, pady=2, sticky='e')

        # 右侧的高级设置按钮，放在最右侧
        self.advanced_btn = ttk.Button(center, text="高级设置", bootstyle="secondary", command=self.callbacks.get('advanced'))
        self.advanced_btn.grid(row=0, column=5, padx=8, pady=2, sticky='e')

    def set_button_state(self, button_name, state):
        """
        动态设置按钮的状态。

        Args:
            button_name (str): 'run'、'stop'、'help' 或 'advanced'。
            state (str): 'normal' 或 'disabled'。
        """
        if button_name == 'run':
            self.run_btn.config(state=state)
        elif button_name == 'stop':
            self.stop_btn.config(state=state)
        elif button_name == 'help':
            self.help_btn.config(state=state)
        elif button_name == 'advanced':
            self.advanced_btn.config(state=state) 