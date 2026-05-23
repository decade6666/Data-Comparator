#运行代码：python -m src.main
import os
import sys
import tkinter as tk
import ttkbootstrap as ttk
from src.utils.file_utils import set_window_icon

# 动态地将项目根目录添加到 sys.path，以支持打包和开发环境
if getattr(sys, 'frozen', False):
    # 在 PyInstaller 打包环境下运行
    # sys._MEIPASS 是单文件模式下提取内容的临时目录
    # os.path.dirname(sys.executable) 是单目录模式下可执行文件所在的目录
    # 我们需要将 PyInstaller 包的根目录添加到 sys.path。
    # 通常，'数据集对比' 顶级包会直接位于这个根目录。
    bundle_dir = sys._MEIPASS if hasattr(sys, '_MEIPASS') else os.path.dirname(os.path.abspath(sys.executable))
    # 对于单文件模式，PyInstaller 会把所有数据文件放在 sys._MEIPASS
    # 对于单目录模式，数据文件则在可执行文件同级目录
    # icon_path = os.path.join(bundle_dir, 'src', 'assets', 'icons', 'app_icon.ico') # 这是假设打包后的结构不变
    # 更安全的做法是，将app_icon.ico也添加到datas，并使用 os.path.join(sys._MEIPASS, 'app_icon.ico')
    # 鉴于app.spec中已经有icon_path，我们保持一致
    if bundle_dir not in sys.path:
        sys.path.insert(0, bundle_dir)
else:
    # 在普通 Python 开发环境下运行
    # 当前脚本路径是 'E:\文档\Gitee\py_-data-compare\src\main.py'
    # 我们需要将 'E:\文档\Gitee\py_-data-compare' (即项目根目录) 添加到 sys.path
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root_dir = os.path.abspath(os.path.join(current_script_dir, os.pardir))
    if project_root_dir not in sys.path:
        sys.path.insert(0, project_root_dir)

# 根据运行环境动态导入主GUI类
# (之前的导入逻辑可以简化，因为路径已经设置好了)
from src.gui.main_window import DatasetComparatorGUI


def main():
    root = ttk.Window(themename="darkly")

    # 统一使用与“使用帮助”弹窗相同的图标设置逻辑
    set_window_icon(root)

    app = DatasetComparatorGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.cleanup)  # 确保在关闭窗口时调用清理函数
    root.mainloop()

if __name__ == '__main__':
    main()
