from typing import Any

from ...shared.log_utils import log


def reorder_columns_with_update_mark_first(df: Any) -> Any:
    try:
        if "更新情况（标记）" in df.columns:
            cols = df.columns.tolist()
            cols.remove("更新情况（标记）")
            cols.insert(0, "更新情况（标记）")
            df = df[cols]
        return df
    except Exception as e:
        log(f"⚠️ 调整列顺序时出错: {str(e)}", None)
        return df
