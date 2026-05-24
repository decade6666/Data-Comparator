import os
import sys

import ttkbootstrap as ttk

if getattr(sys, "frozen", False):
    bundle_dir = getattr(
        sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable))
    )
else:
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    bundle_dir = os.path.abspath(os.path.join(current_script_dir, os.pardir))

if bundle_dir not in sys.path:
    sys.path.insert(0, bundle_dir)

from src.frontend.window_utils import set_window_icon
from src.gui.main_window import DatasetComparatorGUI


def main() -> None:
    root = ttk.Window(themename="darkly")
    set_window_icon(root)

    app = DatasetComparatorGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.cleanup)
    root.mainloop()


if __name__ == "__main__":
    main()
