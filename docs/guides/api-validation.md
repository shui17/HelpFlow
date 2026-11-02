# HelpFlow FastAPI 与 Pydantic 校验指南

> 本文包含早期接口版本的说明。当前注册、登录和权限要求见 [认证指南](security.md)，工单操作见 [工单指南](ticket-workflow.md)。
本阶段在阶段二的 HTTP 接口上补齐内存注册、工单内容修改、关键词搜索、排序、校验、配置和日志。完成后，应能沿着 Router → Schema → Service → MemoryStorage 解释一次请求，并用 Apifox 验证正常和异常结果。

当前注册只登记 username、email，固定创建普通用户；没有密码、登录、JWT 和数据权限。creator_id、author_id 仍由客户端提供。所有数据都保存在单进程内存中，重启或开发模式自动重载后消失，多个 worker 也不会共享数据。本阶段用于本地学习。

## 1 启动与测试

在 PowerShell 执行：

```powershell
cd D:\vscode\HelpFlow\backend
uv sync --locked
.\.venv\Scripts\fastapi.exe dev app\main.py
```

如需配置应用名称和前端来源，先复制示例，再修改 backend/.env：

```powershell
Copy-Item .env.example .env
```

```dotenv
HELPFLOW_APP_NAME=HelpFlow
HELPFLOW_CORS_ORIGINS=["http://localhost:5173"]
```

Settings 在创建应用时读取 backend/.env，操作系统环境变量优先。列表使用 JSON 数组；配置变化后重启服务。实际 .env 被 Git 忽略，示例文件可以提交。配置逻辑见 `backend/app/config.py`。

在另一个终端运行全部测试：

```powershell
cd D:\vscode\HelpFlow\backend
.\.venv\Scripts\python.exe -m pytest tests -q
```

pytest 已声明为开发依赖，默认 uv sync 会安装开发依赖。

## 2 Apifox 准备

在 Apifox 中创建 HTTP 项目，将 `http://127.0.0.1:8000/openapi.json` 作为 OpenAPI 地址导入。应用更新后可重新导入。设置环境变量：

```text
base_url=http://127.0.0.1:8000/api/v1
user_id=1
ticket_id=1
```

下面请求地址使用 `{{base_url}}`。POST、PATCH 请求体选择 JSON，确保 Content-Type 为 application/json。ID 应按实际创建响应填写；不要把示例中的 1 当作固定值。Swagger `/docs` 可用于查看接口定义，练习操作使用 Apifox。

## 3 内存注册与健康检查

```http
GET {{base_url}}/health
```

```json
{"code": 0, "message": "success", "data": {"status": "ok"}}
```

旧地址 `/health` 仍返回 `{"status":"ok"}`，用于兼容阶段二。

```http
POST {{base_url}}/auth/register
```

```json
{
  "username": "Finnian",
  "email": "finnian@example.com"
}
```

成功返回 201 和公开用户字段 id、username、email、role、is_active。用户名去除首尾空白，邮箱规范化为小写；同一邮箱再次注册返回 409、业务码 30002。可以通过 `GET {{base_url}}/users/{{user_id}}` 查询用户。

公开注册不接受 role、password 或 is_active。提交这些字段返回 422。阶段二 `POST /users` 仍可使用，但 role 仅允许省略或填写 user。此阶段不能通过 HTTP 创建客服或管理员；后续阶段再添加受保护的管理入口。

## 4 创建与修改工单

```http
POST {{base_url}}/tickets
```

```json
{
  "title": "无法登录",
  "description": "输入正确密码后仍然无法登录",
  "creator_id": 1,
  "priority": "high"
}
```

创建成功返回 201。title 为 1 到 200 个字符，description 为 1 到 5000 个字符，首尾空白清理后再检查长度。priority 为 low、normal、high、urgent，默认 normal。这里沿用阶段二的字段长度；总体后端设计中的 category、ticket_no 和更严格业务约束属于后续扩展。

```http
PATCH {{base_url}}/tickets/{{ticket_id}}
```

```json
{
  "title": "登录问题补充说明",
  "priority": "urgent"
}
```

成功返回 200 和修改后的完整工单。没有提交的 description 保持原值；id、creator_id、status、assignee_id、created_at 都不能通过本接口修改。

需要分清三个请求：

- `{"title":"新标题"}`：只修改标题。
- `{"title":null}`：返回 422；该字段不允许清空。
- `{}`：返回 422；至少提交一个可修改字段。

修改只允许用于 open 且无人负责的工单；已处理、已解决、已关闭或已分配时返回 409、业务码 40003。工单不存在返回 404、业务码 40001。所有输入和业务检查通过后才保存副本，失败不会留下部分修改。

可以继续使用阶段二接口 `PATCH /tickets/{id}/status`，将状态改为 in_progress，再尝试编辑内容，观察 409。

## 5 搜索 排序与分页

```http
GET {{base_url}}/tickets?keyword=登录&status=open&priority=high&sort_order=asc&page=1&page_size=2
```

| 参数 | 行为 |
| --- | --- |
| page | 从 1 开始，默认 1 |
| page_size | 1 到 100，默认 10 |
| status | 可选 open、in_progress、resolved、closed |
| priority | 可选 low、normal、high、urgent |
| keyword | 最多 200 字符，匹配标题子串或完整 ID；标题匹配忽略大小写，去除首尾空白，空白不筛选 |
| sort_order | asc 或 desc，按 ID 升序或降序，默认 desc |

例如 keyword=2 可以匹配 ID 为 2 的工单，也可以匹配标题包含 2 的工单，但不会仅因 ID 为 12 而匹配。当前没有 ticket_no，因此搜索使用数字 ID。

多个筛选条件取交集。处理顺序为：筛选 → 排序 → 统计总数 → 分页。total 表示筛选后的总数；超出范围页返回 200，items 为空但 total 保留实际总数。省略新增参数时，阶段二的默认倒序行为不变。

## 6 代码怎么读

建议按以下顺序对照请求阅读：

1. `backend/app/main.py`：create_app 装配配置、中间件、异常处理与路由；app 是服务器加载入口。
2. `backend/app/routers/auth.py`、`health.py`、`tickets.py`：URL、方法、状态码、Path、Query、Depends 和响应模型。
3. `backend/app/schemas.py`：TicketCreate、TicketUpdate、TicketRead，以及输入字段、枚举、额外字段和跨字段校验。
4. `backend/app/dependencies.py`：两个 Service 共用一份 MemoryStorage，Depends 把 Service 交给路由。测试可覆盖这些依赖。
5. `backend/app/in_memory/services.py`：工单搜索、排序、分页和可编辑条件。业务规则仍使用普通 Python，不依赖 HTTP。
6. `backend/app/in_memory/storage.py`：负责内存对象保存和读取。未来 Repository 将承担数据访问职责，Service 决定业务流程。
7. `backend/app/exception_handlers.py`、`middleware.py`：分别负责失败响应和请求日志。

Ticket 是业务数据类，TicketRead 是对外响应模型。`from_attributes=True` 允许从业务对象取值，显式列出的响应字段决定客户端能看到什么；内部新增属性不会自动出现在 JSON 中。旧名称 TicketCreateRequest 和 TicketResponse 是兼容别名，方便对照阶段二材料。

PATCH 中的 `payload.model_dump(exclude_unset=True)` 只提取客户端实际提交的字段，使未提交的默认值不会覆盖原值。参阅 [FastAPI 局部更新](https://fastapi.tiangolo.com/tutorial/body-updates/)；输入模型的 extra 和字符串清理设置参阅 [Pydantic 配置](https://docs.pydantic.dev/latest/api/config/)。

## 7 异常与日志验证

| 操作 | HTTP | 业务码 |
| --- | --- | --- |
| 重复注册邮箱 | 409 | 30002 |
| 查询或修改不存在的工单 | 404 | 40001 |
| 修改不允许编辑的工单 | 409 | 40003 |
| 空白字段、非法枚举、空修改、未知输入字段 | 422 | 10001 |
| 不存在的 URL | 404 | 10404 |
| URL 不支持该方法 | 405 | 10405 |
| 未预期异常 | 500 | 90001 |

业务异常、参数异常与 HTTPException 统一返回 code、message、data。HTTPException 的通用码为 10000 加 HTTP 状态码；业务异常使用独立业务码。参数错误仅返回字段位置、说明和类型，不回显提交值。未预期异常返回“系统暂时不可用”，堆栈留在服务端日志。

普通响应包含 X-Process-Time，单位为秒；CORS 允许浏览器读取该响应头。中间件日志记录 method、path、status、duration_ms，不记录查询串、请求体或认证头。未预期 500 由最外层错误处理器生成，仍有请求日志，但不保证包含耗时头；CORS 预检由 CORS 中间件直接处理。

阶段三测试见 `backend/tests/test_api_validation.py`，覆盖注册和旧接口角色限制、局部更新、失败不写入、搜索与分页、响应字段白名单、HTTP 错误、500 脱敏、日志及配置。阶段二测试继续作为回归验证。
