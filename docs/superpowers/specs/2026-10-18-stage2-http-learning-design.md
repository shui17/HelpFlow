# HelpFlow 阶段 2 HTTP 学习实现设计

## 1. 目标

在不提前接入 MySQL、JWT 和完整权限系统的前提下，为 HelpFlow 增加一组可运行、可观察的 HTTP JSON 接口。接口复用阶段 1 的 `MemoryStorage`、`UserService` 和 `TicketService`，让学习者看清 HTTP 层如何调用已有业务层。

本阶段完成后，应能通过浏览器 Swagger 页面或 HTTP 客户端观察 URL、方法、请求头、请求体、响应体和状态码，并能解释 FastAPI、Pydantic、Service 与内存存储之间的数据流。

## 2. 实现范围

### 2.1 应用入口

保留 `backend/app/main.py` 作为 FastAPI 应用入口，负责：

- 创建 FastAPI 应用；
- 配置仅允许 `http://localhost:5173` 的开发环境 CORS；
- 注册用户与工单路由；
- 注册业务异常与请求校验异常处理器；
- 保留根路径和健康检查接口。

### 2.2 请求与响应 Schema

新增 `backend/app/schemas.py`，使用 Pydantic 定义：

- 创建用户请求；
- 创建工单请求；
- 修改工单状态请求；
- 创建回复请求；
- 用户、工单和回复响应数据；
- `code`、`message`、`data` 组成的统一响应结构。

Schema 只负责 HTTP 输入输出的数据形状和基础字段校验，不包含业务流程。

### 2.3 依赖与运行期状态

新增 `backend/app/dependencies.py`，在应用进程内创建一份共享的：

- `MemoryStorage`；
- `UserService`；
- `TicketService`。

数据只存在于内存中，应用重启后清空。该行为是本阶段的教学限制，不作为正式生产方案。

### 2.4 用户接口

新增 `backend/app/routers/users.py`：

- `POST /api/v1/users`：创建用户，成功返回 HTTP `201`；
- `GET /api/v1/users/{user_id}`：查询指定用户，成功返回 HTTP `200`。

### 2.5 工单接口

新增 `backend/app/routers/tickets.py`：

- `POST /api/v1/tickets`：创建工单，成功返回 HTTP `201`；
- `GET /api/v1/tickets/{ticket_id}`：查询指定工单，成功返回 HTTP `200`；
- `PATCH /api/v1/tickets/{ticket_id}/status`：局部修改工单状态；
- `POST /api/v1/tickets/{ticket_id}/comments`：新增回复，成功返回 HTTP `201`；
- `GET /api/v1/tickets/{ticket_id}/comments`：查询回复列表，成功返回 HTTP `200`。

## 3. 数据流

```text
HTTP JSON 请求
    ↓
FastAPI Router：匹配方法和路径
    ↓
Pydantic Schema：解析并校验请求数据
    ↓
阶段 1 Service：执行业务规则
    ↓
MemoryStorage：保存或读取 Python 对象
    ↓
Pydantic Schema：序列化响应数据
    ↓
HTTP 状态码 + JSON 响应
```

## 4. 错误与状态码

业务异常由应用级异常处理器统一转换：

| 场景 | HTTP 状态码 |
| --- | ---: |
| 请求 JSON 或字段校验失败 | `422` |
| 一般业务数据不合法 | `400` |
| 用户或工单不存在 | `404` |
| 邮箱重复 | `409` |
| 工单状态非法流转 | `409` |
| 已关闭工单新增回复 | `409` |

错误仍使用统一结构：

```json
{
  "code": 40001,
  "message": "工单不存在: 99",
  "data": null
}
```

`code` 是 HelpFlow 的业务错误码，HTTP 状态码表达请求在 HTTP 层的结果，两者职责不同。

## 5. 同步与异步边界

阶段 1 的 Service 和内存 Storage 都是同步代码，而且没有等待数据库或网络 I/O。因此本阶段路由使用普通 `def`。FastAPI 会妥善执行同步路由，这比仅为了语法而写 `async def` 更准确。

异步等待示例放在独立练习文件中讲解；等后续接入 SQLAlchemy Async 与 MySQL 时，再把相关调用链改为真正的 `async def` 和 `await`。

## 6. 学习文档

新增 `docs/stage2-http-guide.md`，包含：

- 启动服务的方法；
- Swagger 操作顺序；
- 每个接口的 HTTP 方法、路径、请求体和状态码；
- 使用浏览器开发者工具观察请求的方法；
- `400`、`404`、`409`、`422` 的区别；
- CORS 的作用；
- 从 Vue 到 FastAPI、Service 和存储的完整数据流。

## 7. 验证

使用 FastAPI `TestClient` 或等价测试方式覆盖：

- 创建并查询用户；
- 创建并查询工单；
- 修改工单状态；
- 新增并查询回复；
- 不存在资源返回 `404`；
- 重复邮箱、非法状态流转和关闭后回复返回 `409`；
- 请求字段校验失败返回 `422`；
- 允许来源的 CORS 预检响应正确。

验证过程不向 Git 创建提交。

## 8. 明确不做

本阶段不实现：

- 密码注册和登录；
- JWT 与真实身份认证；
- 用户角色和资源权限控制；
- MySQL、SQLAlchemy 和 Alembic；
- Vue 页面；
- 生产级配置和持久化。

这些内容将在后续阶段替换本阶段的教学实现，而 HTTP 路由、Schema、状态码和分层思想可以继续沿用。
