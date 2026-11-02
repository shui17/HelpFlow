# HelpFlow

客服工单系统，支持账号认证、用户管理、工单领取与分配、状态流转、回复和活动时间线。

## 仓库结构

| 目录 | 内容 |
| --- | --- |
| backend/app | 路由、业务服务、数据访问、领域规则与基础设施 |
| backend/alembic | 数据库结构迁移 |
| backend/scripts | 管理员初始化等管理脚本 |
| backend/examples | 内存工单流程与异步 I/O 示例 |
| backend/sql | 独立数据库脚本 |
| backend/tests | HTTP、校验、数据库、安全与工单测试 |
| docs/requirements | 产品需求与需求确认 |
| docs/architecture | 前后端设计、文件职责及历史设计 |
| docs/guides | 按功能组织的操作指南 |
| frontend | 前端预留目录 |

## 开发与验证

进入 `backend`，执行 `uv sync`，按 [数据库指南](docs/guides/database.md) 配置数据库并执行迁移，按 [认证指南](docs/guides/security.md) 设置 JWT 密钥及初始化管理员，然后启动：

```powershell
uv run uvicorn app.main:app --reload
```

运行测试和独立示例：

```powershell
uv run pytest -q
uv run python -m examples.ticket_workflow
uv run python -m examples.async_io
```

真实 MySQL 测试需要显式配置独立测试库，详见数据库指南。接口操作见 [工单指南](docs/guides/ticket-workflow.md)，完整导航见 [文件职责与依赖](docs/architecture/file-map.md)。
