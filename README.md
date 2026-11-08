# HelpFlow

HelpFlow 是面向客户支持团队的工单管理系统，提供工单协作、站内通知、首次响应 SLA、带来源的回复建议和需人工确认的客服任务助手。

客服工单系统，支持普通用户、客服和管理员三种角色，提供工单创建、领取与分配、回复、状态流转、时间线、客服转交、内部备注、站内通知及首次响应 SLA。

后端使用 FastAPI、SQLAlchemy 和 MySQL，前端使用 Vue 3；Redis 可用于 SLA 到期调度。

## 环境要求

- Python 3.14+、uv。
- Node.js 22.12+ 或 24 LTS、npm。
- MySQL 8.0.16+。
- 本地前端端口 5173、后端端口 8000；数据库端口由连接串指定。

## 数据库与后端

在 MySQL 中创建一个应用专用库，并准备拥有该库读写和迁移 DDL 权限的账号。应用库可使用 `helpflow`：

```sql
CREATE DATABASE helpflow CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
```

从仓库根目录执行：

```powershell
cd backend
uv sync --locked
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

编辑 `backend/.env`：

| 变量 | 配置 |
| --- | --- |
| `HELPFLOW_DATABASE_URL` | `mysql+asyncmy://账号:URL编码后的密码@127.0.0.1:3306/helpflow?charset=utf8mb4` |
| `HELPFLOW_JWT_SECRET_KEY` | 本地生成的随机密钥，至少 32 字节 |
| `HELPFLOW_CORS_ORIGINS` | `["http://localhost:5173","http://127.0.0.1:5173"]` |
| `HELPFLOW_JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | 可选，默认 120 分钟 |

生成密钥并自行填入 `.env`：

```powershell
uv run python -c "import secrets; print(secrets.token_urlsafe(48))"
uv run alembic upgrade head
uv run alembic current
uv run alembic check
```

初始化管理员，密码通过隐藏输入设置；已有管理员不会被重置：

```powershell
uv run python -m scripts.init_admin --username 管理员 --email admin@example.com
```

启动后端：

```powershell
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

访问 `http://localhost:8000/api/v1/health`。健康检查只表示 HTTP 服务可用，数据库还应通过注册、登录或工单查询验证。MySQL 默认密码认证所需的 `cryptography` 已列入依赖。

## 前端

另开终端，从仓库根目录执行：

```powershell
cd frontend
npm ci --legacy-peer-deps
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
npm run dev
```

打开 [HelpFlow](http://localhost:5173)。`frontend/.env` 的 `VITE_API_BASE_URL` 默认 `http://localhost:8000/api/v1`。修改环境变量后重启服务；访问域名或端口变化时同步调整后端 CORS。

## SLA 扫描服务

另开终端运行独立扫描进程，用于首次响应提醒和超时升级：

```powershell
cd backend
uv run python -m scripts.scan_sla
```

Redis 为可选调度索引；不配置时由数据库补偿扫描处理。配置、规则及恢复操作见 [SLA 运行指南](docs/guides/sla.md)。

## 开发与质量保障

- [质量验证与持续集成](docs/guides/verification.md)：单元测试、隔离数据库测试及浏览器回归。
- [演示数据](docs/guides/demo-data.md)：可选的专用演示库与账号初始化。
- [OpenAPI](docs/api/helpflow.openapi.json) 与 [Postman 集合](docs/api/helpflow-workflow.postman_collection.json)：接口契约及请求示例，可导入 Apifox。

## 部署与运行约束

生产构建执行 `npm run build`，输出为 `frontend/dist`。静态服务器需将前端路由回退到 `index.html`，生产域名与预览端口需配置对应 CORS。


工单列表支持后端 `scope=mine|unassigned`、`assignee_id`、`unassigned` 筛选；`GET /api/v1/tickets/summary` 返回角色范围内的统计与最多五条最近工单。列表页码范围为 1～1,000,000，每页最多 100 条。回复及时间线默认返回最近 50 条、最多 100 条，使用 `before_id` 加载更早记录，页内按 ID 升序返回。

刷新时遇到网络异常或服务端故障，前端保留 Token 并展示重试入口；认证失效或账号禁用才清除会话。登录按 IP 和规范化邮箱限流，注册按 IP 限流，超限返回 429 与 `Retry-After`。默认限流窗口为 60 秒，登录每 IP 60 次、每账号 10 次，注册每 IP 10 次，可通过 `.env.example` 中的设置调整。当前应用限流在单进程内生效，多 worker 或多实例部署须在可信网关配置共享限流；代理来源地址应由可信代理配置提供。

`.github/workflows/ci.yml` 在每次 push / PR 中启动独立 MySQL，执行全部后端测试和前端测试、生产构建。请求响应包含 `X-Request-ID`，可与后端请求日志及数据库错误码关联，日志不输出 SQL 参数或连接凭据。

## 仓库目录

| 目录 | 内容 |
| --- | --- |
| `backend/app` | 应用路由、服务、数据访问与领域规则 |
| `backend/alembic` | 数据库版本迁移 |
| `backend/scripts` | 管理员初始化、SLA 运维及演示和测量工具 |
| `backend/tests` | 后端测试与测试辅助代码 |
| `backend/examples` | 独立学习示例 |
| `frontend/src` | 页面、组件、状态、路由及 API 客户端 |
| `frontend/tests`、`frontend/e2e` | 前端单元测试与浏览器回归 |
| `docs` | 功能指南、架构、接口及历史资料 |

完整分类见 [文档索引](docs/README.md)。日常使用从功能指南开始，运行结果以当前版本的实际验证为准。

## 智能助手与数据存储

- [回复助手](docs/guides/reply-assistant.md)：模型配置、知识导入、来源核对与草稿采用。
- [客服任务助手](docs/guides/task-assistant.md)：只读查询、提案审核、执行去重与中断恢复。
- 数据库使用 Alembic 管理，当前包含 `006_agent`。部署时执行 `uv run alembic upgrade head`，不要手工改写版本号。
- Agent 检查点使用持久化本地 SQLite；备份恢复必须同时覆盖 MySQL 与检查点文件。当前面向单机部署。
- 模型生成内容须经客服核对后发送；检索命中不代表资料足以支持回答。
