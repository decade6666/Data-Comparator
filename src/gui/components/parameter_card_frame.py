import tkinter as tk
from tkinter import ttk

class ParameterCardFrame(ttk.Frame):
    """参数卡片展示框架：不含内部滑块，横向排布、根据窗口宽度自动换行，卡片更紧凑。"""
    def __init__(self, parent, **kwargs):
        kwargs.pop('height', None)  # 不固定高度
        super().__init__(parent, **kwargs)

        # 仅使用容器，不引入内部滚动条；整体界面外部滚动由上层控制
        self.container = tk.Frame(self, bg='#fff3cd')
        self.container.pack(fill=tk.BOTH, expand=True)

        # 布局状态
        self.current_row = 0
        self.current_col = 0
        self.max_cols = 6
        self.cards_info = []

        # 响应尺寸变化，动态计算列数
        self.bind('<Configure>', self._on_size_changed)

        # 紧凑布局估算：单卡片宽度（用于列数估算）
        self.ESTIMATED_CARD_PX = 80  # 近似值，仅用于列数估算

    def _on_size_changed(self, event):
        container_width = max(1, self.winfo_width())
        new_max_cols = max(1, min(24, container_width // self.ESTIMATED_CARD_PX))
        if new_max_cols != self.max_cols:
            self.max_cols = new_max_cols
            self.refresh_layout()

    def add_parameter_card(self, text, category):
        card_bg = '#fff3cd'
        border_color = '#ffeeba'
        # 紧凑：更小边距与内边距，不固定宽度
        card_frame = tk.Frame(
            self.container,
            relief='solid', bd=1,
            bg=card_bg,
            highlightbackground=border_color,
            highlightcolor=border_color,
            highlightthickness=1,
            padx=3, pady=1
        )

        display_text = text
        if len(text) > 10:
            display_text = text[:10] + '...'

        label = tk.Label(
            card_frame,
            text=display_text,
            font=('微软雅黑', 9),  # 小号字体
            bg=card_bg, fg='#333333',
            justify='left', anchor='w'
        )
        label.pack(fill='both', expand=True)

        if len(text) > 10:
            def show_tooltip(event):
                tooltip = tk.Toplevel()
                tooltip.wm_overrideredirect(True)
                tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
                tip = tk.Label(tooltip, text=text, background='#ffffe0', foreground='#000',
                               font=('微软雅黑', 8), relief='solid', bd=1, padx=5, pady=2)
                tip.pack()
                tooltip.after(3000, tooltip.destroy)
            label.bind('<Enter>', show_tooltip)
            label.bind('<Leave>', lambda e: None)

        # 放置：不拉伸，保持紧凑
        card_frame.grid(row=self.current_row, column=self.current_col, padx=2, pady=2, sticky='w')
        self.cards_info.append((text, category))

        self.current_col += 1
        if self.current_col >= self.max_cols:
            self.current_col = 0
            self.current_row += 1

        return card_frame

    def clear_cards(self):
        for widget in self.container.winfo_children():
            widget.destroy()
        self.current_row = 0
        self.current_col = 0
        self.cards_info = []

    def refresh_layout(self):
        saved = self.cards_info.copy()
        self.clear_cards()
        for text, category in saved:
            self.add_parameter_card(text, category) 