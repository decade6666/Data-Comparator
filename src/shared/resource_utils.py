import os
import sys


def get_resource_path(relative_path: str) -> str:
    base_path = getattr(sys, "_MEIPASS", None)
    if base_path is None:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        base_path = os.path.join(current_dir, os.pardir)

    return os.path.join(base_path, relative_path)
