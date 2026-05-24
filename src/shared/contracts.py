from typing import Callable, Dict, List, Protocol, TypedDict

LogFunc = Callable[[str], None]


class ParameterColors(TypedDict, total=False):
    highlight_fill: str
    missing_sheet_tab: str
    new_sheet_tab: str


class ParameterDocument(TypedDict, total=False):
    old_file_path: str
    new_file_path: str
    output_directory: str
    anchor_row_num: int
    header_row_num: int
    anchor_row_content: str
    header_row_content: str
    max_workers: int
    merge_deleted_data: bool
    common_cols: List[str]
    exclude_sheets: List[str]
    default_keys: List[str]
    sheet_key_map: Dict[str, List[str]]
    colors: ParameterColors


class ParameterRepository(Protocol):
    current_config_name: str

    def list_configurations(self) -> List[str]: ...

    def load_config(self, config_name: str) -> bool: ...

    def save_config_as(
        self, config_name: str, parameters_to_save: ParameterDocument
    ) -> bool: ...

    def delete_config(self, config_name: str) -> bool: ...


class ProgressReporter(Protocol):
    log_func: LogFunc

    def update_sheet_progress(
        self,
        sheet_name: str,
        status: str = "处理中",
        is_final_update: bool = False,
    ) -> None: ...

    def safe_log(self, message: str) -> None: ...
