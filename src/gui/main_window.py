import tkinter as tk
from tkinter import messagebox, filedialog as Fieldialog
import ttkbootstrap as ttk
import threading
import datetime
import os
import tkinter.colorchooser
import tkinter.simpledialog
import tkinter.font as tkfont
import json # 导入json模块用于导入导出配置
import sys # 导入sys模块
import warnings # 导入warnings模块

# 忽略 openpyxl 的特定 UserWarning
warnings.filterwarnings("ignore", category=UserWarning, module='openpyxl.styles.stylesheet')

# 导入重构后的模块
from ..utils.gui_update_manager import GUIUpdateManager, GUIUpdateType
from .parameter_manager import ParameterManager, BUILTIN_TEMPLATE_CIMS, BUILTIN_TEMPLATE_TM
from ..utils.file_utils import set_window_icon, validate_excel_file, get_sheet_names, read_single_sheet_from_excel, check_and_remove_file_protection, reorder_columns_with_update_mark_first, get_resource_path, remove_auto_filters_from_xlsx, cleanup_nofilter_files, get_app_temp_dir
# 导入对话框函数
from .dialogs.error_dialog import show_file_error_dialog
from .dialogs.help_dialog import show_help

from ..utils.progress_manager import ThreadSafeProgressManager
from ..utils.logger import log # 更新导入路径
from ..core.data_comparison import process_single_sheet_complete, perform_full_comparison, process_missing_sheet, process_new_sheet, create_anchor_by_sas_names, compare_columns_by_sas_names, process_edc_multithreaded
from ..core.excel_utils import replace_worksheet_headers, apply_highlight_to_worksheet
from .components.parameter_card_frame import ParameterCardFrame
from .components.scrollable_frame import ScrollableFrame
from .components.top_operations_bar import TopOperationsBar

# 从原始文件导入 ConfigManager 和 HighlightOptimizer (假设它们已从原始文件独立出来)
from ..utils.config_manager import ConfigManager
from ..utils.highlight_optimizer import HighlightOptimizer

# 确保 HighlightOptimizer 在这里被实例化为全局变量，就像它在原始文件中一样
highlight_optimizer = HighlightOptimizer()

# 新增：文件名清理工具，确保配置名称可安全用于文件名
def _sanitize_filename(name: str) -> str:
    invalid = '\\/:*?"<>|\n\r\t'
    sanitized = ''.join(('-' if ch in invalid else ch) for ch in (name or '').strip())
    # 去除前后空格与多余的连字符
    sanitized = '-'.join([seg for seg in sanitized.split('-') if seg])
    return sanitized or '默认配置'

class _ListEditorDialog(tk.Toplevel):
    """一个通用的、用于编辑列表参数的对话框。"""
    def __init__(self, parent, title, prompt, initial_data_list):
        super().__init__(parent)
        self.transient(parent)
        self.title(title)
        set_window_icon(self)
        self.parent = parent
        self.result = None

        ttk.Label(self, text=prompt, font=('微软雅黑', 10)).pack(padx=15, pady=(10, 5))

        # Text widget with a scrollbar
        text_frame = ttk.Frame(self)
        text_frame.pack(padx=15, pady=(0, 10), fill="both", expand=True)
        self.text = tk.Text(text_frame, width=60, height=15, font=('Consolas', 10))
        scrollbar = ttk.Scrollbar(text_frame, command=self.text.yview)
        self.text.config(yscrollcommand=scrollbar.set)
        
        self.text.insert("1.0", "\n".join(initial_data_list))
        
        self.text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.buttonbox()
        self.grab_set()

        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.geometry(f"+{parent.winfo_rootx()+50}+{parent.winfo_rooty()+50}")
        self.text.focus_set()
        self.wait_window(self)

    def buttonbox(self):
        box = ttk.Frame(self)
        ttk.Button(box, text="确定", width=10, command=self.ok, style="secondary").pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(box, text="取消", width=10, command=self.cancel,style="secondary").pack(side=tk.LEFT, padx=5, pady=5)
        self.bind("<Escape>", self.cancel)
        box.pack()

    def ok(self, event=None):
        raw_text = self.text.get("1.0", tk.END)
        # Split by newline or comma, strip whitespace, and filter out empty strings
        items = [item.strip() for line in raw_text.split('\n') for item in line.split(',') if item.strip()]
        self.result = items
        self.destroy()

    def cancel(self, event=None):
        self.result = None # Ensure result is None on cancel
        self.destroy()

class _DictEditorDialog(tk.Toplevel):
    """一个通用的、用于编辑字典参数（键: 值列表）的对话框。"""
    def __init__(self, parent, title, prompt, initial_data_dict):
        super().__init__(parent)
        self.transient(parent)
        self.title(title)
        set_window_icon(self)
        self.parent = parent
        self.result = None

        ttk.Label(self, text=prompt, font=('微软雅黑', 10)).pack(padx=15, pady=(10, 5))

        text_frame = ttk.Frame(self)
        text_frame.pack(padx=15, pady=(0, 10), fill="both", expand=True)
        self.text = tk.Text(text_frame, width=80, height=15, font=('Consolas', 10))
        scrollbar = ttk.Scrollbar(text_frame, command=self.text.yview)
        self.text.config(yscrollcommand=scrollbar.set)
        
        initial_text = "\n".join([f"{key}: {', '.join(values)}" for key, values in initial_data_dict.items()])
        self.text.insert("1.0", initial_text)
        
        self.text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.buttonbox()
        self.grab_set()

        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.geometry(f"+{parent.winfo_rootx()+50}+{parent.winfo_rooty()+50}")
        self.text.focus_set()
        self.wait_window(self)

    def buttonbox(self):
        box = ttk.Frame(self)
        ttk.Button(box, text="确定", width=10, command=self.ok, style="primary").pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(box, text="取消", width=10, command=self.cancel, style="secondary").pack(side=tk.LEFT, padx=5, pady=5)
        self.bind("<Escape>", self.cancel)
        box.pack()

    def ok(self, event=None):
        raw_text = self.text.get("1.0", tk.END)
        self.result = {}
        try:
            for line in raw_text.split('\n'):
                line = line.strip()
                if not line or ':' not in line:
                    continue
                key, values_str = line.split(':', 1)
                key = key.strip()
                values = [v.strip() for v in values_str.split(',') if v.strip()]
                if key and values:
                    self.result[key] = values
            self.destroy()
        except Exception as e:
            messagebox.showerror("格式错误", f"输入格式有误，请检查后重试。\n错误: {e}", parent=self)

    def cancel(self, event=None):
        self.result = None
        self.destroy()

class _CustomDialog(tk.Toplevel):
    """一个自定义的、更宽的输入对话框。"""
    def __init__(self, parent, title=None, prompt=None, initialvalue=""):
        super().__init__(parent)
        self.transient(parent)
        self.title(title)
        set_window_icon(self)
        self.parent = parent
        self.result = None

        body = ttk.Frame(self)
        self.initial_focus = self.body(body, prompt, initialvalue)
        body.pack(padx=15, pady=15)

        self.buttonbox()
        self.grab_set()

        if not self.initial_focus:
            self.initial_focus = self

        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.geometry(f"+{parent.winfo_rootx()+50}+{parent.winfo_rooty()+50}")
        self.initial_focus.focus_set()
        self.wait_window(self)

    def body(self, master, prompt, initialvalue):
        ttk.Label(master, text=prompt, wraplength=300).pack(pady=(0, 10))
        self.entry = ttk.Entry(master, width=50)
        self.entry.pack()
        if initialvalue:
            self.entry.insert(0, initialvalue)
            self.entry.select_range(0, tk.END)
        return self.entry

    def buttonbox(self):
        box = ttk.Frame(self)
        ttk.Button(box, text="确定", width=10, command=self.ok, style="primary").pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(box, text="取消", width=10, command=self.cancel, style="secondary").pack(side=tk.LEFT, padx=5, pady=5)
        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel)
        box.pack()

    def ok(self, event=None):
        self.result = self.entry.get()
        self.withdraw()
        self.update_idletasks()
        self.parent.focus_set()
        self.destroy()

    def cancel(self, event=None):
        self.parent.focus_set()
        self.destroy()

class _AdvancedSettingsDialog(tk.Toplevel):
    """高级设置弹窗：设置线程数与深色模式。"""
    def __init__(self, parent, title="高级设置", init_workers=1, init_dark=False, max_workers_cap=None):
        super().__init__(parent)
        self.transient(parent)
        self.title(title)
        set_window_icon(self)
        self.parent = parent
        self.result = None

        self.workers_var = tk.IntVar(value=max(1, int(init_workers)))
        self.dark_var = tk.BooleanVar(value=bool(init_dark))

        cap = max_workers_cap if isinstance(max_workers_cap, int) and max_workers_cap > 0 else (os.cpu_count() or 8)

        body = ttk.Frame(self)
        body.pack(padx=15, pady=15, fill=tk.BOTH, expand=True)

        # 线程数
        row0 = ttk.Frame(body)
        row0.pack(fill=tk.X, pady=(0,8))
        ttk.Label(row0, text="最大线程数:").pack(side=tk.LEFT)
        self.workers_spin = tk.Spinbox(row0, from_=1, to=max(1, cap*2), textvariable=self.workers_var, width=8)
        self.workers_spin.pack(side=tk.LEFT, padx=(8,0))

        # 深色模式
        row1 = ttk.Frame(body)
        row1.pack(fill=tk.X)
        ttk.Checkbutton(row1, text="启用深色模式", variable=self.dark_var).pack(side=tk.LEFT)

        # 操作按钮
        btns = ttk.Frame(self)
        btns.pack(pady=(10, 10))
        ttk.Button(btns, text="确定", command=self._ok, style="primary").pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="取消", command=self._cancel, style="secondary").pack(side=tk.LEFT, padx=5)

        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.geometry(f"+{parent.winfo_rootx()+80}+{parent.winfo_rooty()+80}")
        self.workers_spin.focus_set()
        self.wait_window(self)

    def _ok(self):
        try:
            value = int(self.workers_var.get())
            if value <= 0:
                raise ValueError("线程数必须大于0")
            self.result = {"max_workers": value, "dark_mode": bool(self.dark_var.get())}
            self.destroy()
        except Exception as e:
            messagebox.showerror("无效参数", f"请输入有效的线程数(>0)。\n错误: {e}", parent=self)

    def _cancel(self):
        self.result = None
        self.destroy()

class DatasetComparatorGUI:
    """数据集比对程序主GUI类。
    负责构建、管理用户界面，处理用户交互，并协调数据比对任务的启动、停止和进度显示。
    """
    def __init__(self, root):
        self.root = root
        self.root.app = self  # 将app实例附加到root窗口
        self.root.title("比对程序_V1.6.3")
        self.root.geometry("1200x800")
        self._name_tooltip = None
        # 统一默认字体与尺寸（不强制覆盖显式声明的字体）
        try:
            available = {f.lower() for f in tkfont.families(self.root)}
            preferred = ["Microsoft YaHei UI", "Microsoft YaHei", "微软雅黑", "SimHei", "Segoe UI", "Arial"]
            chosen = next((f for f in preferred if f.lower() in available), None)
            if chosen:
                font_spec = f"{{{chosen}}} 10" if " " in chosen else f"{chosen} 10"
                self.root.option_add("*Font", font_spec)
        except Exception:
            pass

        # 让主窗口的行列可伸缩
        self.root.columnconfigure(0, weight=1)
        # 主内容在第2行（row=2）的分栏面板需要占据剩余空间
        self.root.rowconfigure(2, weight=1)

        # Initialize managers
        self.parameter_manager = ParameterManager(self)
        self.config_manager = ConfigManager()
        self.gui_update_manager = GUIUpdateManager(self.root)
        self.stop_flag = threading.Event()

        # Log file related attributes that were missing
        self.log_file_path = None
        self.log_file_lock = threading.Lock()
        self.start_time = None
        self.is_processing = False
        self.tooltip_label = None

        # Initialize variables for UI components
        self.old_path_var = tk.StringVar()
        self.new_path_var = tk.StringVar()
        self.output_dir_var = tk.StringVar()
        # 恢复为两个独立的行号参数
        self.anchor_row_num_var = tk.IntVar(value=1)
        self.header_row_num_var = tk.IntVar(value=1)

        self.max_workers_var = tk.IntVar(value=os.cpu_count())
        self.highlight_color_var = tk.StringVar(value='#FFE5E5')
        self.missing_color_var = tk.StringVar(value='#DC143C')
        self.new_color_var = tk.StringVar(value='#00FF00')
        self.progress_var = tk.DoubleVar()
        self.progress_label_var = tk.StringVar(value="准备就绪")
        self.dark_mode_var = tk.BooleanVar(value=False)
        self.merge_deleted_data_var = tk.BooleanVar(value=True)

        # 强制使用浅色主题与白色底色作为默认
        try:
            if hasattr(self.root, 'style') and hasattr(self.root.style, 'theme_use'):
                self.root.style.theme_use('flatly')
        except Exception:
            pass
        try:
            self.root.configure(bg='white')
        except Exception:
            pass

        # --- Top Operations Frame ---
        top_bar_callbacks = {
            'start': self.start_processing,
            'stop': self.stop_processing,
            'advanced': self._open_advanced_settings_dialog,
            'help': lambda: show_help(self.root),
        }
        self.top_bar = TopOperationsBar(self.root, top_bar_callbacks)
        self.top_bar.grid(row=0, column=0, sticky='ew', padx=10, pady=(6, 2))

        # PanedWindow for left (config list) and right (config details)
        self.main_pane = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL, style="secondary")
        self.main_pane.grid(row=2, column=0, sticky='nsew', padx=10, pady=(0,6))
        
        # --- Left Panel: Config Management ---
        left_frame = ttk.Frame(self.main_pane, width=250)
        self.main_pane.add(left_frame, weight=1)

        ttk.Label(left_frame, text="配置管理").pack(pady=(5, 0), padx=10, anchor='w')
        
        # 配置操作按钮行（放在"配置管理"文字下方）
        cfg_btns = ttk.Frame(left_frame)
        cfg_btns.pack(fill=tk.X, padx=10, pady=(2, 5))
        self.btn_new_config = ttk.Button(cfg_btns, text="新建", style="secondary-outline", command=self._create_new_config)
        self.btn_new_config.pack(side=tk.LEFT, padx=(0,4))
        self.btn_delete_config = ttk.Button(cfg_btns, text="删除", style="danger-outline", command=self._delete_selected_config_from_button)
        self.btn_delete_config.pack(side=tk.LEFT, padx=4)
        self.btn_copy_config = ttk.Button(cfg_btns, text="复制", bootstyle="secondary-outline", command=self._copy_selected_config)
        self.btn_copy_config.pack(side=tk.LEFT, padx=4)
        self.btn_rename_config = ttk.Button(cfg_btns, text="重命名", style="secondary-outline", command=self._rename_selected_config)
        self.btn_rename_config.pack(side=tk.LEFT, padx=4)
        self.btn_import_config = ttk.Button(cfg_btns, text="导入", style="secondary-outline", command=self._import_config)
        self.btn_import_config.pack(side=tk.LEFT, padx=4)
        self.btn_export_config = ttk.Button(cfg_btns, text="导出", style="secondary-outline", command=self._export_current_config)
        self.btn_export_config.pack(side=tk.LEFT, padx=4)
        
        self.config_listbox = tk.Listbox(left_frame, selectbackground="#0078d7", selectforeground="white", borderwidth=0, highlightthickness=0, exportselection=0)
        self.config_listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self.config_listbox.bind('<<ListboxSelect>>', self._on_config_select)
        self._populate_config_listbox()
        
        # 在初始时根据当前选择更新按钮状态
        self._update_config_action_buttons_state()
        
        # --- Right Panel: Configuration Details ---
        right_frame_container = ttk.Frame(self.main_pane)
        self.main_pane.add(right_frame_container, weight=4)

        self.config_name_label_var = tk.StringVar()
        header_bar = ttk.Frame(right_frame_container)
        header_bar.pack(fill=tk.X, pady=(2,2), padx=10)
        header_bar.grid_columnconfigure(0, weight=1)
        header_bar.grid_columnconfigure(1, weight=0)
        # 可截断显示的配置名称标签，超出以...显示，并提供悬停提示
        self.config_name_label = ttk.Label(header_bar, textvariable=self.config_name_label_var)
        self.config_name_label.grid(row=0, column=0, sticky='w', padx=(0,8))

        # 悬浮提示函数定义（在绑定前定义，避免NameError）
        def _show_full_name(event):
            try:
                if hasattr(self, '_name_tooltip') and self._name_tooltip is not None: 
                    self._name_tooltip.destroy()
                self._name_tooltip = tk.Toplevel(self.root)
                self._name_tooltip.wm_overrideredirect(True)
                x = event.x_root + 10
                y = event.y_root + 10
                self._name_tooltip.wm_geometry(f"+{x}+{y}")
                tk.Label(self._name_tooltip, text=self.parameter_manager.current_config_name,
                         bg='#ffffe0', fg='#000', relief='solid', bd=1, padx=6, pady=3,
                         font=('微软雅黑', 9)).pack()
                self._name_tooltip.after(2500, self._name_tooltip.destroy)
            except Exception:
                pass
        def _hide_full_name(event):
            try:
                if hasattr(self, '_name_tooltip') and self._name_tooltip is not None:
                    self._name_tooltip.destroy()
                    self._name_tooltip = None
            except Exception:
                pass

        self.config_name_label.bind('<Enter>', _show_full_name)
        self.config_name_label.bind('<Leave>', _hide_full_name)

        # 右上角：高级设置按钮
        # 顶部操作栏已包含"高级设置"，此处移除按钮
        # 第二行：保存按钮位于名称下方、靠左
        self.btn_save_config = ttk.Button(header_bar, text="保存", command=self.save_current_configuration, style="secondary")
        self.btn_save_config.grid(row=1, column=0, sticky='w', pady=(4,0))
        try:
            self.btn_save_config.configure(width=16)
        except Exception:
            pass

        # 在"保存"右侧添加"快速编辑"按钮
        self.btn_quick_edit = ttk.Button(header_bar, text="快速编辑", command=self._open_quick_edit_dialog, style="secondary")
        self.btn_quick_edit.grid(row=1, column=1, sticky='w', padx=(4,0), pady=(4,0))
        try:
            self.btn_quick_edit.configure(width=16)
        except Exception:
            pass

        # --- 中英文参数名映射 ---
        self.KEY_MAP_EN_TO_ZH = {
            'old_file_path': '旧版本文件路径', 'new_file_path': '新版本文件路径',
            'output_directory': '输出目录', 'anchor_row_num': '锚点行号',
            'header_row_num': '表头行号', 'max_workers': '最大线程数',
            'merge_deleted_data': '合并删除数据',
            'common_cols': '排除列', 'exclude_sheets': '排除Sheet',
            'default_keys': '默认锚点', 'sheet_key_map': '指定Sheet锚点',
            'colors': '颜色配置'
        }
        self.COLOR_KEY_MAP_EN_TO_ZH = {
            'highlight_fill': '更新标记颜色', 'missing_sheet_tab': '删除标记颜色',
            'new_sheet_tab': '新增标记颜色'
        }
        self.KEY_MAP_ZH_TO_EN = {v: k for k, v in self.KEY_MAP_EN_TO_ZH.items()}
        self.COLOR_KEY_MAP_ZH_TO_EN = {v: k for k, v in self.COLOR_KEY_MAP_EN_TO_ZH.items()}


        # Create a Canvas and a Scrollbar for the right panel
        self.canvas = tk.Canvas(right_frame_container, borderwidth=0, highlightthickness=0, bg='white')
        # 使用实例属性保存滚动条，并确保先于Canvas打包，避免窄窗口时被Canvas挤占导致不可见
        self.right_scrollbar = ttk.Scrollbar(right_frame_container, orient="vertical", command=self.canvas.yview)
        self.config_params_frame = ttk.Frame(self.canvas)

        self.config_params_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        
        self.config_params_frame_id = self.canvas.create_window((0, 0), window=self.config_params_frame, anchor="nw")
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfig(self.config_params_frame_id, width=e.width))

        self.canvas.configure(yscrollcommand=self.right_scrollbar.set)
        
        # 先打包滚动条，再打包Canvas，确保任何情况下滚动条都有空间显示
        self.right_scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        
        # --- Widgets inside the scrollable right panel ---
        self._create_path_selection_widgets(self.config_params_frame)
        self._create_preset_and_structure_widgets(self.config_params_frame)
        self._create_color_settings_widgets(self.config_params_frame)
        self._create_parameter_cards(self.config_params_frame)
        self._create_advanced_settings_widgets(self.config_params_frame)

        # Progress bar and status (move directly under start/stop)
        progress_frame = ttk.Labelframe(self.root, text="进度", padding=8, style="info")
        progress_frame.grid(row=1, column=0, sticky='ew', padx=10, pady=(0,4))
        ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100, style="info-striped").pack(fill=tk.X, padx=4, pady=2, expand=True)
        ttk.Label(progress_frame, textvariable=self.progress_label_var).pack(fill=tk.X, padx=4, pady=0)

        # Initialize log file before loading settings（默认放到应用临时目录）
        output_dir = get_app_temp_dir()
        self._initialize_log_file(output_dir)

        # Initialize UI with current config
        self.load_all_settings_from_parameter_manager()
        self._update_current_config_display()
        self._select_config_in_listbox(self.parameter_manager.current_config_name)


    def _translate_params(self, params, key_map, color_key_map):
        """通用参数名翻译函数。"""
        translated = {}
        for key, value in params.items():
            new_key = key_map.get(key, key)
            if key == 'colors' and isinstance(value, dict):
                translated[new_key] = {color_key_map.get(k, k): v for k, v in value.items()}
            else:
                translated[new_key] = value
        return translated

    def _translate_params_to_chinese(self, params):
        """将参数字典的键翻译成中文。"""
        return self._translate_params(params, self.KEY_MAP_EN_TO_ZH, self.COLOR_KEY_MAP_EN_TO_ZH)

    def _translate_params_to_english(self, params):
        """将参数字典的键翻译成英文。"""
        return self._translate_params(params, self.KEY_MAP_ZH_TO_EN, self.COLOR_KEY_MAP_ZH_TO_EN)

    def _create_parameter_cards(self, parent_frame):
        
        def create_card_with_button(parent, text, command):
            frame = ttk.Labelframe(parent, text=text, padding=10, style="info" )
            frame.pack(fill=tk.X, pady=4, padx=10, anchor='n')
            
            content_frame = ttk.Frame(frame, padding=(4, 2))
            content_frame.pack(fill=tk.BOTH, expand=True)
            
            # 使用 grid 保证右侧按钮列拥有固定空间，不被参数内容覆盖
            content_frame.grid_columnconfigure(0, weight=1)
            content_frame.grid_columnconfigure(1, weight=0, minsize=72)

            card_frame = ParameterCardFrame(content_frame)
            card_frame.grid(row=0, column=0, sticky='ew', padx=(0, 6))
            
            button_frame = ttk.Frame(content_frame)
            button_frame.grid(row=0, column=1, sticky='n')
            btn = ttk.Button(button_frame, text="修改", command=command, style="secondary")
            btn.pack(anchor='n')
            
            return card_frame, btn

        # 排除列
        self.common_cols_card_frame, self.btn_edit_common_cols = create_card_with_button(parent_frame, '排除字段', self._edit_exclude_cols)
        # 排除sheet
        self.exclude_sheets_card_frame, self.btn_edit_exclude_sheets = create_card_with_button(parent_frame, '排除表单', self._edit_exclude_sheets)
        # 默认锚点
        self.default_keys_card_frame, self.btn_edit_default_keys = create_card_with_button(parent_frame, '默认锚点', self._edit_default_anchors)
        # sheet锚点
        self.sheet_key_map_card_frame, self.btn_edit_sheet_keys = create_card_with_button(parent_frame, '自定义锚点', self._edit_sheet_anchors)

    def _create_advanced_settings_widgets(self, parent_frame):
        # 主界面不再显示"高级设置"卡片
        return

    def _create_path_selection_widgets(self, parent_frame):
        file_frame = ttk.Labelframe(parent_frame, text='路径选择', padding=10, style="info")
        file_frame.pack(fill=tk.X, pady=5, padx=10, anchor='n')
        file_frame.columnconfigure(1, weight=1) # 让Entry自适应宽度
        
        ttk.Label(file_frame, text='旧版本文件:').grid(row=0, column=0, sticky=tk.W, pady=2)
        self.entry_old_file = ttk.Entry(file_frame, width=60, textvariable=self.old_path_var)
        self.entry_old_file.grid(row=0, column=1, padx=5, sticky=tk.EW)
        self.btn_browse_old = ttk.Button(file_frame, text='浏览...', command=lambda: self.browse_file(self.old_path_var), style="secondary-outline")
        self.btn_browse_old.grid(row=0, column=2, padx=(5, 0))
        
        ttk.Label(file_frame, text='新版本文件:').grid(row=1, column=0, sticky=tk.W, pady=2)
        self.entry_new_file = ttk.Entry(file_frame, width=60, textvariable=self.new_path_var)
        self.entry_new_file.grid(row=1, column=1, padx=5, sticky=tk.EW)
        self.btn_browse_new = ttk.Button(file_frame, text='浏览...', command=lambda: self.browse_file(self.new_path_var), style="secondary-outline")
        self.btn_browse_new.grid(row=1, column=2, padx=(5, 0))
        
        ttk.Label(file_frame, text='输出目录:').grid(row=2, column=0, sticky=tk.W, pady=2)
        self.entry_output_dir = ttk.Entry(file_frame, width=60, textvariable=self.output_dir_var)
        self.entry_output_dir.grid(row=2, column=1, padx=5, sticky=tk.EW)
        self.btn_browse_output = ttk.Button(file_frame, text='浏览...', command=self.browse_directory, style="secondary-outline")
        self.btn_browse_output.grid(row=2, column=2, padx=(5, 0))
        
    def _create_preset_and_structure_widgets(self, parent_frame):
        # 无标题的结构设置区域：将锚点行号与表头行号直接放在界面上
        settings_frame = ttk.Frame(parent_frame)
        settings_frame.pack(fill=tk.X, pady=5, padx=10, anchor='n')

        ttk.Label(settings_frame, text="锚点行号:").grid(row=0, column=0, padx=(0, 5), pady=5, sticky=tk.W)
        self.entry_anchor_row_num = ttk.Entry(settings_frame, textvariable=self.anchor_row_num_var, width=10)
        self.entry_anchor_row_num.grid(row=0, column=1, padx=(0, 20), pady=5, sticky=tk.W)

        ttk.Label(settings_frame, text="表头行号:").grid(row=0, column=2, padx=(0, 5), pady=5, sticky=tk.W)
        self.entry_header_row_num = ttk.Entry(settings_frame, textvariable=self.header_row_num_var, width=10)
        self.entry_header_row_num.grid(row=0, column=3, pady=5, sticky=tk.W)

        # 在表头行号右侧添加"合并删除数据"复选框
        self.chk_merge_deleted_data = ttk.Checkbutton(
            settings_frame,
            text="合并删除数据",
            variable=self.merge_deleted_data_var
        )
        self.chk_merge_deleted_data.grid(row=0, column=4, padx=(20, 0), pady=5, sticky=tk.W)

    def _create_color_settings_widgets(self, parent_frame):
        color_frame = ttk.Labelframe(parent_frame, text='颜色设置', padding=10, style="info")
        color_frame.pack(fill=tk.X, pady=5, padx=10, anchor='n')

        # '更新' color
        ttk.Label(color_frame, text='更新:').grid(row=0, column=0, sticky=tk.W, pady=2, padx=(0, 5))
        self.highlight_color_btn = tk.Button(color_frame, width=4, relief='flat',
                                           command=self.choose_highlight_color) 
        self.highlight_color_btn.grid(row=0, column=1, pady=2, sticky=tk.W)
        ttk.Label(color_frame, textvariable=self.highlight_color_var, font=('Consolas', 9)).grid(row=0, column=2, padx=(5, 20), pady=2, sticky=tk.W) 
        
        # '删除' color
        ttk.Label(color_frame, text='删除:').grid(row=0, column=3, sticky=tk.W, pady=2, padx=(0, 5))
        self.missing_color_btn = tk.Button(color_frame, width=4, relief='flat',
                                         command=self.choose_missing_color) 
        self.missing_color_btn.grid(row=0, column=4, pady=2, sticky=tk.W)
        ttk.Label(color_frame, textvariable=self.missing_color_var, font=('Consolas', 9)).grid(row=0, column=5, padx=(5, 20), pady=2, sticky=tk.W) 
        
        # '新增' color
        ttk.Label(color_frame, text='新增:').grid(row=0, column=6, sticky=tk.W, pady=2, padx=(0, 5))
        self.new_color_btn = tk.Button(color_frame, width=4, relief='flat',
                                     command=self.choose_new_color) 
        self.new_color_btn.grid(row=0, column=7, pady=2, sticky=tk.W)
        ttk.Label(color_frame, textvariable=self.new_color_var, font=('Consolas', 9)).grid(row=0, column=8, pady=2, sticky=tk.W) 

        # 设置颜色按钮的初始颜色
        self.root.after_idle(self._update_color_buttons_appearance)

    def _open_advanced_settings_dialog(self):
        dialog = _AdvancedSettingsDialog(
            self.root,
            init_workers=self.max_workers_var.get(),
            init_dark=self.dark_mode_var.get(),
            max_workers_cap=os.cpu_count() or 8
        )
        if dialog.result is not None:
            self.max_workers_var.set(dialog.result["max_workers"])
            self.dark_mode_var.set(dialog.result["dark_mode"])
            # 立即应用主题
            self._toggle_dark_mode()

    def _update_color_buttons_appearance(self):
        """Helper to update color button visuals based on variables."""
        try:
            # Highlight color button
            highlight_color = self.highlight_color_var.get()
            self.highlight_color_btn.config(bg=highlight_color)
            
            # Missing color button
            missing_color = self.missing_color_var.get()
            self.missing_color_btn.config(bg=missing_color)

            # New color button
            new_color = self.new_color_var.get()
            self.new_color_btn.config(bg=new_color)
        except tk.TclError as e:
            # This can happen if the window is closed while the after_idle callback runs
            print(f"Could not update color button appearance: {e}")

    def _apply_base_colors_recursive(self, widget, bg_color, fg_color):
        """对常见 tk 基础控件递归应用底色/前景色。仅处理 tk.* 控件，避免干扰 ttk 主题。"""
        try:
            # 不处理 tk.Button，以免覆盖颜色选择按钮的背景色
            if isinstance(widget, (tk.Frame, tk.Label, tk.Listbox, tk.Text, tk.Canvas, tk.Scrollbar)):
                try:
                    widget.configure(bg=bg_color)
                except Exception:
                    pass
                try:
                    widget.configure(fg=fg_color)
                except Exception:
                    pass
                # 提升可读性：Entry 插入光标颜色
                if isinstance(widget, tk.Entry):
                    try:
                        widget.configure(insertbackground=fg_color)
                    except Exception:
                        pass
        except Exception:
            pass

        # 递归到子控件
        try:
            for child in widget.winfo_children():
                self._apply_base_colors_recursive(child, bg_color, fg_color)
        except Exception:
            pass

    def _toggle_dark_mode(self):
        """切换深色/浅色底色。"""
        use_dark = bool(self.dark_mode_var.get())
        bg_color = 'black' if use_dark else 'white'
        fg_color = 'white' if use_dark else 'black'
        # 切换 ttkbootstrap 主题
        try:
            if hasattr(self.root, 'style') and hasattr(self.root.style, 'theme_use'):
                target_theme = 'darkly' if use_dark else 'flatly'
                self.root.style.theme_use(target_theme)
        except Exception:
            pass
        # 根窗口与画布
        try:
            self.root.configure(bg=bg_color)
        except Exception:
            pass
        try:
            if hasattr(self, 'canvas') and self.canvas.winfo_exists():
                self.canvas.configure(bg=bg_color)
        except Exception:
            pass
        # 左侧 Listbox 等 tk 控件
        try:
            if hasattr(self, 'config_listbox') and self.config_listbox.winfo_exists():
                self.config_listbox.configure(bg=bg_color, fg=fg_color, highlightbackground=bg_color)
        except Exception:
            pass
        # 颜色按钮的边界与激活底色
        for btn in [getattr(self, 'highlight_color_btn', None), getattr(self, 'missing_color_btn', None), getattr(self, 'new_color_btn', None)]:
            if btn is None:
                continue
            try:
                btn.configure(activebackground=bg_color, highlightbackground=bg_color)
            except Exception:
                pass
        # 尽力对 tk.* 控件递归覆写底色/前景色，避免遗漏
        self._apply_base_colors_recursive(self.root, bg_color, fg_color)
        # 恢复颜色按钮本身的背景显示
        self._update_color_buttons_appearance()

        def _load_config_from_dropdown(self, config_name):
         """从下拉菜单选择配置时加载。"""
         if self.is_processing:
             self.log_message("正在比对中，无法切换配置。请先停止。", 'INFO')
             messagebox.showinfo("提示", "正在比对中，无法切换配置。请先停止。")
             return
         if self.parameter_manager.load_config(config_name):
             self.load_all_settings_from_parameter_manager()
             self.log_message(f"已加载配置: {config_name}", 'INFO')
         else:
             messagebox.showerror("加载失败", f"无法加载配置 '{config_name}'。")

    def _import_config(self):
        """导入配置。"""
        file_path = Fieldialog.askopenfilename(
            title="选择要导入的配置文件",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    raw_imported_params = json.load(f)
                
                # 导入时，自动将中文键名翻译回英文
                imported_params = self._translate_params_to_english(raw_imported_params)
                
                dialog = _CustomDialog(self.root, title="导入配置", prompt="请输入导入配置的名称:",
                                       initialvalue=os.path.splitext(os.path.basename(file_path))[0])
                new_config_name = dialog.result

                if new_config_name:
                    new_config_name = new_config_name.strip()
                    if not new_config_name:
                        messagebox.showwarning("名称无效", "配置名称不能为空。")
                        return
                    if new_config_name in self.parameter_manager.list_configurations():
                        if not messagebox.askyesno("覆盖确认", f"配置名称 '{new_config_name}' 已存在，是否覆盖？"):
                            return

                    if self.parameter_manager.save_config_as(new_config_name, imported_params):
                        self._populate_config_listbox() # 刷新列表
                        self.parameter_manager.load_config(new_config_name) # 加载导入的配置
                        self.load_all_settings_from_parameter_manager() # 更新UI
                        self._select_config_in_listbox(new_config_name) # 在列表中选中
                        self.log_message(f"已成功导入并加载配置: {new_config_name}", 'INFO')
                        messagebox.showinfo("导入成功", f"配置 '{new_config_name}' 已成功导入并加载！")
                    else:
                        messagebox.showerror("导入失败", "导入配置时发生错误。")
            except json.JSONDecodeError:
                messagebox.showerror("导入失败", "文件格式不正确，请选择有效的JSON配置文件。")
            except Exception as e:
                messagebox.showerror("导入失败", f"导入配置时发生错误：{e}")

    def _export_current_config(self):
        """导出当前配置。"""
        if self.is_processing:
            self.log_message("正在比对中，无法导出配置。请先停止。", 'INFO')
            messagebox.showinfo("提示", "正在比对中，无法导出配置。请先停止。")
            return
        if not self.parameter_manager.current_config_name:
            messagebox.showwarning("没有当前配置", "请先加载或保存一个配置。")
            return

        export_dir = Fieldialog.askdirectory(title="选择导出目录")
        if export_dir:
            current_params = self._collect_current_gui_parameters()
            
            # 导出前，仅移除内部使用的固定内容参数和不希望导出的运行时参数
            current_params.pop('anchor_row_content', None)
            current_params.pop('header_row_content', None)
            current_params.pop('max_workers', None)
            
            # 将键名翻译为中文
            translated_params = self._translate_params_to_chinese(current_params)
            
            export_path = os.path.join(export_dir, f"{self.parameter_manager.current_config_name}.json")
            try:
                with open(export_path, 'w', encoding='utf-8') as f:
                    # 以每个参数一行的格式写入纯JSON（数组/映射保持单行展示）
                    f.write("{\n")
                    items = list(translated_params.items())
                    for idx, (k, v) in enumerate(items):
                        value_str = json.dumps(v, ensure_ascii=False, separators=(',', ': '))
                        comma = "," if idx < len(items) - 1 else ""
                        f.write(f'    "{k}": {value_str}{comma}\n')
                    f.write("}\n")
                return True
            except Exception as e:
                messagebox.showerror("导出失败", f"导出配置时发生错误：{e}")
                return False

    def _initialize_log_file(self, output_dir):
        """Initialize log file in the given directory and write header + parameter section."""
        try:
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            # Record start time
            self.start_time = datetime.datetime.now()
            # 生成日志文件名：配置名称-比对日志-生成时间
            current_time = self.start_time.strftime("%Y-%m-%dT%H-%M-%S")
            config_name = getattr(self.parameter_manager, 'current_config_name', '') or ''
            safe_name = _sanitize_filename(config_name)
            log_filename = f"{safe_name}-比对日志-{current_time}.txt"
            self.log_file_path = os.path.join(output_dir, log_filename).replace('\\', '/')

            # Create log file and write header information
            with open(self.log_file_path, 'w', encoding='utf-8') as f:
                f.write("=" * 60 + "\n")
                f.write(f"比对程序 V1.6.3 - 处理日志\n")
                f.write(f"开始时间: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 60 + "\n\n")

                # Write parameter configuration information
                f.write("📝 参数配置信息:\n")
                f.write("-" * 40 + "\n")

                # 构造与导出配置完全一致的参数JSON
                current_params = self._collect_current_gui_parameters()
                # 与导出逻辑保持一致：移除不需要导出的运行时参数
                current_params.pop('anchor_row_content', None)
                current_params.pop('header_row_content', None)
                current_params.pop('max_workers', None)
                # 翻译为中文键名
                translated_params = self._translate_params_to_chinese(current_params)
                # 以每个参数一行的格式写入（数组/映射保持单行展示）
                f.write("{\n")
                items = list(translated_params.items())
                for idx, (k, v) in enumerate(items):
                    value_str = json.dumps(v, ensure_ascii=False, separators=(',', ': '))
                    comma = "," if idx < len(items) - 1 else ""
                    f.write(f'    "{k}": {value_str}{comma}\n')
                f.write("}\n")

                f.write("-" * 40 + "\n\n")
            return True
        except Exception as e:
            self.log_message(f"初始化日志文件失败: {str(e)}", 'ERROR')
            self.log_file_path = None
            return False

    def _collect_current_gui_parameters(self):
        """收集当前GUI界面上的所有参数值，构建一个干净的参数字典。"""
        parameters = {}
        # 1. 从UI控件直接获取的参数
        parameters['old_file_path'] = self.old_path_var.get()
        parameters['new_file_path'] = self.new_path_var.get()
        parameters['output_directory'] = self.output_dir_var.get()
        parameters['anchor_row_num'] = self.anchor_row_num_var.get()
        parameters['header_row_num'] = self.header_row_num_var.get()
        parameters['max_workers'] = self.max_workers_var.get()
        parameters['merge_deleted_data'] = bool(getattr(self, 'merge_deleted_data_var', tk.BooleanVar(value=True)).get())
        # 2. 从 ParameterManager 获取通过对话框等方式管理的复杂参数
        pm_params = self.parameter_manager.get_parameters()
        parameters['common_cols'] = pm_params.get('common_cols', [])
        parameters['exclude_sheets'] = pm_params.get('exclude_sheets', [])
        parameters['default_keys'] = pm_params.get('default_keys', [])
        parameters['sheet_key_map'] = pm_params.get('sheet_key_map', {})
        parameters['colors'] = pm_params.get('colors', {
            'highlight_fill': '#FFE5E5',
            'missing_sheet_tab': '#DC143C',
            'new_sheet_tab': '#00FF00'
        })
        # 3. 固定的内容参数（内部使用，导出/日志前剔除）
        parameters['anchor_row_content'] = 'SASFieldName'
        parameters['header_row_content'] = 'SASFieldLabel'
        return parameters
            
    def log_message(self, message, level='INFO'):
        """写入日志文件（线程安全）并输出到控制台（可选）。"""
        # 写入到文件
        if not getattr(self, 'log_file_path', None):
            # 即使没有日志文件，仍打印到控制台帮助定位
            print(message)
            return
        try:
            with self.log_file_lock:
                timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                log_entry = f"[{timestamp}] {message}\n"
                with open(self.log_file_path, 'a', encoding='utf-8') as f:
                    f.write(log_entry)
        except Exception as e:
            print(f"写入日志文件失败: {str(e)}")

    def _finalize_log_file(self):
        """Finalize log file recording"""
        if self.log_file_path:
            try:
                with self.log_file_lock:
                    end_time = datetime.datetime.now()
                    with open(self.log_file_path, 'a', encoding='utf-8') as f:
                        f.write("\n" + "=" * 60 + "\n")
                        f.write(f"结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                        
                        # Calculate and format total duration
                        if self.start_time:
                            total_seconds = int((end_time - self.start_time).total_seconds())
                            hours = total_seconds // 3600
                            minutes = (total_seconds % 3600) // 60
                            seconds = total_seconds % 60
                            
                            if hours > 0:
                                duration_str = f"{hours}小时{minutes}分钟{seconds}秒"
                            else:
                                duration_str = f"{minutes}分钟{seconds}秒"
                            
                            f.write(f"程序用时: {duration_str}\n")
                        
                        f.write("=" * 60 + "\n")
            except Exception as e:
                self.log_message(f"结束日志文件记录失败: {str(e)}", 'ERROR') # Use log_message here

    def update_progress(self, message, progress=None):
        """Update progress display - use GUI update manager
        Args:
            message: Main progress information
            progress: Progress percentage (0-100)
        """
        # Send progress update message via GUI update manager
        # data = {
        #     'message': message,
        #     'level': level
        # }
        # self.gui_update_manager.post_update(GUIUpdateType.LOG_MESSAGE, data)

        # Also write to log file directly
        self.gui_update_manager.post_update(GUIUpdateType.PROGRESS, {'message': message, 'progress': progress})
        
    def reset_progress(self):
        """Reset progress bar - use GUI update manager"""
        # Send reset progress message via GUI update manager
        self.gui_update_manager.post_update(GUIUpdateType.RESET_PROGRESS)
        
    def start_processing(self):
        if self.is_processing:
            return
        
        # 需求①：先保存配置再比对
        # 检查当前配置是否为模板配置，如果是且已修改，提醒用户先复制另存
        current_config_name = self.parameter_manager.current_config_name
        is_builtin_template = current_config_name in (BUILTIN_TEMPLATE_CIMS, BUILTIN_TEMPLATE_TM)
        
        if is_builtin_template:
            # 需求②：选择模板配置时，无论是否修改都要提醒
            result = messagebox.askyesnocancel(
                "使用模板配置", 
                f"当前配置 '{current_config_name}' 为内置模板。\n\n"
                "建议先复制另存为新配置再使用，以避免影响原始模板。\n\n"
                "是否现在复制另存为新配置？",
                icon='warning'
            )
            if result is None:  # 用户取消
                return
            elif result:  # 用户选择复制
                if not self._copy_template_before_processing():
                    return  # 复制失败，停止处理
        
        # 先验证路径信息
        current_params = self._collect_current_gui_parameters()
        old_path = current_params.get('old_file_path', '')
        new_path = current_params.get('new_file_path', '')
        output_dir = current_params.get('output_directory', '')
        
        # 验证路径是否为空
        if not all([old_path, new_path, output_dir]):
            self.log_message("请填写所有必要的路径信息", 'ERROR')
            messagebox.showerror("错误", "请填写所有必要的路径信息")
            return
        
        # 验证文件是否存在
        if not os.path.exists(old_path) or not os.path.exists(new_path):
            self.log_message("输入文件不存在", 'ERROR')
            messagebox.showerror("错误", "输入文件不存在")
            return
        
        # 确保输出目录存在
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except Exception as e:
                self.log_message(f"创建输出目录失败: {e}", 'ERROR')
                messagebox.showerror("错误", f"创建输出目录失败: {e}")
                return
        
        # 路径验证通过后，再保存配置
        try:
            if self.parameter_manager.current_config_name:
                save_success = self.parameter_manager.save_config_as(self.parameter_manager.current_config_name, current_params)
                if not save_success:
                    # 配置保存失败时直接停止运行
                    error_msg = "当前配置保存失败，无法继续执行比对。"
                    self.log_message(error_msg, 'ERROR')
                    messagebox.showerror("配置保存失败", error_msg)
                    return
                else:
                    self.log_message(f"配置 '{self.parameter_manager.current_config_name}' 已保存", 'INFO')
        except Exception as e:
            # 配置保存异常时直接停止运行
            error_msg = f"自动保存当前配置失败: {e}"
            self.log_message(error_msg, 'ERROR')
            messagebox.showerror("配置保存失败", error_msg)
            return
        
        self.is_processing = True
        self.stop_flag.clear()
        # Update button state via the new component method
        self.top_bar.set_button_state('run', 'disabled')
        self.top_bar.set_button_state('stop', 'normal')
        # 禁用帮助与高级设置按钮
        try:
            self.top_bar.set_button_state('help', 'disabled')
            self.top_bar.set_button_state('advanced', 'disabled')
        except Exception:
            pass
        # 禁用配置相关控件，防止处理中切换/修改配置
        self._set_config_controls_state('disabled')
        # 禁用"快速编辑"按钮
        try:
            if hasattr(self, 'btn_quick_edit') and self.btn_quick_edit.winfo_exists():
                self.btn_quick_edit.config(state='disabled')
        except Exception:
            pass
        
        # 将验证过的路径信息传递给处理线程
        threading.Thread(target=self._processing_thread, args=(old_path, new_path, output_dir), daemon=True).start()

    def stop_processing(self):
        """Stop processing"""
        if self.is_processing:
            self.stop_flag.set()
            self.log_message("正在停止处理...", 'INFO')
            self.update_progress("正在停止...", None)

    def _processing_thread(self, old_path, new_path, output_dir):
        # 首先，从GUI收集当前所有参数，确保处理任务使用的是界面上显示的值
        current_params = self._collect_current_gui_parameters()
        # 使用验证过的路径信息，而不是从GUI重新获取
        current_params['old_file_path'] = old_path
        current_params['new_file_path'] = new_path
        current_params['output_directory'] = output_dir
        self.parameter_manager.parameters = current_params # 更新内存中的参数以保证日志等部分参数一致

        # Initialize log file：设置了输出目录则日志写入输出目录；否则写入应用临时目录
        try:
            try:
                app_temp_dir = get_app_temp_dir()
            except Exception:
                app_temp_dir = '.'
            preferred_log_dir = output_dir or app_temp_dir
        except Exception:
            preferred_log_dir = output_dir or '.'
        log_file_initialized = self._initialize_log_file(preferred_log_dir)
        if log_file_initialized:
            self.log_message(f"📁 日志文件已创建: {os.path.basename(self.log_file_path)}", 'INFO')
        else:
            self.log_message("⚠️ 日志文件创建失败，将仅在界面显示日志", 'INFO')

        try:
            # Check if stopped
            if self.stop_flag.is_set():
                self.log_message("处理已被用户停止", 'INFO')
                return
            
            # Validate files
            old_valid, old_error = validate_excel_file(old_path, self.log_message)
            new_valid, new_error = validate_excel_file(new_path, self.log_message)
            
            if not old_valid:
                self.log_message(f"⚠️ 旧版本文件验证失败: {old_error}")
            if not new_valid:
                self.log_message(f"⚠️ 新版本文件验证失败: {new_error}")
            
            final_old_path = old_path
            final_new_path = new_path
 
            # Prepare parameters for ConfigManager update
            # 直接使用从GUI收集的最新参数
            all_params = current_params

            # Update ConfigManager with all current parameters and colors
            self.config_manager.update_from_parameters(all_params, all_params.get('colors', {}))
            
            # 生成输出文件名：配置名称-比对报告-生成时间
            current_time = datetime.datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
            config_name = getattr(self.parameter_manager, 'current_config_name', '') or ''
            safe_name = _sanitize_filename(config_name)
            output_filename = f"{safe_name}-比对报告-{current_time}.xlsx"
            output_path = os.path.join(output_dir, output_filename).replace('\\', '/')

            # 开始处理
            self.reset_progress()
            self.update_progress("正在启动处理，初始化...", 0)
            self.log_message(f"旧版本数据集: {final_old_path}")
            self.log_message(f"新版本数据集: {final_new_path}")
            self.log_message(f"输出目录: {output_path}")


            # 由于process_edc_multithreaded函数需要导入ConfigManager和相关工具函数，
            # 我们需要在其定义所在的模块中进行导入。这里我们直接调用它，假设它已经被正确导入。
            # 这里传递的self.log_message和self.update_progress方法会自动使用GUIUpdateManager
            result_output_path = process_edc_multithreaded(
                old_path=final_old_path,
                new_path=final_new_path,
                output_path=output_path,
                config=self.config_manager,
                log_func=self.log_message,
                progress_func=self.update_progress,
                stop_flag=self.stop_flag
            )

            self.log_message(f"比对结果已保存至: {result_output_path}", 'SUCCESS')
            
            # Prompt log file location
            if self.log_file_path and os.path.exists(self.log_file_path):
                self.log_message(f"详细日志已保存至: {self.log_file_path}", 'SUCCESS')
            
            # Update message box content, including log file information
            success_message = f"比对结果已保存至:\n{result_output_path}"
            if self.log_file_path and os.path.exists(self.log_file_path):
                success_message += f"\n\n详细日志已保存至:\n{self.log_file_path}"
            
            # 先解锁UI，再弹出提示
            self._force_unlock_ui()
            self.root.after(0, lambda msg=success_message: self._show_message_then_unlock('info', "成功", msg))
        except InterruptedError:
            # User stopped operation
            self.update_progress("操作已停止", 0)
            self.log_message("操作已被用户停止", 'INFO')
            self._force_unlock_ui()
            self.root.after(0, lambda: self._show_message_then_unlock('info', "信息", "操作已停止"))
        except Exception as e:
            error_msg = str(e)  # Save error message to local variable first
            self.update_progress(f"❌ 致命错误: {error_msg}")
            self.log_message(f"处理过程中出现错误：{error_msg}", 'ERROR')
            self._force_unlock_ui()
            self.root.after(0, lambda msg=error_msg: self._show_message_then_unlock('error', "错误", f"处理过程中出现错误：\n{msg}"))
        finally:
            # Finalize log file recording
            self._finalize_log_file()
            # 确保在主线程恢复UI
            self._force_unlock_ui()

    def _reset_ui(self):
        self.is_processing = False
        # Restore mouse cursor for all controls
        self.set_cursor_all("")
        # Restore button state using the component method
        self.top_bar.set_button_state('run', 'normal')
        self.top_bar.set_button_state('stop', 'disabled')
        # 恢复帮助与高级设置按钮
        try:
            self.top_bar.set_button_state('help', 'normal')
            self.top_bar.set_button_state('advanced', 'normal')
        except Exception:
            pass
        # 恢复配置相关控件
        self._set_config_controls_state('normal')
        # 恢复"快速编辑"按钮
        try:
            if hasattr(self, 'btn_quick_edit') and self.btn_quick_edit.winfo_exists():
                self.btn_quick_edit.config(state='normal')
        except Exception:
            pass

        # 清理 nofilter 缓存文件（冗余保障）
        try:
            removed = cleanup_nofilter_files()
            # 静默清理临时 nofilter 文件，不在日志体现
        except Exception as e:
            self.log_message(f"⚠️ 清理临时 nofilter 文件时出错: {e}", 'INFO')

    def cleanup(self):
        """Clean up resources, stop GUI update manager"""
        if hasattr(self, 'gui_update_manager'):
            self.gui_update_manager.stop()
        self.root.destroy() # 添加此行：显式销毁Tkinter根窗口

    def choose_missing_color(self):
        color = tkinter.colorchooser.askcolor(title="选择缺失填充颜色", initialcolor=self.missing_color_var.get())
        if color and color[1]:
            new_color = color[1]
            # 直接更新UI
            self.missing_color_var.set(new_color)
            self._update_color_buttons_appearance()
            # 同步到参数管理器
            self.parameter_manager.parameters['colors']['missing_sheet_tab'] = new_color

    def choose_new_color(self):
        
        color = tkinter.colorchooser.askcolor(title="选择新增填充颜色", initialcolor=self.new_color_var.get())
        if color and color[1]:
            new_color = color[1]
            # 直接更新UI
            self.new_color_var.set(new_color)
            self._update_color_buttons_appearance()
            # 同步到参数管理器
            self.parameter_manager.parameters['colors']['new_sheet_tab'] = new_color

    def choose_highlight_color(self):
        color = tkinter.colorchooser.askcolor(title="选择高亮填充颜色", initialcolor=self.highlight_color_var.get())
        if color and color[1]:
            new_color = color[1]
            # 直接更新UI
            self.highlight_color_var.set(new_color)
            self._update_color_buttons_appearance()
            # 同步到参数管理器
            self.parameter_manager.parameters['colors']['highlight_fill'] = new_color

    def show_help(self):
        """Display help information"""
        # 此函数内容已被移动到 数据集对比/src/gui/dialogs/help_dialog.py
        # 这里直接调用外部函数
        show_help(self.root)

    def _edit_exclude_cols(self):
        """Opens a dialog to edit the excluded columns."""
        current_data = self.parameter_manager.get_parameters().get('common_cols', [])
        dialog = _ListEditorDialog(self.root, 
                                   title="编辑排除列", 
                                   prompt="每行输入一个要排除的列名:", 
                                   initial_data_list=current_data)
        if dialog.result is not None:
            self.parameter_manager.update_parameter('common_cols', dialog.result)
            self.load_all_settings_from_parameter_manager()

    def _edit_exclude_sheets(self):
        """Opens a dialog to edit the excluded sheets."""
        current_data = self.parameter_manager.get_parameters().get('exclude_sheets', [])
        dialog = _ListEditorDialog(self.root, 
                                   title="编辑排除sheet", 
                                   prompt="每行输入一个要排除的sheet名:", 
                                   initial_data_list=current_data)
        if dialog.result is not None:
            self.parameter_manager.update_parameter('exclude_sheets', dialog.result)
            self.load_all_settings_from_parameter_manager()

    def _edit_default_anchors(self):
        """Opens a dialog to edit the default anchors."""
        current_data = self.parameter_manager.get_parameters().get('default_keys', [])
        dialog = _ListEditorDialog(self.root, 
                                   title="编辑默认锚点", 
                                   prompt="每行输入一个默认锚点列名:", 
                                   initial_data_list=current_data)
        if dialog.result is not None:
            self.parameter_manager.update_parameter('default_keys', dialog.result)
            self.load_all_settings_from_parameter_manager()

    def _edit_sheet_anchors(self):
        """Opens a dialog to edit the sheet-specific anchors."""
        current_data = self.parameter_manager.get_parameters().get('sheet_key_map', {})
        dialog = _DictEditorDialog(self.root,
                                     title="编辑sheet锚点",
                                     prompt="每行输入一个sheet的锚点，格式为 'sheet: 锚点1, 锚点2, ...'",
                                     initial_data_dict=current_data)
        if dialog.result is not None:
            self.parameter_manager.update_parameter('sheet_key_map', dialog.result)
            self.load_all_settings_from_parameter_manager()

    def _set_config_controls_state(self, state):
        """启用/禁用与配置切换与编辑相关的控件。"""
        # 左侧配置列表
        try:
            if hasattr(self, 'config_listbox') and self.config_listbox.winfo_exists():
                self.config_listbox.config(state=state)
        except Exception:
            pass
        # 相关按钮
        for name in [
            'btn_new_config', 'btn_delete_config', 'btn_rename_config',
            'btn_import_config', 'btn_export_config', 'btn_save_config',
            'btn_edit_common_cols', 'btn_edit_exclude_sheets',
            'btn_edit_default_keys', 'btn_edit_sheet_keys',
            # 颜色选择按钮（tk.Button）
            'highlight_color_btn', 'missing_color_btn', 'new_color_btn',
            # 路径选择卡片中的浏览按钮
            'btn_browse_old', 'btn_browse_new', 'btn_browse_output',
            # 路径选择卡片中的输入框
            'entry_old_file', 'entry_new_file', 'entry_output_dir',
            # 锚点/表头行号输入框
            'entry_anchor_row_num', 'entry_header_row_num',
            # 合并删除数据复选框
            'chk_merge_deleted_data'
        ]:
            try:
                btn = getattr(self, name, None)
                if btn is not None and btn.winfo_exists():
                    btn.config(state=state)
            except Exception:
                pass
        # 顶部下拉（如果存在）
        try:
            if hasattr(self, 'config_dropdown') and self.config_dropdown.winfo_exists():
                self.config_dropdown.config(state=state)
        except Exception:
            pass

    def _open_quick_edit_dialog(self):
        """打开一个Excel风格的参数快速编辑弹窗。"""
        if getattr(self, 'is_processing', False):
            self.log_message("正在比对中，无法快速编辑参数。请先停止。", 'INFO')
            messagebox.showinfo("提示", "正在比对中，无法快速编辑参数。请先停止。")
            return
 
        # 使用当前界面参数作为初始值，确保与UI一致
        current_params = self._collect_current_gui_parameters()
 
        dialog = tk.Toplevel(self.root)
        dialog.title("快速编辑参数（F11全屏）")
        set_window_icon(dialog)
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.geometry("960x420")
        dialog.minsize(720, 360)
 
        # 仅显示这四类可快速批量编辑的参数
        preferred_keys = ['common_cols', 'exclude_sheets', 'default_keys', 'sheet_key_map']
        keys = [k for k in preferred_keys if k in current_params]
        # 仅数据列（分隔线由叠加的Separator绘制）
        columns = tuple(keys)
 
        # 全屏切换支持（与主界面一致：使用系统按钮；保留任务栏）。提供F11快捷键切换最大化/恢复。
        is_maximized = {'value': False}
        prev_state = {'geometry': None}
        def toggle_maximize():
            try:
                if not is_maximized['value']:
                    prev_state['geometry'] = dialog.geometry()
                    dialog.state('zoomed')
                    is_maximized['value'] = True
                else:
                    dialog.state('normal')
                    if prev_state['geometry']:
                        dialog.geometry(prev_state['geometry'])
                    is_maximized['value'] = False
            except Exception:
                pass
        dialog.bind('<F11>', lambda e: toggle_maximize())
        dialog.bind('<Escape>', lambda e: (toggle_maximize() if is_maximized['value'] else None))
 
        # 优先使用 tksheet（具备Excel风格网格线与内置编辑能力）；若不可用则回退到Treeview
        # 强制使用 tksheet（若未安装则提示并退出）
        try:
            import tksheet  # type: ignore
        except Exception:
            messagebox.showerror("缺少依赖", "未安装 tksheet，请运行:\n\npip install tksheet\n\n安装完成后重启程序。")
            return

        # 使用 tksheet 显示 Excel 风格表格
        sheet_frame = ttk.Frame(dialog)
        # 使用 grid 保证底部按钮在全屏时始终可见
        dialog.grid_rowconfigure(0, weight=1)
        dialog.grid_columnconfigure(0, weight=1)
        # 预留底部按钮可见高度
        try:
            dialog.grid_rowconfigure(1, minsize=100)
        except Exception:
            pass
        sheet_frame.grid(row=0, column=0, sticky='nsew', padx=0, pady=0)

        # 列头（中文）
        headers_zh = [self.KEY_MAP_EN_TO_ZH.get(k, k) for k in keys]
        if not headers_zh:
            # 兜底：四列固定
            headers_zh = ["排除列", "排除Sheet", "默认锚点", "指定Sheet锚点"]
            keys = ['common_cols', 'exclude_sheets', 'default_keys', 'sheet_key_map']

        # 组装数据（至少提供若干空行，保证可见网格）
        common_cols = list(current_params.get('common_cols', []))
        exclude_sheets = list(current_params.get('exclude_sheets', []))
        default_keys = list(current_params.get('default_keys', []))
        sheet_key_map_dict = dict(current_params.get('sheet_key_map', {}))
        sheet_items = sorted(sheet_key_map_dict.items())

        max_len = max(len(common_cols), len(exclude_sheets), len(default_keys), len(sheet_items), 10)
        data_rows: list[list[str]] = []
        for i in range(max_len):
            cc = common_cols[i] if i < len(common_cols) else ''
            es = exclude_sheets[i] if i < len(exclude_sheets) else ''
            dk = default_keys[i] if i < len(default_keys) else ''
            if i < len(sheet_items):
                sh_name, anchors = sheet_items[i]
                sm = f"{sh_name}:{','.join(anchors)}" if isinstance(anchors, (list, tuple)) else f"{sh_name}:{anchors}"
            else:
                sm = ''
            row = [cc, es, dk, sm]
            # 截断/填充到当前列数
            row = (row + [''] * len(headers_zh))[:len(headers_zh)]
            data_rows.append(row)

        # 构造表格
        sheet = tksheet.Sheet(
            sheet_frame,
            data=data_rows,
            headers=headers_zh,
            show_row_index=False,
            show_top_left_corner=False,
        )
        sheet.pack(fill=tk.BOTH, expand=True)

        # 数据获取兼容（不同 tksheet 版本参数不同）
        def _get_data():
            try:
                return sheet.get_sheet_data(return_copy=True)
            except TypeError:
                try:
                    return sheet.get_sheet_data()
                except Exception:
                    pass
            except Exception:
                pass
            try:
                return sheet.get_sheet_data(get_displayed=True)
            except Exception:
                return []

        # 列宽自动铺满窗口
        def stretch_columns_to_fill(event=None):
            try:
                total_cols = max(1, len(headers_zh))
                avail = max(100, sheet_frame.winfo_width() - 6)  # 预留滚动条像素
                target = max(60, avail // total_cols)
                # 兼容不同版本 API
                try:
                    sheet.set_column_widths([target] * total_cols)
                except Exception:
                    try:
                        for ci in range(total_cols):
                            try:
                                sheet.column_width(ci, target)
                            except Exception:
                                sheet.set_column_width(ci, target)
                    except Exception:
                        pass
                try:
                    sheet.redraw()
                except Exception:
                    pass
            except Exception:
                pass
        # 初始与尺寸变化时都铺满
        dialog.bind('<Configure>', lambda e: stretch_columns_to_fill())
        sheet_frame.bind('<Configure>', lambda e: stretch_columns_to_fill())
        dialog.after(100, stretch_columns_to_fill)

        # 视觉选项与重绘
        try:
            sheet.set_options(
                table_grid_fg="#C4C9D3",
                show_vertical_grid=True,
                show_horizontal_grid=True,
                empty_vertical=True,
                empty_horizontal=True,
            )
            # 固定字体，避免编辑时字体被放大导致显示不全（避免使用粗体以兼容部分版本）
            try:
                sheet.set_options(font=("微软雅黑", 10))
            except Exception:
                try:
                    sheet.set_options(font=("Arial", 10))
                except Exception:
                    pass
            try:
                sheet.redraw()
            except Exception:
                pass
        except Exception:
            pass

        # 禁用 Ctrl + 滚轮 / +/- 放大缩小，防止字体尺寸被改变
        for widget in (sheet, dialog):
            try:
                widget.bind('<Control-MouseWheel>', lambda e: 'break')
                widget.bind('<Control-Button-4>', lambda e: 'break')
                widget.bind('<Control-Button-5>', lambda e: 'break')
                widget.bind('<Control-plus>', lambda e: 'break')
                widget.bind('<Control-KP_Add>', lambda e: 'break')
                widget.bind('<Control-minus>', lambda e: 'break')
                widget.bind('<Control-KP_Subtract>', lambda e: 'break')
                widget.bind('<Control-equal>', lambda e: 'break')
            except Exception:
                pass

        # 常用交互
        sheet.enable_bindings(
            "single_select",
            "row_select",
            "column_select",
            "edit_cell",
            "copy",
            "paste",
            "arrowkeys",
            "drag_select",
        )

        # 底部按钮
        btn_frame = ttk.Frame(dialog)
        btn_frame.grid(row=1, column=0, sticky='ew', padx=10, pady=(0, 12))

        # 新增行（末尾追加十行空白）
        def add_empty_row(event=None):
            try:
                # 7.x API
                sheet.insert_rows(rows=10, idx=len(_get_data()))
            except Exception:
                try:
                    # 6.x 及其它 API
                    sheet.insert_rows(10, len(_get_data()))
                except Exception:
                    # 兜底：重设数据
                    cur = _get_data()
                    for _ in range(10):
                        cur.append([''] * len(headers_zh))
                    try:
                        sheet.set_sheet_data(cur)
                    except Exception:
                        pass
            try:
                sheet.redraw()
            except Exception:
                pass

        dialog.bind('<Control-Return>', add_empty_row)
        ttk.Button(btn_frame, text="新增十行", command=add_empty_row, style="secondary").pack(side=tk.LEFT)

        def on_save_tksheet():
            updated = current_params.copy()
            values = _get_data()
            new_common_cols, new_exclude_sheets, new_default_keys = [], [], []
            new_sheet_key_map = {}
            for row in values:
                if not row:
                    continue
                # 根据列头提取列索引
                def _get(idx_name: str, default_index: int) -> str:
                    try:
                        i = headers_zh.index(self.KEY_MAP_EN_TO_ZH.get(idx_name, idx_name))
                    except ValueError:
                        i = default_index
                    return str(row[i]).strip() if i < len(row) and row[i] is not None else ''
                cc = _get('common_cols', 0)
                es = _get('exclude_sheets', 1)
                dk = _get('default_keys', 2)
                sm = _get('sheet_key_map', 3)
                if cc:
                    new_common_cols.append(cc)
                if es:
                    new_exclude_sheets.append(es)
                if dk:
                    new_default_keys.append(dk)
                if sm:
                    part = sm
                    if ':' in part or '：' in part:
                        sep = ':' if ':' in part else '：'
                        sheet_name, anchors = part.split(sep, 1)
                        sheet_name = sheet_name.strip()
                        anchor_list = [a.strip() for a in anchors.replace('，', ',').split(',') if a.strip()]
                        if sheet_name:
                            new_sheet_key_map[sheet_name] = anchor_list
                    else:
                        new_sheet_key_map[part] = []

            updated['common_cols'] = new_common_cols
            updated['exclude_sheets'] = new_exclude_sheets
            updated['default_keys'] = new_default_keys
            updated['sheet_key_map'] = new_sheet_key_map

            self.parameter_manager.parameters = updated
            self.load_all_settings_from_parameter_manager()
            self.log_message("已通过快速编辑更新参数并刷新界面。", 'INFO')
            dialog.destroy()

        def on_cancel_tksheet():
            dialog.destroy()

        ttk.Button(btn_frame, text="取消", command=on_cancel_tksheet, style="secondary-outline").pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="保存", command=on_save_tksheet, style="success").pack(side=tk.RIGHT, padx=(0,8))
        return

    def _create_new_config(self):
        """创建新配置。"""
        if self.is_processing:
            self.log_message("正在比对中，无法新建配置。请先停止。", 'INFO')
            messagebox.showinfo("提示", "正在比对中，无法新建配置。请先停止。")
            return
        dialog = _CustomDialog(self.root, title="新建配置", prompt="请输入新配置的名称:")
        new_config_name = dialog.result

        if new_config_name:
            new_config_name = new_config_name.strip()
            if not new_config_name:
                messagebox.showwarning("名称无效", "配置名称不能为空。")
                return
            if new_config_name in self.parameter_manager.list_configurations():
                messagebox.showwarning("名称重复", "该配置名称已存在，请选择其他名称。")
                return

            # 使用默认参数创建新配置，而不是沿用当前界面参数
            default_params = self.parameter_manager._get_default_parameters()
            # 确保结构完整（包含列表/映射/颜色等键）
            self.parameter_manager.parameters = default_params
            self.parameter_manager._ensure_parameter_structure()
            to_save = self.parameter_manager.parameters
            if self.parameter_manager.save_config_as(new_config_name, to_save):
                self.log_message(f"已创建新配置（默认参数）: {new_config_name}", 'INFO')
                self._populate_config_listbox() # 刷新列表
                self.parameter_manager.current_config_name = new_config_name # 设置当前配置为新配置
                self.load_all_settings_from_parameter_manager() # 加载并更新UI
                self._select_config_in_listbox(new_config_name)
                messagebox.showinfo("保存成功", f"已使用默认参数创建新配置 '{new_config_name}'！")
            else:
                messagebox.showerror("保存失败", "保存新配置时发生错误。")

    def _delete_selected_config(self, config_name_to_delete):
        """Deletes the specified configuration."""
        if messagebox.askyesno("确认删除", f"您确定要删除配置 '{config_name_to_delete}' 吗？\n此操作不可恢复。"):
            try:
                self.parameter_manager.delete_config(config_name_to_delete)
                messagebox.showinfo("成功", f"配置 '{config_name_to_delete}' 已被删除。")
 
                # 如果删除的是当前配置，选择一个可用配置作为新当前配置
                if self.parameter_manager.current_config_name == config_name_to_delete:
                    remaining = self.parameter_manager.list_configurations()
                    if remaining:
                        self.parameter_manager.load_config(remaining[0])

                    # 同步UI
                    self.load_all_settings_from_parameter_manager()
                    self._update_current_config_display()

                # 无论删除的是哪个，最终统一刷新列表UI
                self._refresh_config_list_ui()
            except Exception as e:
                messagebox.showerror("删除失败", f"删除配置时出错: {e}")
 
    def _on_config_select(self, event):
        """当配置列表项被选中时的回调。"""
        if self.is_processing:
            # 恢复到当前配置并提示
            self._select_config_in_listbox(self.parameter_manager.current_config_name)
            self.log_message("正在比对中，无法切换配置。请先停止。", 'INFO')
            try:
                messagebox.showinfo("提示", "正在比对中，无法切换配置。请先停止。")
            except Exception:
                pass
            return
 
        selection_indices = self.config_listbox.curselection()
        if not selection_indices:
            return
        selected_config = self.config_listbox.get(selection_indices[0])
 
        # 防御：若文件已不存在（可能刚被删除），刷新列表并保持当前配置
        available = set(self.parameter_manager.list_configurations())
        if selected_config not in available:
            self._populate_config_listbox()
            self._select_config_in_listbox(self.parameter_manager.current_config_name)
            try:
                messagebox.showinfo("提示", f"配置 '{selected_config}' 已不存在，已为您刷新列表。")
            except Exception:
                pass
            return
 
        if self.parameter_manager.current_config_name != selected_config:
            if self.parameter_manager.load_config(selected_config):
                self.load_all_settings_from_parameter_manager()  # 更新UI
                self._update_current_config_display()            # 更新标题
                self.log_message(f"已加载配置: {selected_config}", 'INFO')
            else:
                messagebox.showerror("加载失败", f"无法加载配置 '{selected_config}'。")
        
        # 每次选中后，更新操作按钮状态（对模板禁用编辑/删除/保存）
        self._update_config_action_buttons_state()

    def _populate_config_listbox(self):
        """填充左侧配置列表。"""
        try:
            self.config_listbox.delete(0, tk.END)
            configs = self.parameter_manager.list_configurations()
            # 固定内置模板置顶显示
            ordered = []
            for name in (BUILTIN_TEMPLATE_CIMS, BUILTIN_TEMPLATE_TM):
                if name in configs:
                    ordered.append(name)
            # 其余配置（排除模板名），按名称排序
            others = sorted([c for c in configs if c not in (BUILTIN_TEMPLATE_CIMS, BUILTIN_TEMPLATE_TM)])
            ordered.extend(others)
            for cfg in ordered:
                self.config_listbox.insert(tk.END, cfg)
            # 保持当前配置选中
            if self.parameter_manager.current_config_name:
                self._select_config_in_listbox(self.parameter_manager.current_config_name)
            # 刷新按钮状态
            self._update_config_action_buttons_state()
        except Exception as e:
            self.log_message(f"填充配置列表时出错: {e}", 'ERROR')

    def _select_config_in_listbox(self, config_name):
        """在列表中选中指定配置。"""
        try:
            items = self.config_listbox.get(0, tk.END)
            if config_name in items:
                index = items.index(config_name)
                self.config_listbox.selection_clear(0, tk.END)
                self.config_listbox.selection_set(index)
                self.config_listbox.activate(index)
                self.config_listbox.see(index)
        except Exception as e:
            self.log_message(f"在列表中选中配置 '{config_name}' 时出错: {e}", 'ERROR')

    def _update_current_config_display(self):
        """更新界面上显示的当前配置名称。"""
        try:
            full_name = f"{self.parameter_manager.current_config_name}"
            # 简单设置（避免复杂测量造成依赖）
            self.config_name_label_var.set(full_name or "")
        except Exception as e:
            self.log_message(f"更新配置名称显示时出错: {e}", 'ERROR')

    def load_all_settings_from_parameter_manager(self):
        """从参数管理器加载所有参数并更新UI。"""
        try:
            params = self.parameter_manager.get_parameters()
            # 基本路径
            self.old_path_var.set(params.get('old_file_path', ''))
            self.new_path_var.set(params.get('new_file_path', ''))
            self.output_dir_var.set(params.get('output_directory', ''))
            # 行号
            self.anchor_row_num_var.set(params.get('anchor_row_num', 1))
            self.header_row_num_var.set(params.get('header_row_num', 1))
            # 其他
            self.merge_deleted_data_var.set(params.get('merge_deleted_data', True))
            self.max_workers_var.set(params.get('max_workers', os.cpu_count()))
            # 颜色
            self.load_color_settings(params)
            # 右侧卡片（若存在）
            if hasattr(self, 'common_cols_card_frame'):
                self.common_cols_card_frame.clear_cards()
                for item in params.get('common_cols', []):
                    self.common_cols_card_frame.add_parameter_card(item, 'common_cols')
            if hasattr(self, 'exclude_sheets_card_frame'):
                self.exclude_sheets_card_frame.clear_cards()
                for item in params.get('exclude_sheets', []):
                    self.exclude_sheets_card_frame.add_parameter_card(item, 'exclude_sheets')
            if hasattr(self, 'default_keys_card_frame'):
                self.default_keys_card_frame.clear_cards()
                for item in params.get('default_keys', []):
                    self.default_keys_card_frame.add_parameter_card(item, 'default_keys')
            if hasattr(self, 'sheet_key_map_card_frame'):
                self.sheet_key_map_card_frame.clear_cards()
                sheet_map_dict = params.get('sheet_key_map', {})
                for sheet, key_list in sheet_map_dict.items():
                    display_text = f"{sheet}: {', '.join(key_list)}"
                    self.sheet_key_map_card_frame.add_parameter_card(display_text, 'sheet_key_map')
            self.root.after_idle(self._update_color_buttons_appearance)
            self.log_message(f"所有配置已从文件加载并更新到界面。当前配置: {self.parameter_manager.current_config_name}", 'INFO')
        except Exception as e:
            self.log_message(f"加载参数到UI时出错: {e}", 'ERROR')

    def save_current_configuration(self):
        """保存当前界面的所有配置到参数管理器。"""
        if self.is_processing:
            self.log_message("正在比对中，无法保存配置。请先停止。", 'INFO')
            try:
                messagebox.showinfo("提示", "正在比对中，无法保存配置。请先停止。")
            except Exception:
                pass
            return
        try:
            selection = self.config_listbox.curselection()
            if not selection:
                messagebox.showwarning("未选择配置", "请先在左侧列表中选择一个要保存的配置。")
                return

            config_to_save = self.config_listbox.get(selection[0])
            # 如果是内置模板，禁止保存覆盖
            if config_to_save in (BUILTIN_TEMPLATE_CIMS, BUILTIN_TEMPLATE_TM):
                messagebox.showinfo("只读模板", f"'{config_to_save}' 为内置模板，不允许直接修改。请使用'新建'创建您自己的配置。")
                return

            # 收集当前界面参数并更新到ParameterManager
            current_params = self._collect_current_gui_parameters()
            
            if self.parameter_manager.save_config_as(config_to_save, current_params):
                # 保存后重新加载，以确保内部状态一致
                self.parameter_manager.load_config(config_to_save)
                self.load_all_settings_from_parameter_manager()

                messagebox.showinfo("保存成功", f"配置 '{config_to_save}' 已成功保存！")
                self.log_message(f"配置 '{config_to_save}' 已成功保存！", 'INFO')
            else:
                messagebox.showerror("保存失败", f"保存配置 '{config_to_save}' 时发生错误。")

        except Exception as e:
            messagebox.showerror("保存失败", f"保存配置时发生错误：{e}")
            self.log_message(f"保存配置时发生错误：{e}", 'ERROR')

    def browse_directory(self):
        """选择输出目录并更新到界面变量。"""
        if self.is_processing:
            self.log_message("正在比对中，无法更换输出目录。请先停止。", 'INFO')
            try:
                messagebox.showinfo("提示", "正在比对中，无法更换输出目录。请先停止。")
            except Exception:
                pass
            return
        dirname = Fieldialog.askdirectory(title="选择输出目录")
        if dirname:
            self.output_dir_var.set(dirname)

    def browse_file(self, path_var):
        """选择一个Excel文件路径并写入指定的StringVar。"""
        if getattr(self, 'is_processing', False):
            self.log_message("正在比对中，无法更换文件路径。请先停止。", 'INFO')
            try:
                messagebox.showinfo("提示", "正在比对中，无法更换文件路径。请先停止。")
            except Exception:
                pass
            return
        try:
            file_path = Fieldialog.askopenfilename(
                title="选择Excel文件",
                filetypes=[("Excel files", "*.xlsx;*.xlsm;*.xls"), ("所有文件", "*.*")]
            )
            if not file_path:
                return
            # 简单校验：存在性 + 扩展名
            if not os.path.exists(file_path):
                messagebox.showerror("文件不存在", f"找不到文件：{file_path}")
                return
            # 若有更严格校验函数，可调用 validate_excel_file
            try:
                if not validate_excel_file(file_path, self.log_message):
                    return
            except Exception:
                # 如果校验函数不可用或异常，忽略并继续
                pass
            path_var.set(file_path)
        except Exception as e:
            try:
                messagebox.showerror("选择文件失败", f"选择文件时发生错误：{e}")
            except Exception:
                pass
            self.log_message(f"选择文件失败：{e}", 'ERROR')

    def load_color_settings(self, parameters=None):
        """从参数加载颜色到变量，并刷新颜色按钮外观。"""
        try:
            if parameters is None:
                colors = self.parameter_manager.get_parameters().get('colors', {})
            else:
                colors = parameters.get('colors', {})
            self.highlight_color_var.set(colors.get('highlight_fill', '#FFE5E5'))
            self.missing_color_var.set(colors.get('missing_sheet_tab', '#DC143C'))
            self.new_color_var.set(colors.get('new_sheet_tab', '#00FF00'))
            self.root.after_idle(self._update_color_buttons_appearance)
        except Exception as e:
            self.log_message(f"加载颜色设置时出错: {e}", 'ERROR')

    def _delete_selected_config_from_button(self):
        """响应删除按钮的点击事件。"""
        if self.is_processing:
            self.log_message("正在比对中，无法删除配置。请先停止。", 'INFO')
            try:
                messagebox.showinfo("提示", "正在比对中，无法删除配置。请先停止。")
            except Exception:
                pass
            return
        selection = self.config_listbox.curselection()
        if not selection:
            messagebox.showwarning("未选择", "请先在左侧列表中选择一个要删除的配置。")
            return
        config_name_to_delete = self.config_listbox.get(selection[0])
        # 如果是内置模板，禁止删除
        if config_name_to_delete in (BUILTIN_TEMPLATE_CIMS, BUILTIN_TEMPLATE_TM):
            messagebox.showinfo("只读模板", f"'{config_name_to_delete}' 为内置模板，不允许删除。")
            return
        self._delete_selected_config(config_name_to_delete)

    def _rename_selected_config(self):
        """重命名当前选中的配置。"""
        if self.is_processing:
            self.log_message("正在比对中，无法重命名配置。请先停止。", 'INFO')
            try:
                messagebox.showinfo("提示", "正在比对中，无法重命名配置。请先停止。")
            except Exception:
                pass
            return
        selection = self.config_listbox.curselection()
        if not selection:
            messagebox.showwarning("未选择", "请先在左侧列表中选择一个要重命名的配置。")
            return
        old_name = self.config_listbox.get(selection[0])
        # 如果是内置模板，禁止重命名
        if old_name in (BUILTIN_TEMPLATE_CIMS, BUILTIN_TEMPLATE_TM):
            messagebox.showinfo("只读模板", f"'{old_name}' 为内置模板，不允许重命名。")
            return
        dialog = _CustomDialog(self.root, title="重命名配置", prompt="请输入新名称:", initialvalue=old_name)
        new_name = dialog.result
        if not new_name:
            return
        new_name = new_name.strip()
        if not new_name:
            messagebox.showwarning("名称无效", "配置名称不能为空。")
            return
        if new_name == old_name:
            return
        if new_name in self.parameter_manager.list_configurations():
            messagebox.showwarning("名称重复", "该配置名称已存在，请选择其他名称。")
            return
        try:
            # 读取旧配置内容
            if not self.parameter_manager.load_config(old_name):
                messagebox.showerror("重命名失败", f"无法读取配置 '{old_name}'。")
                return
            params = self.parameter_manager.get_parameters()
            # 先保存为新名称
            if not self.parameter_manager.save_config_as(new_name, params):
                messagebox.showerror("重命名失败", "写入新配置失败。")
                return
            # 删除旧配置文件
            self.parameter_manager.delete_config(old_name)
            # 刷新列表并选中新配置
            self.parameter_manager.load_config(new_name)
            self.load_all_settings_from_parameter_manager()
            self._update_current_config_display()
            self._refresh_config_list_ui()
            self.log_message(f"配置已重命名为: {new_name}", 'INFO')
        except Exception as e:
            messagebox.showerror("重命名失败", f"重命名配置时出错：{e}")

    def _refresh_config_list_ui(self):
        """刷新左侧配置列表并选中当前配置，确保UI立即更新。"""
        try:
            self._populate_config_listbox()
            # 根据当前选择刷新按钮状态
            self._update_config_action_buttons_state()
        except Exception as e:
            self.log_message(f"刷新配置列表UI时出错: {e}", 'ERROR')

    def _force_unlock_ui(self):
        """强力解锁UI：立即与延时多次恢复，避免任何时序竞态导致的锁定残留。"""
        def do_reset():
            try:
                self._reset_ui()
            except Exception:
                pass
        try:
            self.root.after(0, do_reset)
            self.root.after(100, do_reset)
            self.root.after(300, do_reset)
        except Exception:
            do_reset()

    def _show_message_then_unlock(self, kind: str, title: str, message: str):
        """在主线程弹窗，关闭后再解锁一次UI。kind: 'info' | 'error'."""
        try:
            if kind == 'error':
                messagebox.showerror(title, message)
            else:
                messagebox.showinfo(title, message)
        finally:
            # 弹窗关闭后再解锁一次
            self._force_unlock_ui()

    def set_cursor_all(self, cursor):
        """递归设置窗口内所有控件的鼠标指针样式。"""
        def set_cursor_recursive(widget):
            try:
                widget.config(cursor=cursor)
            except Exception:
                pass
            try:
                children = widget.winfo_children()
            except Exception:
                children = []
            for child in children:
                set_cursor_recursive(child)
        try:
            set_cursor_recursive(self.root)
        except Exception:
            pass
        self._current_cursor = cursor

    # 新增：根据当前选择的配置，启用/禁用操作按钮（模板只读）
    def _update_config_action_buttons_state(self):
        try:
            current_name = None
            sel = self.config_listbox.curselection()
            if sel:
                current_name = self.config_listbox.get(sel[0])
            else:
                current_name = self.parameter_manager.current_config_name
            is_builtin = current_name in (BUILTIN_TEMPLATE_CIMS, BUILTIN_TEMPLATE_TM)
            # 针对不同按钮分别设置：模板时允许"复制"，禁用其他编辑类操作
            btn_save = getattr(self, 'btn_save_config', None)
            btn_delete = getattr(self, 'btn_delete_config', None)
            btn_rename = getattr(self, 'btn_rename_config', None)
            btn_quick = getattr(self, 'btn_quick_edit', None)
            btn_copy = getattr(self, 'btn_copy_config', None)
            try:
                if btn_save is not None:
                    btn_save.configure(state=(tk.DISABLED if is_builtin else tk.NORMAL))
            except Exception:
                pass
            try:
                if btn_delete is not None:
                    btn_delete.configure(state=(tk.DISABLED if is_builtin else tk.NORMAL))
            except Exception:
                pass
            try:
                if btn_rename is not None:
                    btn_rename.configure(state=(tk.DISABLED if is_builtin else tk.NORMAL))
            except Exception:
                pass
            try:
                if btn_quick is not None:
                    btn_quick.configure(state=(tk.DISABLED if is_builtin else tk.NORMAL))
            except Exception:
                pass
            try:
                if btn_copy is not None:
                    # 复制始终允许（除非其他流程如正在处理时统一禁用）
                    btn_copy.configure(state=tk.NORMAL)
            except Exception:
                pass
        except Exception as e:
            self.log_message(f"更新按钮状态时出错: {e}", 'ERROR')

    def _is_template_modified(self):
        """检查当前模板配置是否被修改。"""
        try:
            # 获取当前GUI参数
            current_params = self._collect_current_gui_parameters()
            
            # 获取原始模板配置
            original_params = self.parameter_manager._get_original_template_params()
            if original_params is None:
                return False
            
            # 比较关键参数是否发生变化（排除文件路径等用户输入参数）
            key_params = ['exclude_sheets', 'common_cols', 'default_keys', 'sheet_key_map', 'colors', 'anchor_row_num', 'header_row_num', 'merge_deleted_data']
            for key in key_params:
                if key in current_params and key in original_params:
                    if current_params[key] != original_params[key]:
                        return True
            
            return False
        except Exception as e:
            self.log_message(f"检查模板修改状态时出错: {e}", 'ERROR')
            return False
    
    def _copy_template_before_processing(self):
        """在比对前复制模板配置。"""
        try:
            current_name = self.parameter_manager.current_config_name
            # 生成新配置名称
            base_name = current_name.replace("【模板】", "").strip()
            new_name = f"{base_name}-自定义配置"
            
            # 确保名称唯一
            counter = 1
            original_new_name = new_name
            while new_name in self.parameter_manager.list_configurations():
                new_name = f"{original_new_name}-{counter}"
                counter += 1
            
            # 获取当前参数并保存为新配置
            current_params = self._collect_current_gui_parameters()
            if self.parameter_manager.save_config_as(new_name, current_params):
                # 切换到新配置
                self.parameter_manager.load_config(new_name)
                self.load_all_settings_from_parameter_manager()
                self._update_current_config_display()
                self._refresh_config_list_ui()
                self._select_config_in_listbox(new_name)
                
                self.log_message(f"已复制模板配置为 '{new_name}'", 'INFO')
                messagebox.showinfo("复制成功", f"已复制模板配置为 '{new_name}'，现在可以安全修改。")
                return True
            else:
                messagebox.showerror("复制失败", "复制模板配置失败，请手动复制。")
                return False
        except Exception as e:
            self.log_message(f"复制模板配置时出错: {e}", 'ERROR')
            messagebox.showerror("复制失败", f"复制模板配置时出错: {e}")
            return False

    def _copy_selected_config(self):
        """复制当前选中配置为新的配置。"""
        if self.is_processing:
            self.log_message("正在比对中，无法复制配置。请先停止。", 'INFO')
            try:
                messagebox.showinfo("提示", "正在比对中，无法复制配置。请先停止。")
            except Exception:
                pass
            return
        selection = self.config_listbox.curselection()
        if not selection:
            messagebox.showwarning("未选择", "请先在左侧列表中选择一个要复制的配置。")
            return
        old_name = self.config_listbox.get(selection[0])
        # 内置模板可以作为来源复制，但不能覆盖到内置模板名
        dialog = _CustomDialog(self.root, title="复制配置", prompt="请输入新配置名称:", initialvalue=f"{old_name}-副本")
        new_name = dialog.result
        if not new_name:
            return
        new_name = new_name.strip()
        if not new_name:
            messagebox.showwarning("名称无效", "配置名称不能为空。")
            return
        if new_name in self.parameter_manager.list_configurations():
            messagebox.showwarning("名称重复", "该配置名称已存在，请选择其他名称。")
            return
        if new_name in (BUILTIN_TEMPLATE_CIMS, BUILTIN_TEMPLATE_TM):
            messagebox.showwarning("名称不允许", "新配置名称不能与内置模板名称相同。")
            return
        try:
            # 读取来源配置内容
            if not self.parameter_manager.load_config(old_name):
                messagebox.showerror("复制失败", f"无法读取配置 '{old_name}'。")
                return
            params = self.parameter_manager.get_parameters()
            # 保存为新名称
            if not self.parameter_manager.save_config_as(new_name, params):
                messagebox.showerror("复制失败", "保存新配置失败。")
                return
            # 选中新配置并刷新界面
            self.parameter_manager.load_config(new_name)
            self.load_all_settings_from_parameter_manager()
            self._update_current_config_display()
            self._refresh_config_list_ui()
            self._select_config_in_listbox(new_name)
            self.log_message(f"已复制配置 '{old_name}' 为 '{new_name}'。", 'INFO')
            try:
                messagebox.showinfo("复制成功", f"已复制配置 '{old_name}' 为 '{new_name}'。")
            except Exception:
                pass
        except Exception as e:
            messagebox.showerror("复制失败", f"复制配置时出错：{e}")

if __name__ == '__main__':
    root = ttk.Window(themename="flatly")
    root.title('Excel比对工具-V2.0')
    try:
        root.configure(bg='white')
    except Exception:
        pass
    
    # 设置窗口图标
    set_window_icon(root)

    app = DatasetComparatorGUI(root)
    # 移除这里的load_all_settings_from_parameter_manager()和_update_current_config_display()
    # 因为它们已经在__init__的末尾调用
    root.protocol("WM_DELETE_WINDOW", app.cleanup) # 确保在关闭窗口时调用清理函数
    root.mainloop()