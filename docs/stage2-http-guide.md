# HelpFlow 阶段 2：HTTP 实践指南

阶段三已在此基础上增加注册、内容修改、搜索、排序与配置，最新操作步骤见 [阶段三实践指南](stage3-fastapi-guide.md)。本文保留阶段二学习过程；其中 role 现在只允许普通用户，`POST /auth/register` 已实现为内存用户登记。

## 1. 本阶段做了什么

当前 HelpFlow 已经能通过 HTTP 调用阶段 1 的业务代码：

```text
浏览器 / Vue / Swagger
        ↓ HTTP 请求
FastAPI Router
        ↓ Python 参数
Pydantic Schema
        ↓ 已校验的数据
阶段 1 Service
        ↓ Python 对象
MemoryStorage
        ↓
JSON 响应 + HTTP 状态码
```

这里使用内存存储，所以关闭服务后数据会消失。后续接入 MySQL 时，HTTP 层的很多概念仍然可以保留。

## 2. 启动项目

在 PowerShell 中执行：

```powershell
cd D:\vscode\HelpFlow\backend
.\.venv\Scripts\fastapi.exe dev app\main.py
```

然后打开：

- Swagger 接口页面：`http://127.0.0.1:8000/docs`
- 健康检查：`http://127.0.0.1:8000/health`
- OpenAPI JSON：`http://127.0.0.1:8000/openapi.json`

Swagger 是本阶段最方便的练习入口。展开接口，点击 **Try it out**，填写 JSON 后执行，就能同时看到请求和响应。

## 3. 推荐操作顺序

### 3.1 创建用户

```http
POST /api/v1/users
Content-Type: application/json
```

```json
{
  "username": "Finnian",
  "email": "finnian@example.com",
  "role": "user"
}
```

成功状态码是 `201 Created`。响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 1,
    "username": "Finnian",
    "email": "finnian@example.com",
    "role": "user",
    "is_active": true
  }
}
```

### 3.2 创建工单

```http
POST /api/v1/tickets
Content-Type: application/json
```

```json
{
  "title": "无法登录",
  "description": "输入正确密码后仍然无法登录",
  "creator_id": 1,
  "priority": "high"
}
```

### 3.3 查询工单列表

```http
GET /api/v1/tickets?page=1&page_size=10&status=open&priority=high
```

查询参数不会确定某一张工单，而是控制列表的筛选和分页：

- `page`：第几页，从 `1` 开始；
- `page_size`：每页多少条，范围为 `1` 到 `100`；
- `status`：可选状态筛选；
- `priority`：可选优先级筛选。

分页响应中的 `total` 是筛选后的总记录数，不是当前页的记录数：

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

如果请求的页码超过现有数据范围，接口仍然返回 `200`，但 `items` 是空列表，因为“这一页没有数据”不是请求错误。

### 3.4 查询单张工单

```http
GET /api/v1/tickets/1
```

GET 请求通常没有请求体。`1` 是 URL 路径参数，表示资源 ID。

### 3.5 修改状态

```http
PATCH /api/v1/tickets/1/status
Content-Type: application/json
```

```json
{
  "status": "in_progress"
}
```

这里使用 PATCH，因为只修改工单的一部分，而不是用客户端提交的数据替换整张工单。

阶段 1 允许的状态变化是：

```text
open → in_progress → resolved → closed
                         ↓
                    in_progress
```

### 3.6 新增和查询回复

```http
POST /api/v1/tickets/1/comments
Content-Type: application/json
```

```json
{
  "author_id": 1,
  "content": "补充：浏览器显示 401。"
}
```

然后请求：

```http
GET /api/v1/tickets/1/comments
```

## 4. 一个 HTTP 请求包含什么

以创建工单为例：

- 方法 `POST`：表示创建资源；
- URL `/api/v1/tickets`：表示要操作的资源；
- 请求头 `Content-Type: application/json`：说明请求体是 JSON；
- 请求体：包含标题、描述、创建人和优先级；
- 状态码 `201`：表示资源创建成功；
- 响应头：描述响应格式、长度和 CORS 等信息；
- 响应体：HelpFlow 返回的 JSON 数据。

JSON 只是 HTTP 请求体和响应体的一种常见数据格式，HTTP 本身不等于 JSON。

## 5. 状态码怎么区分

| 状态码 | 本项目中的含义 | 示例 |
| --- | --- | --- |
| `200` | 查询或修改成功 | 查询工单、修改状态 |
| `201` | 新资源创建成功 | 创建用户、工单、回复 |
| `400` | 数据通过了结构校验，但违反一般业务规则 | Service 判断业务数据无效 |
| `404` | URL 指向的资源不存在 | 查询工单 999 |
| `409` | 请求与当前资源状态冲突 | 重复邮箱、非法状态流转 |
| `422` | 请求字段缺失、类型或枚举值不正确 | `creator_id` 传字符串 |

重点理解：

- `404` 是“找不到目标”；
- `409` 是“目标可能存在，但当前状态不允许这样操作”；
- `422` 发生在进入 Service 之前，由 Pydantic 发现请求形状不正确；
- `400` 表示请求结构可以解析，但业务数据仍不合要求。

HTTP 状态码和响应里的 `code` 不是同一个东西。HTTP 状态码供浏览器、代理和通用客户端理解；`code` 是 HelpFlow 自己定义的、更具体的业务错误编号。

## 6. CORS 是什么

浏览器把协议、主机和端口组成的组合称为“来源”。例如：

```text
Vue:     http://localhost:5173
FastAPI: http://localhost:8000
```

端口不同，所以它们是不同来源。浏览器会检查 FastAPI 响应中的 CORS 头，确认 Vue 是否被允许读取响应。

当前后端只允许 `http://localhost:5173`，并允许 `GET`、`POST` 和 `PATCH`。复杂跨域请求之前，浏览器可能先发送一个 `OPTIONS` 预检请求；它是在询问服务器是否允许真正的请求。

CORS 是浏览器安全策略，不是用户身份认证。即使 CORS 允许某个前端来源，后端仍然需要在后续阶段使用 JWT 和权限检查保护数据。

## 7. 在浏览器中观察真实请求

1. 启动 FastAPI，并打开 `http://127.0.0.1:8000/docs`。
2. 按 `F12` 打开开发者工具，选择 **Network（网络）**。
3. 在 Swagger 中执行一个创建工单请求。
4. 在 Network 列表中点开对应请求。
5. 查看：
   - **Headers**：Request URL、Request Method、Status Code、请求头；
   - **Payload**：发送的 JSON 请求体；
   - **Response/Preview**：服务器返回的 JSON。

建议亲自制造三种错误并观察：

- 查询 `/api/v1/tickets/999`，得到 `404`；
- 再次使用相同邮箱创建用户，得到 `409`；
- 创建工单时删除 `title`，得到 `422`。

## 8. 每个代码文件负责什么

| 文件 | 职责 |
| --- | --- |
| `backend/app/main.py` | 创建应用、注册 CORS、异常处理和路由 |
| `backend/app/schemas.py` | 定义 HTTP 请求和响应的 JSON 形状 |
| `backend/app/dependencies.py` | 向路由提供共享的 Service |
| `backend/app/routers/users.py` | 用户 URL、HTTP 方法和状态码 |
| `backend/app/routers/tickets.py` | 工单与回复的 URL、方法和状态码 |
| `backend/app/exception_handlers.py` | 把 Python 业务异常转换为 HTTP 错误响应 |
| `backend/practice/stage1_helpflow/services.py` | 真正的业务规则 |
| `backend/practice/stage1_helpflow/storage.py` | 当前阶段的数据保存位置 |

最重要的分层规则是：Router 负责 HTTP，Service 负责业务。以后从内存存储换成 MySQL 时，不应该把 SQL 直接写进 Router。

## 9. 当前刻意没有实现的内容

- `POST /auth/register` 和 `POST /auth/login`；
- 密码哈希与 JWT；
- 当前登录用户和权限判断；
- MySQL 持久化；
- 真正的异步数据库 I/O。

所以当前接口中的 `creator_id` 和 `author_id` 由客户端直接提交，只适合学习。正式项目中，这些 ID 应从 JWT 对应的当前用户取得，不能信任客户端自报身份。
