import json
import os
from typing import Callable, Dict, List, Optional, cast

from ...shared.contracts import LogFunc, ParameterDocument
from ...shared.log_utils import log

CONFIGS_SUBDIR = "configs"


class JsonParameterRepository:
    def __init__(
        self,
        base_dir_getter: Optional[Callable[[], str]] = None,
        log_func: Optional[LogFunc] = None,
    ) -> None:
        self._base_dir_getter = base_dir_getter
        self._log_func = log_func

    def get_configs_dir(self) -> str:
        base_dir_getter = self._base_dir_getter
        if base_dir_getter is None:
            from .file_runtime import get_app_temp_dir

            base_dir_getter = get_app_temp_dir
        return os.path.join(base_dir_getter(), CONFIGS_SUBDIR)

    def get_config_path(self, config_name: str) -> str:
        return os.path.join(self.get_configs_dir(), f"{config_name}.json")

    def ensure_config_directory(self) -> None:
        configs_dir = self.get_configs_dir()
        os.makedirs(configs_dir, exist_ok=True)
        log(f"配置目录已确保存在: {configs_dir}", self._log_func)

    def load_document(self, config_name: str) -> Optional[ParameterDocument]:
        config_path = self.get_config_path(config_name)
        if not os.path.exists(config_path):
            return None
        with open(config_path, "r", encoding="utf-8") as file:
            document = json.load(file)
        if not isinstance(document, dict):
            raise ValueError("配置文件格式无效")
        return cast(ParameterDocument, document)

    def list_configurations(self) -> List[str]:
        config_dir = self.get_configs_dir()
        if not os.path.exists(config_dir):
            return []
        configs = []
        for filename in os.listdir(config_dir):
            if filename.endswith(".json"):
                configs.append(os.path.splitext(filename)[0])
        return sorted(configs)

    def save_document(self, config_name: str, document: ParameterDocument) -> None:
        config_path = self.get_config_path(config_name)
        with open(config_path, "w", encoding="utf-8") as file:
            json.dump(document, file, ensure_ascii=False, indent=4)

    def delete_document(self, config_name: str) -> bool:
        config_path = self.get_config_path(config_name)
        if not os.path.exists(config_path):
            return False
        os.remove(config_path)
        return True

    def ensure_builtin_templates(self, templates: Dict[str, ParameterDocument]) -> None:
        self.ensure_config_directory()
        for name, params in templates.items():
            config_path = self.get_config_path(name)
            if os.path.exists(config_path):
                continue
            self.save_document(name, params)
            log(f"已创建内置模板: {name}", self._log_func)
