import queue
import time
import tkinter as tk


class GUIUpdateType:
    """GUI更新消息类型枚举
    定义了不同类型的GUI更新，用于在后台线程和主GUI线程之间传递指令。
    """

    PROGRESS = "progress"
    RESET_PROGRESS = "reset_progress"
    BUTTON_STATE = "button_state"
    PARAMETER_DISPLAY = "parameter_display"
    COLOR_UPDATE = "color_update"
    LOG_MESSAGE = "log_message"


class GUIUpdateMessage:
    """GUI更新消息
    封装了GUI更新的类型、数据和可选的回调函数。
    """

    def __init__(self, msg_type, data=None, callback=None):
        self.msg_type = msg_type
        self.data = data
        self.callback = callback
        self.timestamp = time.time()


class GUIUpdateManager:
    """专门的GUI更新管理器，确保所有GUI更新都在主线程中执行
    通过一个线程安全的队列来接收来自其他线程的更新请求，
    并通过Tkinter的`after`方法在主线程中调度这些更新，避免GUI卡顿。
    """

    def __init__(self, root):
        self.root = root
        self.update_queue = queue.Queue()
        self.is_running = True
        self.update_interval = 50
        self.start_update_loop()

    def start_update_loop(self):
        self.process_updates()

    def process_updates(self):
        if not self.is_running:
            return

        try:
            updates_processed = 0
            max_updates_per_cycle = 10

            while updates_processed < max_updates_per_cycle:
                try:
                    message = self.update_queue.get_nowait()
                    self._execute_update(message)
                    updates_processed += 1
                except queue.Empty:
                    break
        except Exception as e:
            print(f"GUI更新处理出错: {str(e)}")

        if self.is_running:
            self.root.after(self.update_interval, self.process_updates)

    def _execute_update(self, message):
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
                pass

            if message.callback:
                message.callback()
        except tk.TclError:
            pass
        except Exception as e:
            print(f"执行GUI更新失败: {str(e)}")

    def _update_progress(self, data):
        message = data.get("message", "")
        progress = data.get("progress", None)

        if hasattr(self.root, "app"):
            app = self.root.app
            if message is not None and hasattr(app, "progress_label_var"):
                app.progress_label_var.set(message)
            if progress is not None and hasattr(app, "progress_var"):
                app.progress_var.set(progress)

    def _reset_progress(self):
        if hasattr(self.root, "app"):
            app = self.root.app
            if hasattr(app, "progress_var"):
                app.progress_var.set(0)
            if hasattr(app, "progress_label_var"):
                app.progress_label_var.set("准备就绪")

    def _update_button_state(self, data):
        button_name = data.get("button")
        state = data.get("state")
        cursor = data.get("cursor")

        if hasattr(self.root, "app"):
            app = self.root.app
            if button_name and hasattr(app, button_name):
                button = getattr(app, button_name)
                if state:
                    button.config(state=state)
                if cursor:
                    button.config(cursor=cursor)

    def _update_parameter_display(self):
        if hasattr(self.root, "app"):
            app = self.root.app
            if hasattr(app, "_update_parameter_cards"):
                app._update_parameter_cards()

    def _update_color(self, data):
        color_type = data.get("type")
        color_value = data.get("value")

        if hasattr(self.root, "app"):
            app = self.root.app
            if color_type == "highlight" and hasattr(app, "highlight_color_btn"):
                app.highlight_color_btn.config(bg=color_value)
                app.highlight_color_var.set(color_value)
            elif color_type == "missing" and hasattr(app, "missing_color_btn"):
                app.missing_color_btn.config(bg=color_value)
                app.missing_color_var.set(color_value)
            elif color_type == "new" and hasattr(app, "new_color_btn"):
                app.new_color_btn.config(bg=color_value)
                app.new_color_var.set(color_value)

    def post_update(self, msg_type, data=None, callback=None):
        message = GUIUpdateMessage(msg_type, data, callback)
        self.update_queue.put(message)

    def stop(self):
        self.is_running = False
