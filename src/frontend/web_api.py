from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from ..backend.application.comparison_runner import run_comparison
from ..shared.contracts import ParameterColors, ParameterDocument
from ..shared.log_utils import log

API_TITLE = "Dataset Comparator API"
API_VERSION = "1.0.0"

app = FastAPI(title=API_TITLE, version=API_VERSION)


class CompareColors(BaseModel):
    highlight_fill: Optional[str] = None
    missing_sheet_tab: Optional[str] = None
    new_sheet_tab: Optional[str] = None


class CompareRequest(BaseModel):
    old_file_path: str
    new_file_path: str
    output_directory: str
    config_name: str = "web"
    anchor_row_num: int = 1
    header_row_num: int = 1
    anchor_row_content: str = "SASFieldName"
    header_row_content: str = "SASFieldLabel"
    max_workers: Optional[int] = None
    merge_deleted_data: bool = True
    common_cols: List[str] = Field(default_factory=list)
    exclude_sheets: List[str] = Field(default_factory=list)
    default_keys: List[str] = Field(default_factory=list)
    sheet_key_map: Dict[str, List[str]] = Field(default_factory=dict)
    colors: CompareColors = Field(default_factory=CompareColors)

    def to_parameter_document(self) -> ParameterDocument:
        document: ParameterDocument = {
            "old_file_path": self.old_file_path,
            "new_file_path": self.new_file_path,
            "output_directory": self.output_directory,
            "anchor_row_num": self.anchor_row_num,
            "header_row_num": self.header_row_num,
            "anchor_row_content": self.anchor_row_content,
            "header_row_content": self.header_row_content,
            "merge_deleted_data": self.merge_deleted_data,
            "common_cols": list(self.common_cols),
            "exclude_sheets": list(self.exclude_sheets),
            "default_keys": list(self.default_keys),
            "sheet_key_map": dict(self.sheet_key_map),
        }
        if self.max_workers is not None:
            document = {**document, "max_workers": self.max_workers}

        colors: ParameterColors = {}
        if self.colors.highlight_fill is not None:
            colors = {**colors, "highlight_fill": self.colors.highlight_fill}
        if self.colors.missing_sheet_tab is not None:
            colors = {**colors, "missing_sheet_tab": self.colors.missing_sheet_tab}
        if self.colors.new_sheet_tab is not None:
            colors = {**colors, "new_sheet_tab": self.colors.new_sheet_tab}
        if colors:
            document = {**document, "colors": colors}

        return document


class CompareResponse(BaseModel):
    output_path: str


def _api_log(message: str) -> None:
    log(message, None)


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/api/compare", response_model=CompareResponse)
def compare(request: CompareRequest) -> CompareResponse:
    try:
        output_path = run_comparison(
            request.to_parameter_document(),
            config_name=request.config_name,
            log_func=_api_log,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except InterruptedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (OSError, RuntimeError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        message = f"比对处理失败: {exc}"
        _api_log(message)
        raise HTTPException(status_code=500, detail=message) from exc

    return CompareResponse(output_path=output_path)
