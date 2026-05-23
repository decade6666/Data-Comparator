import datetime
import queue
import time
import tkinter as tk
from tkinter import ttk

class GUIUpdateType:
    """GUI更新消息类型枚举
    定义了不同类型的GUI更新，用于在后台线程和主GUI线程之间传递指令。
    """
    PROGRESS = "progress" # 进度更新消息
    RESET_PROGRESS = "reset_progress" # 重置进度条消息
    BUTTON_STATE = "button_state" # 按钮状态更新消息（启用/禁用）
    PARAMETER_DISPLAY = "parameter_display" # 参数显示更新消息
    COLOR_UPDATE = "color_update" # 颜色设置更新消息
    LOG_MESSAGE = "log_message" # 日志消息更新

class GUIUpdateMessage:
    """GUI更新消息
    封装了GUI更新的类型、数据和可选的回调函数。
    """
    def __init__(self, msg_type, data=None, callback=None):
        self.msg_type = msg_type # 消息类型，取自GUIUpdateType
        self.data = data # 消息携带的数据，具体内容取决于msg_type
        self.callback = callback # 可选的回调函数，在GUI更新执行后调用
        self.timestamp = time.time() # 消息创建时间戳

class GUIUpdateManager:
    """专门的GUI更新管理器，确保所有GUI更新都在主线程中执行
    通过一个线程安全的队列来接收来自其他线程的更新请求，
    并通过Tkinter的`after`方法在主线程中调度这些更新，避免GUI卡顿。
    """
    
    def __init__(self, root):
        """
        初始化GUI更新管理器。
        Args:
            root: Tkinter的根窗口对象。
        """
        self.root = root # Tkinter根窗口
        self.update_queue = queue.Queue() # 线程安全的更新队列
        self.is_running = True # 标记管理器是否正在运行
        self.update_interval = 50  # 更新间隔 (50ms)，每50毫秒检查一次队列

        # 启动GUI更新循环
        self.start_update_loop()
    
    def start_update_loop(self):
        """启动GUI更新循环，通过`process_updates`方法周期性检查队列。"""
        self.process_updates()
    
    def process_updates(self):
        """
        处理GUI更新队列中的消息。
        此方法会在主线程中周期性调用，批量处理队列中的更新请求。
        """
        if not self.is_running:
            return
            
        try:
            # 批量处理多个更新以提高效率，避免过于频繁的GUI刷新
            updates_processed = 0
            max_updates_per_cycle = 10  # 每次最多处理10个更新，防止单次循环耗时过长
            
            while updates_processed < max_updates_per_cycle:
                try:
                    message = self.update_queue.get_nowait() # 非阻塞获取消息
                    self._execute_update(message) # 执行更新
                    updates_processed += 1
                except queue.Empty:
                    break # 队列为空，退出批量处理
                    
        except Exception as e:
            print(f"GUI更新处理出错: {str(e)}") # 打印异常信息
        
        # 调度下一次更新，确保周期性执行
        if self.is_running:
            self.root.after(self.update_interval, self.process_updates)
    
    def _execute_update(self, message):
        """
        根据消息类型执行具体的GUI更新操作。
        此方法在主线程中执行，安全地修改GUI组件。
        """
        try:
            if message.msg_type == GUIUpdateType.PROGRESS:
                self._update_progress(message.data)
            elif message.msg_type == GUIUpdateType.RESET_PROGRESS:
                self._reset_progress()
            elif message.msg_type == GUIUpdateType.BUTTON_STATE:
                self._update_button_state(message.data)
            elif message.msg_type == GUIUpdateType.PARAMETER_DISPLAY:
                self._update_parameter_display()
            elif message.msg_type == GUIUpdateType.COLOR_UPDATE:
                self._update_color(message.data)
            elif message.msg_type == GUIUpdateType.LOG_MESSAGE:
                # 日志现在直接写入文件，GUI层面不显示，所以这里为空
                pass
            
            # 执行回调函数（如果有的话）
            if message.callback:
                message.callback()
                
        except tk.TclError:
            # 窗口已关闭时可能引发TclError，此时忽略错误
            pass
        except Exception as e:
            print(f"执行GUI更新失败: {str(e)}") # 打印其他执行错误
    
    def _update_progress(self, data):
        """
        更新进度显示（包括进度文本和进度条）。
        Args:
            data (dict): 包含'message'（进度文本）和'progress'（进度百分比）的字典。
        """
        message = data.get('message', '') # 进度消息文本
        progress = data.get('progress', None) # 进度值 (0-100)
        
        if hasattr(self.root, 'app'):
            app = self.root.app # 获取GUI实例
            if message is not None and hasattr(app, 'progress_label_var'):
                app.progress_label_var.set(message) # 更新进度文本
            if progress is not None and hasattr(app, 'progress_var'):
                app.progress_var.set(progress) # 更新进度条值
    
    def _reset_progress(self):
        """重置进度条到初始状态（0）。"""
        if hasattr(self.root, 'app'):
            app = self.root.app
            if hasattr(app, 'progress_var'):
                app.progress_var.set(0) # 将进度条值设为0
            if hasattr(app, 'progress_label_var'):
                app.progress_label_var.set("准备就绪") # 重置标签
    
    def _update_button_state(self, data):
        """
        更新指定按钮的状态（启用/禁用）和鼠标光标。
        Args:
            data (dict): 包含'button'（按钮属性名）、'state'（状态，如'normal'/'disabled'）和'cursor'（鼠标光标样式）的字典。
        """
        button_name = data.get('button') # 按钮的实例属性名
        state = data.get('state') # 按钮状态
        cursor = data.get('cursor') # 鼠标光标样式
        
        if hasattr(self.root, 'app'):
            app = self.root.app
            if button_name and hasattr(app, button_name):
                button = getattr(app, button_name)
                if state:
                    button.config(state=state) # 通过属性名获取并设置按钮状态
                if cursor:
                    button.config(cursor=cursor) # 单独为按钮设置光标
    
    def _update_parameter_display(self):
        """触发GUI实例中的参数显示更新。"""
        if hasattr(self.root, 'app'):
            app = self.root.app
            if hasattr(app, '_update_parameter_cards'):
                app._update_parameter_cards() # 调用GUI实例的具体更新方法
    
    def _update_color(self, data):
        """
        更新界面上的颜色显示和颜色变量。
        Args:
            data (dict): 包含'type'（颜色类型，如'highlight'/'missing'/'new'）和'value'（颜色值，如'#RRGGBB'）的字典。
        """
        color_type = data.get('type') # 颜色类型
        color_value = data.get('value') # 颜色值
        
        if hasattr(self.root, 'app'):
            app = self.root.app
            if color_type == 'highlight' and hasattr(app, 'highlight_color_btn'):
                app.highlight_color_btn.config(bg=color_value) # 更新高亮按钮背景色
                app.highlight_color_var.set(color_value) # 更新高亮颜色变量
            elif color_type == 'missing' and hasattr(app, 'missing_color_btn'):
                app.missing_color_btn.config(bg=color_value) # 更新缺失按钮背景色
                app.missing_color_var.set(color_value) # 更新缺失颜色变量
            elif color_type == 'new' and hasattr(app, 'new_color_btn'):
                app.new_color_btn.config(bg=color_value) # 更新新增按钮背景色
                app.new_color_var.set(color_value) # 更新新增颜色变量
    
    def post_update(self, msg_type, data=None, callback=None):
        """
        向GUI更新队列投递消息。
        此方法可以从任何线程调用，用于请求GUI更新。
        Args:
            msg_type (GUIUpdateType): 要发送的消息类型。
            data (any, optional): 消息携带的数据。
            callback (function, optional): 消息处理完成后在主线程执行的回调函数。
        """
        message = GUIUpdateMessage(msg_type, data, callback) # 创建消息对象
        self.update_queue.put(message) # 将消息放入队列
    
    def stop(self):
        """停止GUI更新管理器，中断其更新循环。"""
        self.is_running = False # 设置停止标志 