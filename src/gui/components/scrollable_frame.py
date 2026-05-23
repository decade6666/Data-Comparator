import tkinter as tk
import ttkbootstrap as ttk

class ScrollableFrame(ttk.Frame):
    """可滚动框架，用于包装内容，使其在超出可见区域时能够滚动。"""
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        # 创建Canvas，作为可滚动区域的"视口"
        canvas = tk.Canvas(self, borderwidth=0, background='#f7f7f9', highlightthickness=0)
        # 创建垂直滚动条，并关联到Canvas的yview
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        # 创建一个内部框架，实际放置所有可滚动内容
        self.scrollable_frame = ttk.Frame(canvas, style='TFrame')
        # 将内部框架放置到Canvas中，并锚定在西北角（左上角）
        self.scrollable_frame_id = canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        # 配置Canvas，使其通过滚动条滚动
        canvas.configure(yscrollcommand=scrollbar.set)
        # 布局Canvas和滚动条
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.canvas = canvas # 将Canvas实例保存为属性，以便后续访问
        self.bind_events() # 绑定鼠标滚轮事件
        # 关键：同步内部框架的宽度与Canvas宽度，确保内容正常换行
        self.scrollable_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
    def bind_events(self):
        """绑定鼠标滚轮事件到Canvas及其所有子组件，实现整体滚动。"""
        # 绑定到整个应用，确保无论鼠标在哪个组件上都能滚动
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
    def _on_mousewheel(self, event):
        """处理鼠标滚轮事件，实现垂直滚动。"""
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    def _on_frame_configure(self, event):
        """当内部可滚动框架的大小改变时，更新Canvas的滚动区域，并确保内部框架宽度与Canvas一致。"""
        # 更新Canvas的滚动区域，使其适应scrollable_frame的实际内容大小
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        # 让内部scrollable_frame的宽度与Canvas的当前宽度一致
        self.canvas.itemconfig(self.scrollable_frame_id, width=self.canvas.winfo_width())
    def _on_canvas_configure(self, event):
        """当Canvas的大小改变时，确保内部可滚动框架的宽度与其一致。"""
        # 让内部scrollable_frame的宽度与Canvas的当前宽度一致
        self.canvas.itemconfig(self.scrollable_frame_id, width=event.width) 