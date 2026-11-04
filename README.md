# HelpFlow

阶段13新增首次响应 SLA、超时升级通知、Redis ZSET 调度与数据库补偿，以及首页筛选和详情记录。升级需运行 `uv sync --locked`、`uv run alembic upgrade head`，并独立启动 `uv run python -m scripts.scan_sla`。配置和验证范围见 [阶段13运行与验证](docs/guides/stage13-sla.md)。

阶段13本地验证：100项后端测试通过，1项真实 Redis 测试因本机无服务跳过；24项前端测试、3项浏览器流程及生产构建通过。Redis 服务验证已接入 CI，远端结果待实际运行。

阶段12新增客服转交、内部备注和持久化站内通知。升级现有库需先运行 `uv run alembic upgrade head`，详情及验证状态见 [阶段12运行与验证](docs/guides/stage12-collaboration.md)。

阶段12本地验证：86项后端测试、21项前端测试、2项浏览器流程通过，生产构建成功；250张工单的聚合测量与 EXPLAIN 已留存。

客服工单系统，支持用户、客服和管理员三种角色，包含注册登录、工单创建、领取与分配、回复、状态流转、时间线和用户管理。

## 环境要求

- Python 3.14+、uv。
- Node.js 22.12+ 或 24 LTS、npm。
- MySQL 8.0.16+（本次联调使用 8.0.46）。
- 本地前端端口 5173、后端端口 8000；数据库端口由连接串指定。

## 数据库与后端

在 MySQL 中创建一个应用专用库，并准备拥有该库读写和迁移 DDL 权限的账号。普通运行可用 `helpflow`；需要演示初始化时使用 `helpflow_demo_local`：

```sql
CREATE DATABASE helpflow_demo_local CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
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
| `HELPFLOW_DATABASE_URL` | `mysql+asyncmy://账号:URL编码后的密码@127.0.0.1:3306/helpflow_demo_local?charset=utf8mb4` |
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

## 演示账号与数据

仅在 `helpflow_demo` 前缀的专用演示库运行：

```powershell
cd backend
uv run python -m scripts.seed_demo
```

脚本通过隐藏输入设置新建演示账号的共用密码，不重置既有密码，不覆盖既有工单。准备四个账号及待处理、处理中、已解决三种状态的示例工单：

| 角色 | 邮箱 |
| --- | --- |
| 普通用户 | `user@demo.example.com` |
| 客服一 | `agent1@demo.example.com` |
| 客服二 | `agent2@demo.example.com` |
| 管理员 | `admin@demo.example.com` |

也可用 `--password-env 环境变量名` 从进程环境读取密码，适用于自动化；不要把真实密码写入代码或提交到 Git。

完整演示：用户创建工单 → 客服领取 → 开始处理并回复 → 标记已解决 → 用户回复并确认关闭 → 管理员查看时间线、分配其它工单及管理用户。重新打开、撤销和并发领取冲突见 [工单指南](docs/guides/ticket-workflow.md)。

## 验证

```powershell
cd backend
uv run pytest -q
cd ../frontend
npm test
npm run build
```

默认跳过真实 MySQL 测试。运行全量测试时必须使用独立测试库，库名以 `helpflow_stage5_test` 开头，连接串通过进程变量 `HELPFLOW_TEST_DATABASE_URL` 提供。测试会迁移及回退测试库字段，不能指向业务库或演示库。详情见 [数据库指南](docs/guides/database.md)。

本次联调的环境、通过项和需求差异见 [阶段九验收记录](docs/guides/stage9-acceptance.md)。生产构建输出 `frontend/dist`，静态服务器需将前端路由回退到 `index.html`；生产环境和预览端口 4173 需要配置对应 CORS。

接口资料见 [OpenAPI](docs/api/helpflow.openapi.json) 与 [21 个业务和异常场景](docs/api/helpflow-workflow.postman_collection.json)，可导入 Apifox。2026-11-03 已通过 70 项后端真实 MySQL 测试、18 项前端测试及生产构建，完成核心三角色浏览器演示。

## 目录与文档

| 目录 | 内容 |
| --- | --- |
| `backend/app` | 路由、服务、数据访问、领域规则与基础设施 |
| `backend/alembic` | 数据库迁移 |
| `backend/scripts` | 管理员及演示数据初始化 |
| `backend/tests` | HTTP、认证、MySQL 与业务回归 |
| `frontend/src` | Vue 页面、组件、认证状态、路由及 API |
| `docs/requirements` | 需求确认和 PRD |
| `docs/architecture` | 前后端设计与文件职责 |
| `docs/guides` | 运行、功能及验收指南 |

更多说明：[前端](docs/guides/frontend.md)、[认证与安全](docs/guides/security.md)、[工单流程](docs/guides/ticket-workflow.md)、[文件职责](docs/architecture/file-map.md)。

## 代码审查修复

工单列表支持后端 `scope=mine|unassigned`、`assignee_id`、`unassigned` 筛选；`GET /api/v1/tickets/summary` 返回角色范围内的统计与最多五条最近工单。列表页码范围为 1～1,000,000，每页最多 100 条。回复及时间线默认返回最近 50 条、最多 100 条，使用 `before_id` 加载更早记录，页内按 ID 升序返回。

刷新时遇到网络异常或服务端故障，前端保留 Token 并展示重试入口；认证失效或账号禁用才清除会话。登录按 IP 和规范化邮箱限流，注册按 IP 限流，超限返回 429 与 `Retry-After`。默认限流窗口为 60 秒，登录每 IP 60 次、每账号 10 次，注册每 IP 10 次，可通过 `.env.example` 中的设置调整。当前应用限流在单进程内生效，多 worker 或多实例部署须在可信网关配置共享限流；代理来源地址应由可信代理配置提供。

`.github/workflows/ci.yml` 在每次 push / PR 中启动独立 MySQL，执行全部后端测试和前端测试、生产构建。请求响应包含 `X-Request-ID`，可与后端请求日志及数据库错误码关联，日志不输出 SQL 参数或连接凭据。

### 浏览器自动回归

先在 `backend` 进程环境设置独立的 `HELPFLOW_TEST_DATABASE_URL`，执行全量 `uv run pytest -q`（会迁移测试库），再准备测试账号并启动浏览器回归：

```powershell
# 在 backend 执行，沿用上面设置的独立测试库环境变量
uv run python -m tests.seed_browser
cd ../frontend
npx playwright install chromium
npm run test:e2e
```

测试使用专用端口 8011 和 5175，自动启动、关闭前后端，验证用户注册和创建工单、客服领取回复与解决、用户确认关闭、管理员查看，以及服务端临时 503 后保留会话并恢复。测试启动前校验测试库前缀，强制后端使用该测试库，不使用业务库连接。浏览器测试账号只在测试库创建，默认密码 `BrowserTest123`，可用 `E2E_PASSWORD` 覆盖；已有测试账号不重置密码。可选 `E2E_BROWSER_PATH` 指定本机 Chromium 浏览器路径。

本次修复本地验证：后端 79 项测试在隔离 MySQL 中通过、无跳过；前端 20 项单元测试和 1 项三角色浏览器测试通过，生产构建成功。组件改为按入口引入后，不再出现超过 500 kB 的构建分包提示。GitHub Actions 配置已加入同一浏览器流程，远端运行结果需以提交后的 Actions 为准。
