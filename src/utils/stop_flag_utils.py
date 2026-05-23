import threading
from .logger import log

# 全局停止标志，用于快速检查
_global_stop_flag = None

def set_global_stop_flag(stop_flag):
    """设置全局停止标志，用于在多线程操作中控制程序的停止。"""
    global _global_stop_flag
    _global_stop_flag = stop_flag # 将传入的Event对象赋值给全局变量

def check_stop_frequently(log_func, stop_flag=None):
    """高频率停止检查，用于关键处理路径，确保程序能及时响应停止指令。"""
    global _global_stop_flag
    current_flag = stop_flag or _global_stop_flag # 优先使用传入的stop_flag，否则使用全局的
    if current_flag and current_flag.is_set(): # 检查停止标志是否被设置
        log("处理已被用户停止", log_func) # 记录日志
        raise InterruptedError("用户停止了操作") # 抛出中断异常，终止当前操作

# 检查是否应该停止处理 - 带计数器优化
def check_stop(log_func, stop_flag=None, check_counter=None):
    """检查是否应该停止处理，带计数器优化性能，减少不必要的频繁检查。
    在耗时循环中，可以每隔N次操作检查一次停止标志。
    Args:
        log_func (callable): 日志函数。
        stop_flag (threading.Event, optional): 停止标志Event对象。
        check_counter (list, optional): 包含一个整数的列表，用于计数检查频率。
    """
    global _global_stop_flag
    current_flag = stop_flag or _global_stop_flag # 优先使用传入的stop_flag，否则使用全局的
    
    # 使用计数器减少检查频率，提升性能
    if check_counter is not None:
        if check_counter[0] % 100 != 0:  # 每100次操作检查一次（可调整频率）
            check_counter[0] += 1
            return
        check_counter[0] += 1
    
    if current_flag and current_flag.is_set(): # 检查停止标志是否被设置
        log("处理已被用户停止", log_func) # 记录日志
        raise InterruptedError("用户停止了操作") # 抛出中断异常

#更新进度条 - 线程安全版本
def update_progress(msg, progress=None, progress_func=None):
    """线程安全的进度更新函数。
    通过回调函数将进度信息传递给GUI，避免直接在工作线程中操作GUI。
    Args:
        msg (str): 进度消息文本。
        progress (int, optional): 进度百分比 (0-100)。
        progress_func (callable, optional): 实际执行GUI进度更新的回调函数。
    """
    if progress_func: # 如果提供了进度更新函数
        try:
            progress_func(msg, progress) # 调用回调函数更新GUI
        except Exception as e:
            # 如果进度更新失败，不中断主流程，只是打印错误到控制台
            print(f"进度更新异常: {str(e)}") 