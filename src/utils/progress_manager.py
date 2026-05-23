import threading

class ThreadSafeProgressManager:
    """线程安全的进度管理器
    用于在多线程环境中安全地更新比对进度和日志。
    """
    def __init__(self, total_sheets, progress_func, log_func):
        """
        初始化线程安全的进度管理器。
        Args:
            total_sheets (int): 总共需要处理的Sheet数量。
            progress_func (callable): 用于更新GUI进度的回调函数。
            log_func (callable): 用于记录日志的回调函数。
        """
        self.total_sheets = total_sheets # 总Sheet数量
        self.progress_func = progress_func # GUI进度更新函数
        self.log_func = log_func # 日志记录函数
        self.completed_sheets_count = 0  # 已完成处理的Sheet计数
        self.lock = threading.Lock() # 线程锁，确保数据访问的原子性
        
    def update_sheet_progress(self, sheet_name, status="处理中", is_final_update=False):
        """
        更新单个Sheet的处理进度。
        Args:
            sheet_name (str): 当前处理的Sheet名称。
            status (str): Sheet的当前处理状态（如"处理中", "新增表单"等）。
            is_final_update (bool): 是否为该Sheet的最终进度更新。
        """
        with self.lock: # 确保线程安全
            if is_final_update:
                self.completed_sheets_count += 1 # 只有在最终更新时才增加完成计数
            
            # 进度计算基于实际完成的sheets，从30%开始（预处理部分）
            progress = 30 + (self.completed_sheets_count / self.total_sheets) * 50 if self.total_sheets > 0 else 30
            
            # 仅在最终更新时显示完成信息
            display_message = None if not is_final_update else f"已完成表单 [{self.completed_sheets_count}/{self.total_sheets}]: {sheet_name}"
            
            if self.progress_func:
                try:
                    self.progress_func(
                        display_message,
                        progress
                    )
                except Exception as e:
                    # 如果进度更新失败，记录但不中断处理
                    if self.log_func:
                        self.log_func(f"进度更新失败: {str(e)}")
            
    def safe_log(self, message):
        """线程安全地记录日志。"""
        with self.lock:
            if self.log_func:
                self.log_func(message) 