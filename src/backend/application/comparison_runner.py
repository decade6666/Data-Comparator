import datetime
import os
from typing import Callable, Optional, Protocol

from ...shared.contracts import LogFunc, ParameterColors, ParameterDocument
from .processing_service import build_output_path, validate_processing_paths


class ComparisonConfig(Protocol):
    def update_from_parameters(
        self, parameters: ParameterDocument, colors: ParameterColors
    ) -> None: ...


ProcessFunc = Callable[..., str]
ConfigFactory = Callable[[], ComparisonConfig]


def _noop_log(_message: str) -> None:
    return None


def _default_config_factory() -> ComparisonConfig:
    from ..infrastructure.config_manager import ConfigManager

    return ConfigManager()


def _default_process_func() -> ProcessFunc:
    from ..domain.data_comparison import process_edc_multithreaded

    return process_edc_multithreaded


def run_comparison(
    parameters: ParameterDocument,
    config_name: str = "web",
    log_func: Optional[LogFunc] = None,
    progress_func: Optional[Callable[[str, Optional[int]], None]] = None,
    stop_flag=None,
    process_func: Optional[ProcessFunc] = None,
    config_factory: ConfigFactory = _default_config_factory,
    path_exists: Callable[[str], bool] = os.path.exists,
    make_dirs: Callable[..., None] = os.makedirs,
    now: Optional[datetime.datetime] = None,
) -> str:
    processing_paths = validate_processing_paths(
        parameters,
        path_exists=path_exists,
        make_dirs=make_dirs,
    )
    config = config_factory()
    colors: ParameterColors = parameters.get("colors", {})
    config.update_from_parameters(parameters, colors)
    output_path = build_output_path(config_name, processing_paths.output_dir, now=now)
    active_log_func = log_func or _noop_log
    active_process_func = process_func or _default_process_func()

    return active_process_func(
        processing_paths.old_path,
        processing_paths.new_path,
        output_path,
        active_log_func,
        config=config,
        progress_func=progress_func,
        stop_flag=stop_flag,
    )
