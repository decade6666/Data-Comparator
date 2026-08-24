# Nginx 子路径反代支持

## Goal

前端运行时推导 API 挂载前缀 + 相对路径构建产物，支持任意子路径 nginx 反向代理；postbuild 回归检查；README 反代示例

## Requirements

- 构建产物使用相对资源路径，未配置 `VITE_BASE_PATH` 时 asset 引用为 `./assets/...`
- API 前缀运行时推导：优先构建期 `VITE_BASE_PATH`，否则由模块 URL 回溯挂载根
- 保留既有 `VITE_BASE_PATH` 显式配置与根路径部署行为
- README 提供 nginx 子路径反代示例，说明无需 `sub_filter` 等改写规则
- postbuild 校验产物 asset 路径格式，防止 base 回归

## Acceptance Criteria

- [x] `npm run build` 产物 `dist/index.html` 引用 `./assets/...`，postbuild 检查通过
- [x] 子路径反代下前端请求 `/dataset/api/...`（`proxy_pass` 剥离前缀即可）
- [x] 根路径部署行为不变
- [x] vitest 全量 20 项通过（含新增 5 项 useApi 测试）
- [x] README nginx 子路径反代示例已添加

## Notes

- 轻量任务，PRD-only；实现与验证已完成（详见 changelog 2026-08-20 后工作区改动）。
