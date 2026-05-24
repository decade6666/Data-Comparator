from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    import pandas as pd


class SheetProcessResult:
    """单个 Excel sheet 的处理结果。"""

    def __init__(self, sheet_name: str) -> None:
        self.sheet_name = sheet_name
        self.success = False
        self.error_message: Optional[str] = None
        self.change_type: Optional[str] = None
        self.differences: Optional[Dict[str, Any]] = None
        self.add_sas_names: List[str] = []
        self.del_sas_names: List[str] = []
        self.sas_file_names: List[str] = []
        self.sas_file_labels: List[str] = []
        self.sas_name_to_label: Dict[str, str] = {}
        self.is_split_result = False
        self.split_chunks: List[Any] = []
        self.original_source_file: Optional[str] = None
        self.original_source_sheet_name: Optional[str] = None
        self.df: Optional[pd.DataFrame] = None
        self.updated_rows_count = 0
        self.deleted_rows_count = 0
        self.added_rows_count = 0
