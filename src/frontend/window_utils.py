import os
from typing import Any

from ..shared.log_utils import log
from ..shared.resource_utils import get_resource_path


def set_window_icon(window: Any) -> None:
    try:
        icon_files = [
            "app_icon.ico",
            os.path.join("assets", "icons", "app_icon.ico"),
        ]

        icon_loaded = False
        for icon_file in icon_files:
            icon_path = get_resource_path(icon_file)
            if os.path.exists(icon_path):
                window.iconbitmap(icon_path)
                log(f"[OK] 成功加载图标: {icon_file}", None)
                icon_loaded = True
                break

        if not icon_loaded:
            log("[WARN] 未找到图标文件，使用默认图标", None)
    except Exception as e:
        log(f"[ERROR] 设置图标失败: {str(e)}", None)
