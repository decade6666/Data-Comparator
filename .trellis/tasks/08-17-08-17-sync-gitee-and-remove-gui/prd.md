# 同步 gitee 比对配置功能并清理桌面入口

## 背景

上游 gitee（py_DataCompare）新增三个比对配置功能，但基于旧目录结构；本项目已重构为前后端分层 + Web API，两边 git 历史不相交，需按新分层手工移植。

## 需求

1. 移植 `include_sheets` / `ignore_cols` / `sheet_ignore_cols` / `sheet_order` 四个配置项（语义与上游一致）：
   - `include_sheets`：非空时只比对/输出列表内表单
   - `ignore_cols` / `sheet_ignore_cols`：字段照常输出但不参与差异判定（不高亮/不影响行标记/不计入汇总），按表单整体替换全局
   - `sheet_order`：输出表单顺序，优先级 sheet_order > include_sheets > 源文件顺序
2. 清理历史遗留：删除 src/gui、run.py、src/main.py、Windows 打包脚本 scripts/、失效前端/共享辅助模块，pyproject 去除 ttkbootstrap/pywin32/GUI 入口，版本 1.7.0。
3. 更新 README 与全部模块文档为纯 Web/API 定位。

## 验收

- 新增集成测试（tests/test_compare_scope_and_order.py）与 Web API 字段测试通过
- 全量 pytest 通过，覆盖率不低于基线
- 端到端：pip install -e . → 启动服务 → /health 与 /api/compare 全参数请求 → 输出表单顺序与忽略列行为正确
- grep 无 src/gui、tkinter、ttkbootstrap、pywin32、run.py、src/main.py 残留（历史 changelog 除外）
