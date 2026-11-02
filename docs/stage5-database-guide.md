# HelpFlow 阶段五异步数据库实践指南

本文保留阶段五学习记录。当前代码已进入阶段六，注册参数、认证要求和工单身份字段请以 [阶段六指南](stage6-security-guide.md) 为准。

阶段五把现有注册、用户查询、工单创建与修改、列表筛选分页、状态更新、回复接口改为 MySQL 持久化。阶段四的 `helpflow_stage4` 仍是独立 SQL 练习库；本阶段应用使用新库 `helpflow`。原阶段一、二练习仍可以独立运行。

## 1 准备与启动

进入后端目录并同步依赖：

```powershell
cd D:\vscode\HelpFlow\backend
uv sync
```

使用 MySQL 8.0.16+（本次在 8.0.46 验证），登录自己的本地数据库后执行：

```sql
CREATE DATABASE helpflow CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
```

复制配置示例，只在未创建 `.env` 时执行复制；已有配置直接补充数据库变量：

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

编辑 `backend/.env`，将 `HELPFLOW_DATABASE_URL` 中的账号、`CHANGE_ME`、端口替换为自己的本地连接信息。账号需要该库的读写和迁移 DDL 权限，脚本不会替你创建账号。密码含 `@`、`:`、`/`、`%` 等字符时，先进行 URL 百分号编码。真实 `.env` 不进入 Git。也可通过进程环境变量覆盖配置。

```dotenv
HELPFLOW_DATABASE_URL=mysql+asyncmy://helpflow:CHANGE_ME@127.0.0.1:3306/helpflow?charset=utf8mb4
```

执行迁移、检查版本与启动：

```powershell
uv run alembic upgrade head
uv run alembic current
uv run alembic check
uv run uvicorn app.main:app --reload
```

应用不会自动建库、建表或执行迁移。健康检查仅表示 HTTP 服务运行，不检查 MySQL 是否可访问。业务请求报 500 时先核对数据库是否启动、账号和端口、库是否存在、是否已迁移到 head。

## 2 从内存到数据库的调用链

```mermaid
flowchart LR
    request["HTTP 请求"] --> router["异步 Router 和 Pydantic Schema"]
    router --> service["异步 Service：业务规则和写事务"]
    service --> repo["Repository：SQL 查询和 flush"]
    repo --> session["AsyncSession"]
    session --> driver["SQLAlchemy 和 asyncmy"]
    driver --> mysql[("MySQL helpflow")]
```

- `app/db/base.py`：ORM 基类、UTC 日期转换。
- `app/db/session.py`：引擎和连接池、会话工厂、请求级 Session 依赖。
- `app/models/__init__.py`：五张表的 ORM 模型、约束、索引和关联。
- `app/repositories/`：数据库查询、分页和写入暂存，不负责 commit。
- `app/services/`：原有业务规则的异步实现，写操作通过 `session.begin()` 提交或回滚。
- `app/dependencies.py`：将同一次请求的 Session 交给 Service。

一个请求一个 Session。Service 写入成功后提交，才返回成功响应；事务中的异常会回滚。依赖退出时对剩余读事务兜底回滚，并关闭 Session、归还连接。应用退出时释放引擎。不要将同一个 Session 传给多个 `gather()` 并发任务。

`flush()` 把待写入变更发送至数据库并取得 ID，尚未提交；本次会话即使已经 flush，发生异常仍可回滚。`expire_on_commit=False` 让响应序列化能够直接读取提交后的已加载字段，避免额外隐式查询。

ORM Model 表示数据库记录；Pydantic Schema 表示 HTTP 输入和输出；早期 dataclass 表示独立内存练习对象。它们职责不同。关系默认 `lazy="raise"`，防止读取属性时意外触发数据库 IO；回复查询通过 `selectinload(Comment.author)` 批量加载作者，不逐条查人。

## 3 接口兼容与本阶段边界

原阶段三路径、请求与响应结构继续有效，包括 `/users` 兼容创建入口。先注册用户，再用返回的真实 ID 创建工单，不要假定用户和工单 ID 永远从 1 开始。

```json
{"username":"学习用户","email":"learner@example.com"}
```

将其发送至 `POST /api/v1/auth/register`；随后把返回的用户 ID 填入：

```json
{"title":"无法登录","description":"输入账号后提示错误","creator_id":1,"priority":"high"}
```

发送至 `POST /api/v1/tickets`，再查询工单详情、修改标题、筛选列表、添加回复与修改状态。数据库的 `ticket_no` 用 UUID 生成，分类暂为 `other`，本阶段不扩展响应字段。状态规则继续沿用早期版本，完整角色和领取流程在阶段六、七完善。

注册仍不接收密码，固定创建普通用户，数据库存入 `!stage5-no-login` 无效占位值。没有登录、JWT、数据归属鉴权；`creator_id`、`author_id` 仍由学习客户端提供。这个版本用于本地学习，不能视为已经完成权限的业务系统。活动和用户管理日志目前完成表与关系映射，现有写操作尚不写这些日志，阶段七再实现完整业务审计。

邮箱写入前统一去空白、转小写；预检查与数据库唯一约束共同防止重复，并发冲突也返回原 409。其他 SQLAlchemy 错误返回脱敏 500，数据库错误日志只记录异常类型，不打印 SQL、参数或连接串。配置使用 `SecretStr`，日志中不要自行打印解密后的 URL。

分页和 count 在 SQL 中使用同一组筛选条件。关键词中的 `%`、`_` 被转义为普通字符，数字还可以精确匹配 ID；绑定参数避免拼接 SQL。排序仍按 ID，保持旧接口行为。数据库默认排序规则对重音字符的等价判断可能与 Python `casefold()` 不完全相同。数据库 DATETIME 保存 UTC，ORM 读取恢复时区，响应仍为 UTC ISO 时间。

## 4 Alembic 升级与回退

两版迁移均自包含，不读取当前 ORM 或阶段四脚本生成历史结构：

| 版本 | 作用 |
| --- | --- |
| `001_five_tables` | 建立五表、约束与索引，工单暂不包含 updated_at |
| `002_ticket_updated_at` | 增加工单 updated_at，最终结构与阶段四一致 |

在自己的独立练习库中停止应用后，可以验证：

```powershell
uv run alembic downgrade 001_five_tables
uv run alembic upgrade head
uv run alembic history
uv run alembic check
```

回退会删除 `tickets.updated_at` 及其值，重新升级只能补齐新默认值；其他记录保留。不要在有业务数据的数据库随意回退。不要通过删表重建代替迁移，也不要把阶段四手工建表库直接 `stamp head`。本阶段从新库开始，不自动迁移旧内存或阶段四示例数据。

后续修改 Model 后生成迁移：

```powershell
uv run alembic revision --autogenerate -m "describe_schema_change"
```

检查生成的 upgrade / downgrade 是否符合预期，再升级和验证。自动生成及 `alembic check` 不保证发现所有 CHECK 或默认值差异，必须人工核对。基线迁移使用冻结的 MySQL DDL，字段增量迁移使用 Alembic 操作；不要修改已应用的历史迁移。

## 5 验证数据保留

1. 用 Apifox 注册一个未使用过的邮箱并创建工单，记录返回 ID。
2. 完全关闭后端进程，再按原连接配置重新启动。
3. 查询该用户和工单，确认仍然存在。
4. 测试重复邮箱、错误创建人、非法状态和已关闭工单回复的错误响应。

自动化验证：

```powershell
uv run pytest -q
```

未提供测试库时，真实数据库的三个集成测试会跳过，其余回归仍执行。数据库集成测试必须指定独立空库，库名以 `helpflow_stage5_test` 开头，勿使用日常业务库：

```sql
CREATE DATABASE helpflow_stage5_test_local CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
```

```powershell
# 用你自己的本地测试账号连接串替换占位值
$env:HELPFLOW_TEST_DATABASE_URL='mysql+asyncmy://helpflow:CHANGE_ME@127.0.0.1:3306/helpflow_stage5_test_local?charset=utf8mb4'
uv run pytest -q
Remove-Item Env:HELPFLOW_TEST_DATABASE_URL
```

集成测试会迁移该测试库、插入测试数据，并执行 updated_at 的回退与恢复；数据留在测试库中，不自动删库。普通 HTTP 回归通过测试专用异步适配器复用早期内存服务；真实 MySQL 测试独立验证完整持久化链路。

2026-11-02 在隔离 MySQL 8.0.46 实例中，全套 **51 个测试通过**，覆盖现有接口、空库迁移、字段回退与重新升级、元数据差异检查、应用重建后的读取、flush 后提交失败回滚、并发注册的 Session 隔离及连接归还。临时实例已关闭。现有 Starlette/httpx 弃用提示不影响本次验证。

参考：[SQLAlchemy 异步文档](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)、[Alembic 异步迁移](https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic)。
