import tkinter as tk
from tkinter import ttk, messagebox, filedialog as Fieldialog
import json
import os
import tkinter.font as tkFont
from ..utils.file_utils import set_window_icon # 修正导入路径
from ..utils.logger import log
from ..utils.file_utils import get_app_temp_dir # Import the new function

CONFIGS_SUBDIR = "configs"
# 保留常量位置，但不再使用默认配置概念
# 新增：内置模板名称
BUILTIN_TEMPLATE_CIMS = "【模板】CIMS数据集"
BUILTIN_TEMPLATE_TM = "【模板】TM数据集"

class ParameterManager:
    """参数管理类，负责加载、保存和管理应用程序的各种配置参数。
    提供参数的持久化功能（通过parameters.json文件）。
    """
    def __init__(self, main_app_instance):
        self.main_app = main_app_instance # 主应用程序实例
        self.window = None # 参数管理窗口的Toplevel实例
        # 当前加载的配置名称：默认指向CIMS模板
        self.current_config_name = BUILTIN_TEMPLATE_CIMS

        self._ensure_config_directory() # 确保配置目录存在
        # 新增：确保内置模板存在
        self._ensure_builtin_templates()
        self.parameters = self._load_initial_config() # 加载初始参数（默认或上次使用的）
        self._ensure_parameter_structure() # 确保参数结构完整性

    def get_configs_dir(self):
        """获取配置文件的存放目录。"""
        app_temp_dir = get_app_temp_dir()
        return os.path.join(app_temp_dir, CONFIGS_SUBDIR)

    def get_config_path(self, config_name):
        """获取指定配置名称的完整文件路径。"""
        return os.path.join(self.get_configs_dir(), f"{config_name}.json")

    def _ensure_config_directory(self):
        """确保配置目录存在。"""
        os.makedirs(self.get_configs_dir(), exist_ok=True)
        log(f"配置目录已确保存在: {self.get_configs_dir()}", None)

    def _load_initial_config(self):
        """加载初始配置：优先加载CIMS模板配置。"""
        cims_path = self.get_config_path(BUILTIN_TEMPLATE_CIMS)
        if os.path.exists(cims_path):
            try:
                with open(cims_path, 'r', encoding='utf-8') as f:
                    loaded_params = json.load(f)
                    self.current_config_name = BUILTIN_TEMPLATE_CIMS
                    log(f"成功从 {cims_path} 加载内置模板配置。", None)
                    return loaded_params
            except Exception as e:
                log(f"加载内置模板配置失败: {e}。将使用默认参数结构。", None)
        else:
            log(f"未找到内置模板文件: {cims_path}，将使用默认参数结构。", None)
        return self._get_default_parameters()

    def list_configurations(self):
        """列出所有可用的配置名称。"""
        configs = []
        config_dir = self.get_configs_dir()
        if os.path.exists(config_dir):
            for filename in os.listdir(config_dir):
                if filename.endswith(".json"):
                    configs.append(os.path.splitext(filename)[0])
        return sorted(configs)

    def load_config(self, config_name):
        """加载指定名称的配置。"""
        config_path = self.get_config_path(config_name)
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    self.parameters = json.load(f)
                    self.current_config_name = config_name
                    self._ensure_parameter_structure() # 确保加载的配置结构完整
                    log(f"成功加载配置: {config_name}", None)
                    return True
            except json.JSONDecodeError as e:
                log(f"加载配置 '{config_name}' 失败 (JSONDecodeError): {e}", None)
            except Exception as e:
                log(f"加载配置 '{config_name}' 失败: {e}", None)
        else:
            log(f"配置 '{config_name}' 文件不存在。", None)
        return False

    def save_config_as(self, config_name, parameters_to_save):
        """将指定参数保存为新配置。"""
        # 内置模板保护：禁止覆盖写入内置模板
        if config_name in (BUILTIN_TEMPLATE_CIMS, BUILTIN_TEMPLATE_TM):
            log(f"'{config_name}' 为内置模板，不允许被修改或覆盖保存。", None)
            return False
        config_path = self.get_config_path(config_name)
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(parameters_to_save, f, ensure_ascii=False, indent=4)
            self.current_config_name = config_name
            log(f"配置已成功保存为 '{config_name}'。", None)
            return True
        except Exception as e:
            log(f"保存配置 '{config_name}' 失败: {e}", None)
            return False

    def delete_config(self, config_name):
        """删除指定名称的配置。"""
        # 内置模板保护：禁止删除内置模板
        if config_name in (BUILTIN_TEMPLATE_CIMS, BUILTIN_TEMPLATE_TM):
            log(f"'{config_name}' 为内置模板，不允许删除。", None)
            return False
        config_path = self.get_config_path(config_name)
        if os.path.exists(config_path):
            try:
                os.remove(config_path)
                log(f"配置 '{config_name}' 已成功删除。", None)
                return True
            except Exception as e:
                log(f"删除配置 '{config_name}' 失败: {e}", None)
        else:
            log(f"尝试删除的配置 '{config_name}' 不存在。", None)
        return False

    def _ensure_parameter_structure(self):
        """确保加载的参数结构完整，如果缺少键则使用默认值填充。"""
        default_structure = { # 定义完整的默认参数结构
            'common_cols': [],
            'exclude_sheets': [],
            'default_keys': [],
            'sheet_key_map': {},
            'colors': {
                'highlight_fill': '#FFE5E5',
                'missing_sheet_tab': '#DC143C',
                'new_sheet_tab': '#00FF00'
            },
            'old_file_path': '',
            'new_file_path': '',
            'output_directory': '',
            'anchor_row_num': 1,
            'header_row_num': 1,
            'max_workers': max(1, os.cpu_count() - 1), # 默认最大线程数为CPU核心数减1，至少为1
            'merge_deleted_data': True,
        }

        for key, default_value in default_structure.items():
            if key not in self.parameters: # 如果主键缺失，则添加默认值
                self.parameters[key] = default_value

        # 确保colors子键都存在
        for color_key, color_value in default_structure['colors'].items():
            if color_key not in self.parameters['colors']:
                self.parameters['colors'][color_key] = color_value

    # 新增：创建内置模板（若不存在）
    def _ensure_builtin_templates(self):
        try:
            os.makedirs(self.get_configs_dir(), exist_ok=True)
            templates = {
                BUILTIN_TEMPLATE_CIMS: {
                    'old_file_path': '',
                    'new_file_path': '',
                    'output_directory': '',
                    'anchor_row_num': 1,
                    'header_row_num': 2,
                    'merge_deleted_data': True,
                    'common_cols': [
                        "STUDYID", "RANDID", "SUBINI", "SUBSTA", "FORMNO", "FORMSTA",
                        "STA_DEC", "SDVSTA", "DMRSTA", "MR_STA", "TOPIC"
                    ],
                    'exclude_sheets': [
                        "系统变量", "数据范围", "eCRF表单", "CPH_FT--Header & Footer", "eCRF备注日志"
                    ],
                    'default_keys': ["SUBJID", "VISITNUM", "FORMSEQ", "TOPICSEQ"],
                    'sheet_key_map': {},
                    'colors': {
                        'highlight_fill': '#FFE5E5',
                        'missing_sheet_tab': '#DC143C',
                        'new_sheet_tab': '#00FF00'
                    }
                },
                BUILTIN_TEMPLATE_TM: {
                    'old_file_path': '',
                    'new_file_path': '',
                    'output_directory': '',
                    'anchor_row_num': 2,
                    'header_row_num': 1,
                    'merge_deleted_data': True,
                    'common_cols': [
                        "PSTUDYNM", "PSTUDYID", "GROUPID", "ISDEL", "CRFVER"
                    ],
                    'exclude_sheets': ["Code_List", "DOMAIN_NAME"],
                    'default_keys': [
                        "SUBJID", "VISTOID", "VISTREP", "FORMOID", "FORMREP", "RECREP"
                    ],
                    'sheet_key_map': {},
                    'colors': {
                        'highlight_fill': '#FFE5E5',
                        'missing_sheet_tab': '#DC143C',
                        'new_sheet_tab': '#00FF00'
                    }
                }
            }
            for name, params in templates.items():
                cfg_path = self.get_config_path(name)
                if not os.path.exists(cfg_path):
                    try:
                        with open(cfg_path, 'w', encoding='utf-8') as f:
                            json.dump(params, f, ensure_ascii=False, indent=4)
                        log(f"已创建内置模板: {name}", None)
                    except Exception as e:
                        log(f"创建内置模板 '{name}' 失败: {e}", None)
        except Exception as e:
            log(f"确保内置模板存在时出错: {e}", None)

    def load_parameters(self):
        """从parameters.json文件加载参数。如果文件不存在或加载失败，则使用默认参数。"""
        # 此方法不再直接从parameters.json加载，而是调用_load_initial_config
        # 实际上，_load_initial_config已经在__init__中调用，这里留作兼容性或未来扩展
        return self._load_initial_config()

    def save_parameters(self):
        """将当前参数保存到当前活跃的配置文件。"""
        if not self.current_config_name:
            # 无当前配置名时，不进行保存
            log("无当前配置名称，已跳过保存。", None)
            return False
        # 内置模板保护：不允许覆盖保存
        if self.current_config_name in (BUILTIN_TEMPLATE_CIMS, BUILTIN_TEMPLATE_TM):
            log(f"'{self.current_config_name}' 为内置模板，已阻止覆盖保存。", None)
            return False
        return self.save_config_as(self.current_config_name, self.parameters)
    
    def _get_original_template_params(self):
        """获取原始模板参数，用于检测模板是否被修改。"""
        try:
            current_name = self.current_config_name
            if current_name == BUILTIN_TEMPLATE_CIMS:
                return self._get_builtin_template_params(BUILTIN_TEMPLATE_CIMS)
            elif current_name == BUILTIN_TEMPLATE_TM:
                return self._get_builtin_template_params(BUILTIN_TEMPLATE_TM)
            else:
                return None
        except Exception as e:
            log(f"获取原始模板参数时出错: {e}", None)
            return None
    
    def _get_builtin_template_params(self, template_name):
        """获取指定内置模板的原始参数。"""
        if template_name == BUILTIN_TEMPLATE_CIMS:
            return {
                'old_file_path': '',
                'new_file_path': '',
                'output_directory': '',
                'anchor_row_num': 1,
                'header_row_num': 2,
                'merge_deleted_data': True,
                'common_cols': [
                    "STUDYID", "RANDID", "SUBINI", "SUBSTA", "FORMNO", "FORMSTA",
                    "STA_DEC", "SDVSTA", "DMRSTA", "MR_STA", "TOPIC"
                ],
                'exclude_sheets': [
                    "系统变量", "数据范围", "eCRF表单", "CPH_FT--Header & Footer", "eCRF备注日志"
                ],
                'default_keys': ["SUBJID", "VISITNUM", "FORMSEQ", "TOPICSEQ"],
                'sheet_key_map': {},
                'colors': {
                    'highlight_fill': '#FFE5E5',
                    'missing_sheet_tab': '#DC143C',
                    'new_sheet_tab': '#00FF00'
                }
            }
        elif template_name == BUILTIN_TEMPLATE_TM:
            return {
                'old_file_path': '',
                'new_file_path': '',
                'output_directory': '',
                'anchor_row_num': 2,
                'header_row_num': 1,
                'merge_deleted_data': True,
                'common_cols': [
                    "PSTUDYNM", "PSTUDYID", "GROUPID", "ISDEL", "CRFVER"
                ],
                'exclude_sheets': ["Code_List", "DOMAIN_NAME"],
                'default_keys': [
                    "SUBJID", "VISTOID", "VISTREP", "FORMOID", "FORMREP", "RECREP"
                ],
                'sheet_key_map': {},
                'colors': {
                    'highlight_fill': '#FFE5E5',
                    'missing_sheet_tab': '#DC143C',
                    'new_sheet_tab': '#00FF00'
                }
            }
        return None

    def show_parameter_manager(self):
        """显示参数管理窗口。"""
        if self.window: # 如果窗口已存在，则先销毁旧窗口
            self.window.destroy()

        self.window = tk.Toplevel(self.main_app.root) # 创建一个新的顶级窗口
        self.window.title("参数管理")
        self.window.geometry("400x300") # 设置窗口大小

        set_window_icon(self.window) # 为参数管理窗口设置图标

        # 创建notebook（选项卡式界面）用于切换不同类型的参数
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill='both', expand=True, padx=10, pady=5)

        # 创建各个参数类型的页面，并添加到notebook中
        self.create_common_cols_page(notebook)
        self.create_exclude_sheets_page(notebook)
        self.create_default_keys_page(notebook)
        self.create_sheet_key_map_page(notebook)

        # 添加关闭按钮和关闭窗口的方法
        btn_frame = ttk.Frame(self.window)
        btn_frame.pack(pady=10, padx=10, fill='x')
        close_btn = ttk.Button(btn_frame, text='关闭', command=self.close_window)
        close_btn.pack(side=tk.RIGHT)

        # 添加关闭窗口事件处理，确保点击窗口X按钮也能正确关闭并保存参数
        def on_closing():
            self.close_window()

        self.window.protocol("WM_DELETE_WINDOW", on_closing)

    def close_window(self):
        """关闭参数管理窗口，并在关闭前保存所有参数。"""
        if hasattr(self, 'window') and self.window:
            self.save_parameters() # 保存参数
            self.window.destroy() # 销毁窗口
            self.window = None # 将窗口引用设为None

    def create_common_cols_page(self, notebook):
        """创建并填充"删除列"参数页面。"""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="删除列")

        # 创建列表框和滚动条用于显示和管理列名
        list_frame = ttk.Frame(frame)
        list_frame.pack(fill='both', expand=True, padx=5, pady=5)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side='right', fill='y')

        self.common_cols_list = tk.Listbox(list_frame, yscrollcommand=scrollbar.set) # 列名列表框
        self.common_cols_list.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=self.common_cols_list.yview) # 关联滚动条

        # 添加按钮框架，包含"添加"和"删除"按钮
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', padx=5, pady=5)

        ttk.Button(btn_frame, text="添加", command=lambda: self.add_parameter('common_cols')).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="删除", command=lambda: self.delete_parameter('common_cols')).pack(side='left', padx=5)

        # 加载现有参数到列表框
        for item in self.parameters['common_cols']:
            self.common_cols_list.insert(tk.END, item)

    def create_exclude_sheets_page(self, notebook):
        """创建并填充"排除表单"参数页面。"""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="排除表单")

        list_frame = ttk.Frame(frame)
        list_frame.pack(fill='both', expand=True, padx=5, pady=5)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side='right', fill='y')

        self.exclude_sheets_list = tk.Listbox(list_frame, yscrollcommand=scrollbar.set)
        self.exclude_sheets_list.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=self.exclude_sheets_list.yview)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', padx=5, pady=5)

        ttk.Button(btn_frame, text="添加", command=lambda: self.add_parameter('exclude_sheets')).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="删除", command=lambda: self.delete_parameter('exclude_sheets')).pack(side='left', padx=5)

        for item in self.parameters['exclude_sheets']:
            self.exclude_sheets_list.insert(tk.END, item)

    def create_default_keys_page(self, notebook):
        """创建并填充"默认锚点"参数页面。"""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="默认锚点")

        list_frame = ttk.Frame(frame)
        list_frame.pack(fill='both', expand=True, padx=5, pady=5)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side='right', fill='y')

        self.default_keys_list = tk.Listbox(list_frame, yscrollcommand=scrollbar.set)
        self.default_keys_list.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=self.default_keys_list.yview)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', padx=5, pady=5)

        ttk.Button(btn_frame, text="添加", command=lambda: self.add_parameter('default_keys')).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="删除", command=lambda: self.delete_parameter('default_keys')).pack(side='left', padx=5)

        for item in self.parameters['default_keys']:
            self.default_keys_list.insert(tk.END, item)

    def create_sheet_key_map_page(self, notebook):
        """创建并填充"指定表单锚点"参数页面。"""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="指定表单锚点")

        list_frame = ttk.Frame(frame)
        list_frame.pack(fill='both', expand=True, padx=5, pady=5)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side='right', fill='y')

        self.sheet_key_map_list = tk.Listbox(list_frame, yscrollcommand=scrollbar.set)
        self.sheet_key_map_list.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=self.sheet_key_map_list.yview)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', padx=5, pady=5)

        ttk.Button(btn_frame, text="添加", command=lambda: self.add_sheet_key_map()).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="删除", command=lambda: self.delete_sheet_key_map()).pack(side='left', padx=5)

        for sheet, keys in self.parameters['sheet_key_map'].items():
            self.sheet_key_map_list.insert(tk.END, f"{sheet}: {', '.join(keys)}") # 显示Sheet名和对应的锚点列表


    def add_parameter(self, param_type):
        """通用方法：弹出对话框，允许用户添加指定类型的单个参数（如删除列、排除表单、默认锚点）。"""
        dialog = tk.Toplevel(self.window) # 创建一个顶级对话框窗口
        dialog.title("添加参数")
        dialog.geometry("300x150") # 设置大小
        dialog.configure(bg='#f5f6fa') # 设置背景色

        set_window_icon(dialog) # 为对话框设置图标

        # 设置对话框样式
        style = ttk.Style()
        style.configure('Dialog.TLabel', background='#f5f6fa', font=('微软雅黑', 10))
        style.configure('Dialog.TEntry', font=('微软雅黑', 10))

        # 创建内容框架
        content_frame = ttk.Frame(dialog, style='Dialog.TFrame')
        content_frame.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(content_frame, text="请输入参数值:", style='Dialog.TLabel').pack(pady=5)
        entry = ttk.Entry(content_frame, width=30, style='Dialog.TEntry')
        entry.pack(pady=5)

        def save():
            value = entry.get().strip() # 获取输入值并去除空白
            if value:
                if param_type == 'common_cols':
                    self.common_cols_list.insert(tk.END, value) # 添加到列表框
                    if 'common_cols' not in self.parameters: # 防御性编程
                        self.parameters['common_cols'] = []
                    self.parameters['common_cols'].append(value) # 添加到参数字典
                elif param_type == 'exclude_sheets':
                    self.exclude_sheets_list.insert(tk.END, value)
                    self.parameters['exclude_sheets'].append(value)
                elif param_type == 'default_keys':
                    self.default_keys_list.insert(tk.END, value)
                    self.parameters['default_keys'].append(value)
                self.save_parameters() # 保存参数到文件
                self.main_app.update_parameter_display() # 通知父GUI更新参数显示
            dialog.destroy() # 关闭对话框

        tk.Button(content_frame, text="保存", command=save).pack(pady=10)

        entry.focus_set() # 设置焦点到输入框

    def delete_parameter(self, param_type):
        """通用方法：从指定类型的参数列表中删除选定的参数。"""
        if param_type == 'common_cols':
            selection = self.common_cols_list.curselection() # 获取选中的索引
            if selection:
                index = selection[0]
                value = self.common_cols_list.get(index) # 获取选中值
                self.common_cols_list.delete(index) # 从列表框删除
                self.parameters['common_cols'].remove(value) # 从参数字典删除
        elif param_type == 'exclude_sheets':
            selection = self.exclude_sheets_list.curselection()
            if selection:
                index = selection[0]
                value = self.exclude_sheets_list.get(index)
                self.exclude_sheets_list.delete(index)
                self.parameters['exclude_sheets'].remove(value)
        elif param_type == 'default_keys':
            selection = self.default_keys_list.curselection()
            if selection:
                index = selection[0]
                value = self.default_keys_list.get(index)
                self.default_keys_list.delete(index)
                self.parameters['default_keys'].remove(value)
        self.save_parameters() # 保存参数到文件
        self.main_app.update_parameter_display() # 通知父GUI更新参数显示

    def add_sheet_key_map(self):
        """弹出对话框，允许用户添加或修改特定表单的锚点映射。"""
        dialog = tk.Toplevel(self.window)
        dialog.title("添加参数")
        dialog.geometry("400x200")

        set_window_icon(dialog) # 为对话框设置图标

        ttk.Label(dialog, text="表单名称:").pack(pady=5)
        sheet_entry = ttk.Entry(dialog, width=40)
        sheet_entry.pack(pady=5)

        ttk.Label(dialog, text="锚点列表(用逗号分隔):").pack(pady=5)
        keys_entry = ttk.Entry(dialog, width=40)
        keys_entry.pack(pady=5)

        def save():
            sheet = sheet_entry.get().strip() # 获取Sheet名称
            keys = [k.strip() for k in keys_entry.get().split(',') if k.strip()] # 解析逗号分隔的锚点列表
            if sheet and keys: # 确保Sheet名称和锚点列表都不为空
                self.sheet_key_map_list.insert(tk.END, f"{sheet}: {', '.join(keys)}") # 更新列表框显示
                self.parameters['sheet_key_map'][sheet] = keys # 更新参数字典
                self.save_parameters() # 保存参数到文件
                self.main_app.update_parameter_display() # 通知父GUI更新参数显示
            dialog.destroy() # 关闭对话框

        tk.Button(dialog, text="保存", command=save).pack(pady=10)

        # entry.focus_set() # 设置焦点到输入框

    def delete_sheet_key_map(self):
        """删除选定的特定表单锚点映射。"""
        selection = self.sheet_key_map_list.curselection()
        if selection:
            index = selection[0]
            value = self.sheet_key_map_list.get(index) # 获取选中项的显示文本
            sheet = value.split(':')[0].strip() # 从显示文本中提取Sheet名称
            self.sheet_key_map_list.delete(index) # 从列表框删除
            del self.parameters['sheet_key_map'][sheet] # 从参数字典删除
            self.save_parameters() # 保存参数到文件
            self.main_app.update_parameter_display() # 通知父GUI更新参数显示

    def get_parameters(self):
        """返回当前所有加载和修改后的参数字典。"""
        return self.parameters

    def _get_default_parameters(self):
        """返回默认参数字典。"""
        return {
            'old_file_path': '',
            'new_file_path': '',
            'output_directory': '',
            'anchor_row_num': 1,
            'header_row_num': 1,
            'max_workers': max(1, os.cpu_count() - 1), # 默认最大线程数为CPU核心数减1，至少为1
            'merge_deleted_data': True,
        }

    def update_parameter(self, key, value):
        """更新单个参数。注意：此方法不再自动保存参数。需手动调用save_parameters。"""
        if key in self.parameters:
            self.parameters[key] = value
        else:
            log(f"警告: 尝试更新不存在的参数键: {key}", None) 