# log_utils.py
import sys

def log(msg, log_func):
    """通用的日志记录函数，将消息传递给传入的日志回调。"""
    try:
        print(msg) # 增加此行以打印到控制台
    except UnicodeEncodeError:
        # 如果默认编码无法处理，则使用UTF-8编码
        print(msg.encode('utf-8', 'replace').decode(sys.stdout.encoding or 'utf-8', 'replace'))
    if log_func:
        log_func(msg) 