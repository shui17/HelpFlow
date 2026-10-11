# HelpFlow 后端设计文档

## 1 文档信息


| 项目     | 内容                                                                 |
| ---------- | ---------------------------------------------------------------------- |
| 项目名称 | HelpFlow 客服工单管理系统                                            |
| 文档类型 | 后端详细设计                                                         |
| 文档版本 | V1.0                                                                 |
| 编写日期 | 2026-10-04                                                           |
| 上游文档 | `docs/requirements-confirmation.md`、`docs/prd.md`                   |
| 后端技术 | Python、FastAPI、Pydantic、SQLAlchemy Async、asyncmy、Alembic、MySQL |

## 2 文档目的

本文档用于指导 HelpFlow 后端框架、数据库和 API 实现，明确后端目录、分层职责、数据表、Schema、接口、权限、事务、并发、异常、迁移和 Apifox 验证要求。

本文档不包含前端组件实现和学习路线。前端实际展示和交互以 `frontend-design.md` 为准，业务范围以需求确认书和 PRD 为准。

## 3 后端目标

- 提供版本化的 JSON API。
- 使用 MySQL 持久化所有业务数据。
- 使用异步 SQLAlchemy 访问数据库。
- 使用 JWT 识别当前用户。
- 在后端执行角色、数据归属和状态权限校验。
- 使用事务保证业务数据与操作记录一致。
- 使用数据库条件更新解决客服并发领取问题。
- 返回统一、稳定、可被前端和 Apifox 使用的响应。

## 4 后端架构

```text
HTTP Request
    ↓
API Router
    ├── 读取路径、查询参数和请求体
    ├── 注入当前用户和数据库 Session
    └── 调用 Service
    ↓
Service
    ├── 权限和状态校验
    ├── 组织业务流程
    ├── 管理事务
    └── 调用 Repository
    ↓
Repository
    ├── 组合 SQLAlchemy 查询
    ├── 新增、更新和统计
    └── 不决定业务权限
    ↓
SQLAlchemy Model
    ↓
MySQL 8
```

### 4.1 分层约束

- Router 不直接编写复杂 SQL。
- Router 不自行提交多个有关联的事务。
- Service 不拼接 HTTP Response 对象。
- Repository 不返回面向用户的中文错误信息。
- Model 不作为外部请求 Schema 直接使用。
- Schema 不包含数据库 Session 和业务操作。
- 跨模块业务规则集中在 Service，避免散落在多个路由。

## 5 技术与依赖

### 5.1 运行依赖

```text
fastapi
uvicorn
sqlalchemy
asyncmy
alembic
pydantic
pydantic-settings
pyjwt
pwdlib[argon2]
email-validator
python-multipart
```

具体版本在创建 `requirements.txt` 时固定。当前不引入 Redis、Celery、pytest、消息队列和额外 ORM。

### 5.2 Python 约定

- Python 3.11 或更高版本。
- 异步函数使用 `async def`。
- 数据库操作统一使用 `AsyncSession`。
- 不在异步路由中调用阻塞型数据库驱动。
- 文件和函数使用清晰英文命名。
- 枚举值使用英文小写字符串。

## 6 后端目录结构

```text
backend/
├── app/
│   ├── api/
│   │   ├── dependencies/
│   │   │   ├── auth.py
│   │   │   └── database.py
│   │   └── v1/
│   │       ├── router.py
│   │       ├── auth.py
│   │       ├── tickets.py
│   │       ├── users.py
│   │       ├── dashboard.py
│   │       └── health.py
│   ├── core/
│   │   ├── config.py
│   │   ├── security.py
│   │   ├── exceptions.py
│   │   ├── exception_handlers.py
│   │   ├── responses.py
│   │   └── logging.py
│   ├── db/
│   │   ├── base.py
│   │   ├── session.py
│   │   └── init_admin.py
│   ├── models/
│   │   ├── user.py
│   │   ├── ticket.py
│   │   ├── ticket_comment.py
│   │   ├── ticket_activity_log.py
│   │   └── user_admin_log.py
│   ├── repositories/
│   │   ├── user_repository.py
│   │   ├── ticket_repository.py
│   │   ├── comment_repository.py
│   │   ├── activity_repository.py
│   │   └── user_admin_log_repository.py
│   ├── schemas/
│   │   ├── common.py
│   │   ├── auth.py
│   │   ├── user.py
│   │   ├── ticket.py
│   │   ├── comment.py
│   │   ├── activity.py
│   │   └── dashboard.py
│   ├── services/
│   │   ├── auth_service.py
│   │   ├── ticket_service.py
│   │   ├── user_service.py
│   │   └── dashboard_service.py
│   ├── enums.py
│   └── main.py
├── alembic/
│   ├── versions/
│   └── env.py
├── scripts/
│   └── init_admin.py
├── .env.example
├── alembic.ini
└── requirements.txt
```

### 6.1 文件边界

- `api/v1/*.py`：HTTP 接口和依赖声明。
- `core/config.py`：读取环境变量。
- `core/security.py`：密码和 JWT。
- `core/exceptions.py`：业务异常类型与错误码。
- `core/exception_handlers.py`：异常到统一响应的转换。
- `core/responses.py`：统一成功和分页响应结构。
- `db/session.py`：异步 Engine、Session 工厂和请求依赖。
- `models`：五张数据库表。
- `repositories`：可复用数据库操作。
- `services`：业务规则、权限、事务和并发。
- `schemas`：请求、响应和分页结构。
- `scripts/init_admin.py`：初始化或更新本地管理员。

## 7 配置与环境变量

后端 `.env.example` 建议包含：

```text
APP_NAME=HelpFlow
APP_ENV=development
DEBUG=true
API_V1_PREFIX=/api/v1
DATABASE_URL=mysql+asyncmy://helpflow_user:change_me@localhost:3306/helpflow
JWT_SECRET_KEY=replace_with_a_long_random_value
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=120
ALLOWED_ORIGINS=http://localhost:5173
```

规则：

- 所有配置通过 `pydantic-settings` 集中读取。
- 应用启动时检查必需配置。
- 真实 `.env` 不写入文档内容。
- JWT 密钥不得提供弱默认值。
- `ALLOWED_ORIGINS` 解析为明确来源列表。
- 数据库密码和 JWT 不写入日志。

## 8 数据库统一约定

- 数据库使用 MySQL 8，字符集使用 `utf8mb4`。
- 表名和字段名使用小写下划线。
- 主键使用自增整数，Python 和数据库映射保持一致。
- 所有外键建立索引。
- 业务时间保存为 UTC，前端负责格式化显示。
- 时间字段至少包含 `created_at`；可修改主表还包含 `updated_at`。
- 不对用户和工单做物理删除。
- 枚举在 Python 中使用 `str, Enum`，数据库保存稳定英文字符串。
- 数据库约束与 Service 校验同时存在，不能只依赖前端。

## 9 枚举设计

### 9.1 `UserRole`

```text
user
agent
admin
```

### 9.2 `TicketStatus`

```text
open
in_progress
resolved
closed
```

### 9.3 `TicketCategory`

```text
account
product
payment
technical
other
```

### 9.4 `TicketPriority`

```text
low
normal
high
urgent
```

### 9.5 `TicketActivityType`

```text
created
updated
cancelled
claimed
assigned
reassigned
status_changed
reopened
closed
```

### 9.6 `UserAdminAction`

```text
role_changed
account_enabled
account_disabled
```

## 10 数据表设计

字段类型是设计约定，具体 SQLAlchemy 声明在实现时保持等价。

### 10.1 `users`


| 字段            | 类型         | 约束             | 说明                       |
| ----------------- | -------------- | ------------------ | ---------------------------- |
| `id`            | BIGINT       | 主键、自增       | 用户 ID                    |
| `username`      | VARCHAR(30)  | 非空             | 显示名称                   |
| `email`         | VARCHAR(255) | 非空、唯一       | 登录邮箱，保存规范化小写值 |
| `password_hash` | VARCHAR(255) | 非空             | Argon2 哈希                |
| `role`          | VARCHAR(20)  | 非空、默认`user` | 用户角色                   |
| `is_active`     | BOOLEAN      | 非空、默认 true  | 是否启用                   |
| `created_at`    | DATETIME     | 非空             | 创建时间                   |
| `updated_at`    | DATETIME     | 非空             | 更新时间                   |

索引：

- 唯一索引：`email`
- 普通索引：`role`
- 普通索引：`is_active`

规则：

- 邮箱写入前去除首尾空格并转小写。
- 用户名可以重复，邮箱不能重复。
- 公开注册强制写入 `role=user` 和 `is_active=true`。

### 10.2 `tickets`


| 字段          | 类型         | 约束               | 说明           |
| --------------- | -------------- | -------------------- | ---------------- |
| `id`          | BIGINT       | 主键、自增         | 内部 ID        |
| `ticket_no`   | VARCHAR(32)  | 非空、唯一         | 对外工单编号   |
| `title`       | VARCHAR(200) | 非空               | 工单标题       |
| `description` | TEXT         | 非空               | 问题描述       |
| `category`    | VARCHAR(20)  | 非空               | 问题分类       |
| `priority`    | VARCHAR(20)  | 非空、默认`normal` | 优先级         |
| `status`      | VARCHAR(20)  | 非空、默认`open`   | 当前状态       |
| `creator_id`  | BIGINT       | 外键、非空         | 创建人         |
| `assignee_id` | BIGINT       | 外键、可空         | 当前客服       |
| `assigned_at` | DATETIME     | 可空               | 最近分配时间   |
| `closed_at`   | DATETIME     | 可空               | 关闭或撤销时间 |
| `created_at`  | DATETIME     | 非空               | 创建时间       |
| `updated_at`  | DATETIME     | 非空               | 更新时间       |

索引：

- 唯一索引：`ticket_no`
- 索引：`creator_id`
- 索引：`assignee_id`
- 索引：`status`
- 索引：`priority`
- 索引：`category`
- 索引：`created_at`
- 组合索引：`creator_id, created_at`
- 组合索引：`assignee_id, status, created_at`

规则：

- 工单编号由后端生成，不接受客户端传入。
- 工单编号生成算法必须唯一；具体实现建议采用日期前缀加随机或唯一序列。
- 新工单 `status=open`、`assignee_id=null`。
- `closed` 时写入 `closed_at`。
- 重新打开时清空 `closed_at`。

### 10.3 `ticket_comments`


| 字段         | 类型     | 约束       | 说明       |
| -------------- | ---------- | ------------ | ------------ |
| `id`         | BIGINT   | 主键、自增 | 回复 ID    |
| `ticket_id`  | BIGINT   | 外键、非空 | 所属工单   |
| `author_id`  | BIGINT   | 外键、非空 | 回复人     |
| `content`    | TEXT     | 非空       | 纯文本回复 |
| `created_at` | DATETIME | 非空       | 回复时间   |

索引：

- 组合索引：`ticket_id, created_at`
- 索引：`author_id`

规则：

- 内容去除首尾空格后不能为空。
- 内容最大长度由 Schema 限制为 2000 个字符。
- 回复按 `created_at` 升序返回。

### 10.4 `ticket_activity_logs`


| 字段              | 类型         | 约束       | 说明         |
| ------------------- | -------------- | ------------ | -------------- |
| `id`              | BIGINT       | 主键、自增 | 活动 ID      |
| `ticket_id`       | BIGINT       | 外键、非空 | 所属工单     |
| `action`          | VARCHAR(30)  | 非空       | 操作类型     |
| `operator_id`     | BIGINT       | 外键、非空 | 操作人       |
| `old_status`      | VARCHAR(20)  | 可空       | 原状态       |
| `new_status`      | VARCHAR(20)  | 可空       | 新状态       |
| `old_assignee_id` | BIGINT       | 外键、可空 | 原负责人     |
| `new_assignee_id` | BIGINT       | 外键、可空 | 新负责人     |
| `description`     | VARCHAR(500) | 可空       | 人类可读说明 |
| `created_at`      | DATETIME     | 非空       | 操作时间     |

索引：

- 组合索引：`ticket_id, created_at`
- 索引：`operator_id`
- 索引：`action`

日志表只新增，不提供普通更新和删除接口。

### 10.5 `user_admin_logs`


| 字段             | 类型        | 约束       | 说明       |
| ------------------ | ------------- | ------------ | ------------ |
| `id`             | BIGINT      | 主键、自增 | 日志 ID    |
| `target_user_id` | BIGINT      | 外键、非空 | 被操作用户 |
| `operator_id`    | BIGINT      | 外键、非空 | 管理员     |
| `action`         | VARCHAR(30) | 非空       | 管理操作   |
| `old_role`       | VARCHAR(20) | 可空       | 原角色     |
| `new_role`       | VARCHAR(20) | 可空       | 新角色     |
| `old_is_active`  | BOOLEAN     | 可空       | 原启用状态 |
| `new_is_active`  | BOOLEAN     | 可空       | 新启用状态 |
| `created_at`     | DATETIME    | 非空       | 操作时间   |

索引：

- 组合索引：`target_user_id, created_at`
- 索引：`operator_id`
- 索引：`action`

日志表只新增，不提供普通更新和删除接口。

## 11 数据库关系与加载策略

```text
User.created_tickets       用户创建的工单
User.assigned_tickets      客服负责的工单
Ticket.creator             工单创建人
Ticket.assignee            当前负责人，可空
Ticket.comments            工单回复
Ticket.activities          工单时间线
Comment.author             回复人
Activity.operator          操作人
```

列表接口只加载列表需要的创建人和负责人摘要，不加载全部回复和时间线。详情接口分别查询工单、回复和时间线，避免列表产生大量无用关联数据。

## 12 Schema 设计

### 12.1 通用响应

- `ApiResponse[T]`：`code`、`message`、`data`。
- `PageData[T]`：`items`、`page`、`page_size`、`total`。
- 所有响应 Schema 启用从 ORM 对象读取数据的配置。

### 12.2 认证 Schema

`RegisterRequest`：

- `username`：2～30 字符
- `email`：有效邮箱
- `password`：8～64 字符，至少一个字母和数字
- `password_confirm`：必须与密码一致

`LoginRequest`：

- `email`
- `password`

`TokenData`：

- `access_token`
- `token_type`，固定为 `bearer`
- `expires_in`

`ChangePasswordRequest`：

- `current_password`
- `new_password`
- `new_password_confirm`

### 12.3 用户 Schema

`UserSummary`：

- `id`
- `username`
- `email`
- `role`
- `is_active`

`UserDetail` 在此基础上增加 `created_at`、`updated_at`。

`UserRoleUpdateRequest`：

- `role`，只允许 `user` 或 `agent`

`UserStatusUpdateRequest`：

- `is_active`

### 12.4 工单 Schema

`TicketCreateRequest`：

- `title`：5～200 字符
- `description`：10～5000 字符
- `category`
- `priority`

`TicketUpdateRequest`：

- 可选 `title`
- 可选 `description`
- 可选 `category`
- 可选 `priority`
- 至少提供一个字段

`TicketListItem`：

- `id`
- `ticket_no`
- `title`
- `category`
- `priority`
- `status`
- `creator` 摘要
- `assignee` 摘要或空
- `created_at`
- `updated_at`

`TicketDetail` 在列表字段上增加：

- `description`
- `assigned_at`
- `closed_at`
- 当前用户可以执行的操作可由前端根据角色和状态计算；后端不依赖该结果做权限判断

`TicketAssignRequest`：

- `assignee_id`

`TicketStatusChangeRequest`：

- `status`

### 12.5 回复和活动 Schema

`CommentCreateRequest`：

- `content`：1～2000 字符

`CommentResponse`：

- `id`
- `author` 摘要
- `content`
- `created_at`

`ActivityResponse`：

- `id`
- `action`
- `operator` 摘要
- `old_status`
- `new_status`
- `old_assignee` 摘要或空
- `new_assignee` 摘要或空
- `description`
- `created_at`

### 12.6 查询参数

工单列表：

- `page`：默认 1，最小 1
- `page_size`：默认 10，最大 100
- `status`
- `priority`
- `category`
- `assignee_id`，仅管理员范围使用
- `keyword`，匹配工单编号或标题
- `sort_order`：`asc` 或 `desc`，默认 `desc`

用户列表：

- `page`
- `page_size`
- `keyword`，匹配用户名或邮箱
- `role`
- `is_active`

## 13 身份认证设计

### 13.1 密码

- `hash_password(password)` 生成 Argon2 哈希。
- `verify_password(plain, hashed)` 校验密码。
- 不实现可逆加密。

### 13.2 JWT 载荷

至少包含：

```text
sub       用户 ID 字符串
role      签发时角色
exp       过期时间
iat       签发时间
```

每次受保护请求根据 `sub` 重新查询用户，并确认账号存在且启用。最终角色以数据库当前值为准，避免角色调整后旧 Token 长时间保留旧权限。

### 13.3 认证依赖

- `get_current_user()`：解析 Token、查询用户、检查启用状态。
- `require_roles(*roles)`：检查当前数据库角色是否允许访问。
- 资源归属权限不只使用角色依赖，需要在 Service 中结合工单判断。

## 14 Repository 设计

### 14.1 `UserRepository`

- 按 ID 获取用户
- 按邮箱获取用户
- 创建用户
- 分页查询用户
- 更新角色
- 更新启用状态
- 统计角色和状态数量
- 检查客服是否存在未关闭负责工单

### 14.2 `TicketRepository`

- 创建工单
- 按 ID 或编号获取工单
- 按角色范围分页查询工单
- 更新可编辑字段
- 条件领取工单
- 分配和重新分配负责人
- 更新状态和时间字段
- 统计不同角色可见的状态数量

### 14.3 `CommentRepository`

- 新增回复
- 按工单和时间查询回复

### 14.4 `ActivityRepository`

- 新增工单活动
- 按工单和时间查询活动

### 14.5 `UserAdminLogRepository`

- 新增用户管理日志
- 按目标用户查询管理日志，当前版本可仅供内部使用

Repository 不执行 `commit()`。事务提交和回滚由 Service 或请求事务边界控制。

## 15 Service 设计

### 15.1 `AuthService`

负责：

- 注册参数规范化
- 邮箱唯一检查
- 密码哈希
- 登录校验
- Token 签发
- 修改密码

### 15.2 `TicketService`

负责：

- 工单创建和编号生成
- 基于角色的数据查询范围
- 工单归属检查
- 可编辑条件检查
- 撤销规则
- 客服领取与并发冲突
- 管理员分配和重新分配
- 回复权限
- 状态流转
- 活动记录
- 相关事务

### 15.3 `UserService`

负责：

- 管理员用户查询
- 角色调整限制
- 启用和禁用限制
- 用户管理日志
- 管理事务

### 15.4 `DashboardService`

根据当前角色返回不同统计：

- 普通用户：自己各状态工单数。
- 客服：待领取数、本人处理中和已解决数。
- 管理员：全局各状态工单数、启用用户和客服数。

## 16 API 详细设计

### 16.1 `POST /api/v1/auth/register`

访问：公开。

处理：

- 规范化邮箱。
- 检查邮箱唯一。
- 校验密码规则和确认密码。
- 创建 `user` 角色账号。

成功：`201`，返回用户摘要，不返回密码哈希。

错误：邮箱已存在返回 `409`。

### 16.2 `POST /api/v1/auth/login`

访问：公开。

处理：验证邮箱、密码和启用状态。

成功：`200`，返回 Token 信息。

错误：邮箱或密码错误使用同一提示；禁用账号返回 `403`。

### 16.3 `GET /api/v1/auth/me`

访问：已登录。

成功：返回当前数据库中的用户详情。

### 16.4 `PATCH /api/v1/auth/password`

访问：已登录。

处理：校验当前密码和新密码，更新哈希。

成功：返回成功消息；前端清理当前 Token。

### 16.5 `POST /api/v1/tickets`

访问：普通用户。

处理：由当前用户作为创建人，生成唯一工单编号，创建 `open` 工单并写入 `created` 活动记录。

事务：工单和创建记录必须同时提交。

### 16.6 `GET /api/v1/tickets`

访问：已登录。

范围：

- `user`：只返回自己创建的工单。
- `agent`：通过查询参数区分待领取或本人负责；不得返回其他客服负责的工单。
- `admin`：返回全部工单，可按负责人筛选。

返回分页结果。

### 16.7 `GET /api/v1/tickets/{ticket_id}`

访问：已登录且有权查看。

允许：普通用户查看自己创建的工单；客服查看自己负责的工单或无人负责的待领取工单；管理员查看全部工单。

### 16.8 `PATCH /api/v1/tickets/{ticket_id}`

访问：工单创建人。

条件：`status=open` 且 `assignee_id` 为空。

处理：更新允许字段并写入 `updated` 记录。

### 16.9 `POST /api/v1/tickets/{ticket_id}/cancel`

访问：工单创建人。

条件：`status=open` 且负责人为空。

处理：状态改为 `closed`，写入 `closed_at` 和 `cancelled` 记录。

### 16.10 `POST /api/v1/tickets/{ticket_id}/claim`

访问：启用客服。

条件：工单仍为 `open` 且负责人为空。

处理：条件更新负责人，写入 `claimed` 记录。

冲突：影响行数为零时返回 `409`。

### 16.11 `POST /api/v1/tickets/{ticket_id}/assign`

访问：管理员。

条件：工单未关闭，目标用户是启用客服。

处理：首次设置负责人记录 `assigned`，更换负责人记录 `reassigned`。

### 16.12 `POST /api/v1/tickets/{ticket_id}/status`

访问：根据目标流转决定。

规则：

- `open → in_progress`：当前负责人客服。
- `in_progress → resolved`：当前负责人客服。
- `resolved → in_progress`：工单创建人。
- `resolved → closed`：工单创建人。

用户撤销不使用此通用接口，使用专用 `/cancel` 接口。

### 16.13 `GET /api/v1/tickets/{ticket_id}/comments`

访问：有权查看工单的用户。

返回：按时间升序排列的回复。

### 16.14 `POST /api/v1/tickets/{ticket_id}/comments`

访问：工单创建人或当前负责人客服。

条件：工单未关闭；管理员默认不允许回复。

### 16.15 `GET /api/v1/tickets/{ticket_id}/activities`

访问：有权查看工单的用户。

返回：按时间升序排列的时间线。

### 16.16 `GET /api/v1/users`

访问：管理员。

支持：分页、用户名或邮箱搜索、角色和启用状态筛选。

### 16.17 `GET /api/v1/users/{user_id}`

访问：管理员。

返回：用户详情，不包含密码哈希。

### 16.18 `PATCH /api/v1/users/{user_id}/role`

访问：管理员。

限制：

- 只允许 `user` 与 `agent` 相互调整。
- 不能通过该接口创建或降级管理员。
- 客服存在未关闭负责工单时不能降级。

处理：更新角色并写入 `role_changed` 日志。

### 16.19 `PATCH /api/v1/users/{user_id}/status`

访问：管理员。

限制：

- 管理员不能禁用自己。
- 客服存在未关闭负责工单时不能禁用。

处理：更新状态并写入启用或禁用日志。

### 16.20 `GET /api/v1/dashboard/summary`

访问：已登录。

根据当前角色返回对应结构，不接受客户端指定要查看的角色。

### 16.21 `GET /api/v1/health`

访问：公开。

返回应用可用状态。当前只用于本地连通验证，不暴露数据库密码和内部环境信息。

## 17 权限实现

### 17.1 角色依赖

Router 层用于限制明显角色入口，例如管理员用户管理和客服领取。

### 17.2 资源权限

Service 层按以下规则判断：

- 普通用户：角色为 `user` 且 `ticket.creator_id == current_user.id`
- 客服处理：`ticket.assignee_id == current_user.id`
- 客服查看待领取：`ticket.status == open and ticket.assignee_id is None`
- 管理员查看：允许查看所有工单

### 17.3 返回码原则

- 用户无权访问已知资源时返回 `403`。
- 数据确实不存在时返回 `404`。
- 不通过改变前端参数扩大数据查询范围。

## 18 状态机实现

合法流转集中定义，不在多个路由中重复 `if`：

```text
open          -> in_progress
in_progress   -> resolved
resolved      -> in_progress
resolved      -> closed
```

撤销是独立业务动作：

```text
open + 无负责人 -> closed
```

Service 同时检查：

- 原状态与目标状态是否合法
- 当前角色是否可以执行该流转
- 当前用户是否为创建人或负责人
- 工单是否已关闭

## 19 事务设计

### 19.1 事务边界

Service 负责组织一组写操作，全部成功后提交，任何异常回滚。

必须原子完成：

- 创建工单与创建活动
- 修改工单与修改活动
- 撤销工单与撤销活动
- 领取工单与领取活动
- 分配工单与分配活动
- 状态变化与状态活动
- 角色变化与用户管理日志
- 启用状态变化与用户管理日志

### 19.2 Session 规则

- 每个请求使用独立 `AsyncSession`。
- Repository 使用同一个 Session。
- Repository 不私自提交。
- Service 决定提交和回滚。
- 提交后在需要返回数据库生成字段时刷新对象。

## 20 并发领取实现

领取必须使用原子条件更新：

```sql
UPDATE tickets
SET assignee_id = :agent_id,
    assigned_at = :now,
    updated_at = :now
WHERE id = :ticket_id
  AND assignee_id IS NULL
  AND status = 'open';
```

流程：

1. 检查当前用户为启用客服。
2. 执行条件更新。
3. 检查影响行数。
4. 影响一行时新增领取活动并提交。
5. 影响零行时回滚或结束当前事务，重新读取工单。
6. 工单不存在返回 `404`；已领取或状态变化返回 `409`。

不能在读取负责人为空后直接无条件更新，因为两个请求可能同时通过读取检查。

## 21 统一响应设计

### 21.1 成功

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

### 21.2 分页

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [],
    "page": 1,
    "page_size": 10,
    "total": 0
  }
}
```

### 21.3 错误

```json
{
  "code": 40001,
  "message": "工单不存在",
  "data": null
}
```

## 22 业务错误码


| 错误码  | HTTP | 含义                   |
| --------- | ------ | ------------------------ |
| `10001` | 422  | 请求参数校验失败       |
| `20001` | 401  | 邮箱或密码错误         |
| `20002` | 401  | Token 无效或过期       |
| `20003` | 403  | 账号已禁用             |
| `20004` | 400  | 当前密码错误           |
| `30001` | 404  | 用户不存在             |
| `30002` | 409  | 邮箱已经注册           |
| `30003` | 400  | 不能禁用当前管理员自己 |
| `30004` | 409  | 客服仍有未关闭负责工单 |
| `30005` | 400  | 不允许的角色修改       |
| `40001` | 404  | 工单不存在             |
| `40002` | 403  | 无权查看或操作该工单   |
| `40003` | 409  | 当前工单不能修改       |
| `40004` | 409  | 工单已被其他客服领取   |
| `40005` | 409  | 非法工单状态流转       |
| `40006` | 409  | 已关闭工单不能继续操作 |
| `40007` | 400  | 指定负责人不是启用客服 |
| `40008` | 409  | 当前工单不能撤销       |
| `50001` | 400  | 回复内容无效           |
| `90001` | 500  | 系统暂时不可用         |

Pydantic 的字段错误由异常处理器转换成统一结构，并保留安全、可理解的字段错误信息。

## 23 异常处理

### 23.1 `AppException`

包含：

- `code`
- `message`
- `http_status`
- 可选安全详情

Service 抛出业务异常，Router 不重复转换。

### 23.2 全局异常处理器

处理：

- `AppException`
- FastAPI 请求校验异常
- JWT 相关异常
- 未预期异常

未预期异常只返回通用信息，真实堆栈仅在后端开发日志中出现。

## 24 日志设计

控制台日志至少记录：

- 应用启动和关闭
- 请求方法、路径、状态码和耗时
- 未预期异常及堆栈
- 管理员初始化结果

不得记录：

- 明文密码
- JWT 完整内容
- 数据库密码
- 登录请求完整 Body

业务审计使用数据库中的两张日志表，不依赖控制台日志替代。

## 25 Alembic 迁移设计

迁移顺序建议：

```text
001_create_users
002_create_tickets
003_create_ticket_activity_logs
004_create_ticket_comments
005_create_user_admin_logs
```

要求：

- 每次迁移只包含一个清晰主题。
- Model 变化后通过 Alembic 生成并人工检查迁移。
- 不通过删除数据库代替正常迁移。
- 执行新迁移前确认数据库地址正确。
- 本地演示数据不写入结构迁移。

## 26 管理员初始化

提供 `scripts/init_admin.py`：

- 从命令行或安全环境变量读取管理员用户名、邮箱和密码。
- 邮箱不存在时创建管理员。
- 邮箱已存在时只在明确确认的逻辑下升级为管理员。
- 密码使用同一 Argon2 工具哈希。
- 不把默认管理员密码写死在源码。
- 脚本可重复执行，不产生重复账号。

公开注册接口永远不能接收并信任 `role=admin`。

## 27 CORS 与接口安全

- 开发环境只允许 `http://localhost:5173`。
- 只开放前端需要的 HTTP 方法和请求头。
- 不在生产式配置中使用任意来源与认证组合。
- 所有写接口都要求正确身份和权限。
- 任何创建人、操作人都从当前登录用户取得。
- 任何管理员身份都从数据库角色确认。
- 用户输入作为参数交给 ORM，不拼接原始 SQL 字符串。
- 返回数据显式使用响应 Schema，避免意外返回 `password_hash`。

## 28 Apifox 设计

### 28.1 环境变量

```text
base_url=http://localhost:8000/api/v1
user_token=
agent_token=
admin_token=
ticket_id=
```

### 28.2 认证脚本

登录请求成功后，将不同角色 Token 保存到对应环境变量。各接口通过 Bearer Token 引用，不把真实 Token 固定写入文档。

### 28.3 用例组织

```text
01 健康检查
02 注册与登录
03 普通用户工单
04 客服领取与处理
05 管理员分配
06 回复与时间线
07 用户管理
08 数据概览
09 权限和异常
10 并发领取
```

### 28.4 验证重点

- HTTP 状态码正确。
- `code`、`message`、`data` 结构一致。
- 无权限请求不会返回业务数据。
- 非法状态请求不会修改数据库。
- 并发领取只有一个成功。
- 密码哈希和敏感配置不出现在响应。

## 29 后端阶段安排

### 后端阶段 1：基础框架

- 建立目录和配置。
- 创建异步数据库 Engine 与 Session。
- 配置 CORS、异常处理和统一响应。
- 实现健康检查。

验收：服务启动，前端和 Apifox 可以访问健康检查。

### 后端阶段 2：认证

- 创建 `users` 模型与迁移。
- 完成密码、JWT、认证依赖和管理员初始化。
- 完成注册、登录、当前用户和修改密码。

验收：三种角色可登录，禁用账号和无效 Token 被拒绝。

### 后端阶段 3：普通用户工单

- 创建 `tickets` 模型与迁移。
- 完成创建、列表、详情、修改和撤销。
- 完成用户范围查询和概览。

验收：用户只能操作自己的工单，数据保存到 MySQL。

### 后端阶段 4：领取、分配与活动

- 创建活动表与迁移。
- 完成条件领取、分配、重新分配和活动记录。

验收：并发领取仅一个成功，活动与业务修改保持事务一致。

### 后端阶段 5：回复与状态

- 创建回复表与迁移。
- 完成回复、状态机和时间线查询。

验收：合法流转成功，非法流转和越权被拒绝。

### 后端阶段 6：用户管理与概览

- 创建用户管理日志表与迁移。
- 完成用户查询、角色调整、启用和禁用。
- 完成三种角色概览。

验收：安全限制和管理日志正确。

### 后端阶段 7：Apifox 验证与整理

- 完成接口目录、环境变量和用例。
- 修正响应、权限、事务和错误信息不一致。
- 检查日志与敏感数据。

验收：PRD 指定的主要测试场景全部通过。

## 30 后端完成标准

- [ ]  应用可以通过环境变量连接 MySQL。
- [ ]  五张核心表通过 Alembic 创建。
- [ ]  普通用户只能通过注册获得 `user` 角色。
- [ ]  密码以 Argon2 哈希保存。
- [ ]  JWT、角色和启用状态校验正确。
- [ ]  工单查询遵守角色和数据归属范围。
- [ ]  工单状态只允许合法流转。
- [ ]  并发领取只有一个请求成功。
- [ ]  业务数据和操作记录在同一事务中完成。
- [ ]  已关闭工单不能回复、修改或重新分配。
- [ ]  用户管理限制和日志正确。
- [ ]  所有接口返回统一响应结构。
- [ ]  敏感信息不出现在响应和普通日志中。
- [ ]  Apifox 主要场景通过。

## 31 与前端文档的边界

后端确定接口、权限和业务结果；前端确定页面呈现和交互。以下约定必须同步：

- 路径和 HTTP 方法
- 请求字段和枚举值
- 响应字段和分页结构
- Token 携带方式
- HTTP 状态码和业务错误码
- 角色、状态、分类和优先级映射

接口发生变化时，先修改后端设计和 Apifox 定义，再同步前端设计，不允许只修改其中一端。
