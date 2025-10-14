# nata (protask) 的 Copilot 使用指南

本文件为在此仓库（小型 Flask + SQLite 待办应用 `nata`）上工作的 AI 编码代理提供简明、可操作的说明。尽量保持改动最小、保留现有行为，并优先在测试与文档中保持清晰。

项目概览
- 单一文件的 Flask web 应用（`app.py`）与一个 HTML 模板（`templates/index.html`）。
- 使用仓库根目录下的 SQLite 数据库文件 `todos.db` 保存任务数据。
- 后端暴露简单的 JSON REST API（路径以 `/api/*`），并在根路径 `/` 提供 HTML UI。

重要文件（优先阅读）
- `app.py` — 主应用：路由、数据库初始化、工具函数（如获取本机 IP、生成二维码）、以及程序入口。
- `templates/index.html` — 前端页面与客户端 JS：从 `/api/tasks` 和 `/api/network-info` 获取数据并渲染。

架构要点（大局观）
- 单体：前端和后端同仓库同进程，前端直接请求后端 JSON 接口。
- 不依赖外部反向代理或应用容器：开发服务器在 `app.py` 中以 12345 端口启动。
- 数据库是单个 SQLite 文件 `todos.db`；`init_db()` 在启动时会创建表或进行轻量的 ALTER（例如添加 `due_date` 字段）。

开发与运行
- 本地运行：在项目根目录下执行 `python app.py`（需先安装依赖：`flask`, `qrcode` 等）。
- 启动时会尝试用 `lsof` 查找并终止占用 12345 端口的进程（通过 SIGTERM）；在 CI 或非类 Unix 平台请谨慎或禁用此行为。
- 目前无测试框架；可在 `tests/` 下添加 pytest 测试（推荐使用 Flask 的 `app.test_client()`）。

项目约定与模式
- 单文件服务优先：除非需要较大重构，否则在 `app.py` 做小而明确的改动。
- 数据库迁移：`init_db()` 采用非破坏性、幂等的 ALTER TABLE 以添加新列（例如 `due_date`），避免删除表或重建导致数据丢失。
- 时间戳与格式：`created_at` 使用 SQLite 的 CURRENT_TIMESTAMP；前端将 datetime-local 转换为 `YYYY-MM-DD HH:MM:SS` 存入 `due_date` 字段。
- 布尔值处理：`completed` 存为 BOOLEAN （SQLite 实际为 0/1），代码中有时以真值/假值判断，请在更新时保持 0/1 或 True/False 的一致性。

集成点与外部依赖
- Python 包：`flask`, `qrcode`（其余为标准库：`sqlite3`, `socket`, `subprocess`, `signal`）。
- 系统依赖：`lsof`（用于查找占端口进程）。在没有 `lsof` 的环境下 `kill_port_process` 可能静默失败。
- 网络检测：`get_local_ip()` 通过 UDP 连接到 8.8.8.8 来推断 LAN IP；在隔离网络/无外网环境下可能返回 `127.0.0.1`。

可复用的实现模式（修改时参考）
- 新增 API 路由的样式：使用 `sqlite3.connect(DB_NAME)` -> cursor 执行 -> commit -> close；返回 JSON，并在创建时使用 201，删除/更新成功返回 204（无内容）。
- 查询排序：获取任务时按 `due_date`（NULL 值放后），再 `due_date ASC`，最后 `created_at DESC`，如要改动请保留此用户可见排序语义。

PR/变更前的安全检查
- 确认 `init_db()` 不会无意中删除或重建 `tasks` 表。
- 在 CI 或测试环境中建议跳过或模拟 `kill_port_process()`（例如通过 `SKIP_PORT_KILL=1` 环境变量控制），以避免不可预期的进程终止。
- 保持 `app.run(..., debug=False)`；不要在主分支中启用 debug 热重载。

应避免的改动
- 不要假设有多个 worker 或并发写入 SQLite；避免引入需要并发控制的设计。
- 不要移除 `/api/network-info` 或二维码功能，`templates/index.html` 依赖这些接口用于移动访问体验。

测试与 CI 建议
- 增加 pytest：使用 Flask 的 `app.test_client()` 启动测试客户端，覆盖 `/api/tasks` 的增删改查并验证 `todos.db` 的变化。
- 在 CI 中避免实际运行 `kill_port_process()`；可以在 `app.py` 中添加对 `SKIP_PORT_KILL` 的检测并在 CI 环境下跳过。

重构建议
- 优先提取小的工具函数并保持现有路由签名不变。
- 若将数据库逻辑抽离到模块中，请保持 `DB_NAME` 常量和 `init_db()` 的语义不变，以兼容现有脚本/测试。

未决问题或需询问维护者的点
- 如果不确定目标运行环境是否提供 `lsof` 或是否允许在启动时终止进程，请询问维护者在 CI/部署环境中的期望行为。

如需我继续：我可以把该文件翻译成更详细的中文开发文档、添加基本 pytest 测试并在本地运行，或者在 `app.py` 中添加 `SKIP_PORT_KILL` 支持。请告知你想下一步我做什么。