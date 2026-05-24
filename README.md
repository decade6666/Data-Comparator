# 数据集对比（Dataset Comparator）

高效的数据集比对工具，专为 Excel (.xlsx/.xlsm) 文件的跨版本差异分析而设计，当前以 Linux Web/API 运行入口为主，复用多线程处理与可视化高亮标记能力，适合业务与研发协同使用。

## 主要特性
- 多工作表对比：逐表读取与处理，自动识别 新增/删除/更新 三类变更
- 表头与锚点行可配置：支持自定义表头行（SASFieldLabel）与锚点行（SASFieldName）
- 锚点（主键）灵活：可设置默认锚点列与“按表单指定锚点列”
- 列级增删检测：自动识别新增/删除列，并在表头高亮标注
- 单元格级高亮：仅对“更新”行的变更单元格进行高亮，新增/删除行整行高亮
- 大文件与多线程优化：可配置最大线程数，内置条件 GC 与内存峰值保护
- Excel 预处理：自动清理筛选器、可选择排除指定 Sheet，处理“受保护的来源”标记
- 配置管理：支持多配置方案（新建/删除/重命名/导入/导出），保存在用户 AppData 下
- 过程可停止：支持随时停止任务，保证 UI 或 API 调用可响应
- Web/API 入口：提供 FastAPI 服务，可在 Linux 环境通过外部 Web 访问触发比对
- 打包发布：提供 PyInstaller 配置，可生成单文件/单目录可执行程序

## 环境要求
- Linux（当前后续运行目标）
- Python 3.8 及以上
- 依赖（节选）：pandas、numpy、openpyxl、fastapi、pydantic、uvicorn、appdirs（可选：psutil/xlrd/xlsxwriter）

建议通过项目的 pyproject 安装：

```bash
# 开发模式安装（包含可选的性能增强）
pip install -e .[performance]
```

## 快速上手
- 启动 Web/API 服务：
  ```bash
  DATASET_COMPARATOR_WEB_HOST=0.0.0.0 DATASET_COMPARATOR_WEB_PORT=8000 dataset-comparator-web
  ```
  未安装脚本时可直接运行：
  ```bash
  python -m src.main_web
  ```

- 健康检查：
  ```bash
  curl http://127.0.0.1:8000/health
  ```

- 同步触发比对：
  ```bash
  curl -X POST http://127.0.0.1:8000/api/compare \
    -H 'Content-Type: application/json' \
    -d '{
      "old_file_path": "/data/old.xlsx",
      "new_file_path": "/data/new.xlsx",
      "output_directory": "/data/output"
    }'
  ```

- 旧桌面入口仍保留用于历史兼容：
  ```bash
  python -m src.main
  dataset-comparator-gui
  ```

提示：首次运行会在用户数据目录创建临时与配置子目录（例如 `PyDataCompare/temp/configs`）。

## 目录结构（摘要）
- `src/main_web.py`：Linux Web/API 程序入口
- `src/main.py`：历史 GUI 程序入口
- `src/gui/`：Tkinter 主窗口、参数管理、组件与对话框
- `src/frontend/`：Web API 与前端运行时辅助，如窗口资源与 GUI 更新队列
- `src/backend/application/`：应用编排服务，如路径校验与输出路径生成
- `src/backend/domain/`：比对领域逻辑、Excel 读取/渲染、高亮与停止控制
- `src/backend/infrastructure/`：配置、进度、临时目录与文件预处理等运行时适配
- `src/shared/`：跨层契约、资源路径与日志转发
- `scripts/`：构建与发布相关脚本

## 构建与发布
- 使用 PyInstaller（pyproject 已给出示例配置）：
  ```bash
  pyinstaller --noconfirm --clean \
    --name 数据集对比 \
    --icon src/assets/icons/app_icon.ico \
    --onefile --windowed \
    src/main.py
  ```
  或使用已有的 `scripts/app.spec` 进行构建。

- 安装可执行后，用户无需 Python 环境即可运行。

## 输出说明（概览）
- 结果文件为 Excel 工作簿：
  - 新增/删除列在表头以颜色标注
  - “更新情况（标记）”列置于第 1 列；新增/删除行整行高亮；更新行仅高亮变更单元格
  - 缺失/新增 Sheet 在标签色上区分（若构建流程设置）
- 输出目录由界面“输出目录”设置决定；如未设置，可能使用应用临时目录（AppData）

## 常见问题
- xls 旧格式：建议另存为 .xlsx 再处理；`xlrd` 不再支持 .xlsx
- 表头/锚点行不正确导致列名重复：请在“参数设置”中调整行号，避免 `SASFieldName` 重复
- 来自互联网的受保护 Excel 无法读取：程序会尝试移除 Zone.Identifier；若失败，请手动解除文件阻止
- 大文件内存压力：适当降低线程数、关闭非必要的应用、预留磁盘空间 