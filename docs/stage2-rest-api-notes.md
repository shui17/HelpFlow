# HTTP 接口与 REST 基础笔记

## 1. 什么是接口

接口是两个程序之间约定好的沟通入口和规则。

在 HelpFlow 中，Vue 前端通过 HTTP 接口调用 FastAPI 后端：

```text
Vue 前端
   ↓ HTTP 请求
FastAPI 接口
   ↓
Service 业务逻辑
   ↓
数据存储
```

HTTP 接口需要约定：

- HTTP 方法；
- URL；
- 请求数据；
- 响应状态码；
- 响应数据格式。

例如创建工单接口：

```text
方法：POST
路径：/api/v1/tickets
请求格式：JSON
成功状态码：201
响应格式：code、message、data
```

## 2. 接口与普通 Python 函数的区别

普通 Python 函数只能由 Python 代码调用：

```python
ticket_service.create_ticket(...)
```

HTTP 接口可以被多种客户端调用：

```http
POST /api/v1/tickets
```

调用方可以是 Vue、浏览器、手机 App、Swagger 或其他后端服务。

客户端不需要知道接口内部是怎么实现的，只需要遵守方法、路径和数据格式约定。

## 3. 什么是 REST

REST 是一种 HTTP 接口设计风格。

最核心的规则是：

> URL 表示资源，HTTP 方法表示对资源进行的操作。

HelpFlow 中的资源包括：

```text
/users       用户资源
/tickets     工单资源
/comments    回复资源
```

推荐：

```text
POST /tickets
GET  /tickets/1
```

不推荐：

```text
/createTicket
/getTicket
```

因为创建和查询等动作已经由 HTTP 方法表示。

## 4. 常用 HTTP 方法

| 方法 | 含义 | 示例 |
| --- | --- | --- |
| `GET` | 查询资源 | `GET /api/v1/tickets/1` |
| `POST` | 创建资源 | `POST /api/v1/tickets` |
| `PUT` | 完整替换资源 | `PUT /api/v1/tickets/1` |
| `PATCH` | 修改部分字段 | `PATCH /api/v1/tickets/1/status` |
| `DELETE` | 删除资源 | `DELETE /api/v1/tickets/1` |

同一个 URL 可以通过不同方法表示不同操作：

```text
GET    /api/v1/tickets/1    查询工单
PATCH  /api/v1/tickets/1    修改工单
DELETE /api/v1/tickets/1    删除工单
```

## 5. 集合资源与单个资源

不带 ID 通常表示资源集合：

```text
GET  /api/v1/tickets    查询工单列表
POST /api/v1/tickets    创建新工单
```

带 ID 表示一个具体资源：

```text
GET /api/v1/tickets/1
```

可以理解为：

```text
/tickets       工单集合
/tickets/1     ID 为 1 的工单
```

## 6. 从属资源

回复属于某张工单，因此可以使用嵌套路径：

```text
POST /api/v1/tickets/1/comments
GET  /api/v1/tickets/1/comments
```

含义是：

```text
工单 1 的回复集合
```

## 7. 路径参数与查询参数

### 7.1 路径参数

路径参数用于确定具体资源：

```text
GET /api/v1/tickets/1
```

这里的 `1` 是工单 ID。

### 7.2 查询参数

查询参数用于筛选、排序和分页：

```text
GET /api/v1/tickets?status=open
GET /api/v1/tickets?page=1&page_size=10
GET /api/v1/tickets?status=open&priority=high
```

基本原则：

```text
资源身份放在路径参数中
筛选条件放在查询参数中
```

## 8. 请求格式

创建或修改资源时，客户端通常发送 JSON 请求体：

```http
POST /api/v1/tickets
Content-Type: application/json
```

```json
{
  "title": "无法登录",
  "description": "输入密码后页面没有反应",
  "creator_id": 1,
  "priority": "high"
}
```

## 9. 响应格式

HelpFlow 使用统一响应格式：

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

字段含义：

- `code`：HelpFlow 自定义的业务结果编号；
- `message`：处理结果的文字说明；
- `data`：真正返回的业务数据。

成功示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 1,
    "title": "无法登录"
  }
}
```

失败示例：

```json
{
  "code": 40001,
  "message": "工单不存在",
  "data": null
}
```

## 10. HTTP 状态码

| 状态码 | 含义 |
| --- | --- |
| `200` | 查询或修改成功 |
| `201` | 创建资源成功 |
| `400` | 一般请求或业务数据错误 |
| `401` | 未登录或凭证无效 |
| `403` | 已登录但没有权限 |
| `404` | 资源不存在 |
| `409` | 请求与资源当前状态冲突 |
| `422` | 请求字段校验失败 |

HTTP 状态码与业务 `code` 不相同：

```text
HTTP 状态码：404
业务错误码：40001
```

## 11. 核心总结

```text
接口是程序之间约定好的功能入口
REST 使用 URL 表示资源
REST 使用 HTTP 方法表示操作
具体资源使用路径参数
筛选和分页使用查询参数
请求和响应通常使用 JSON
处理结果使用 HTTP 状态码表达
```
