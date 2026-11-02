# HelpFlow FastAPI 与 Pydantic 设计

> 历史设计记录：文中的实现范围反映当时版本；当前目录与依赖以 [文件职责图](../file-map.md) 为准。
## 目标与已确认范围

2026-10-27 用户确认在阶段二实现上增量补齐阶段三。继续使用阶段一 Service 和 MemoryStorage，不重写业务层；学习路线 Word 文档仅作为阶段范围依据，不修改原文档。

新增内存注册、独立健康检查路由、工单内容修改、关键词搜索、可选排序、输入校验、HTTP 异常处理、环境配置和请求耗时日志。保留已有状态流转、回复和学习接口。数据库、密码与 JWT、权限、领取并发及前端留到后续阶段。

## 接口与边界

- `POST /api/v1/auth/register`：接收 username 和 email，规范化输入，固定创建 user，拒绝额外字段。此阶段仅登记内存用户，不代表已完成身份认证。
- `POST /api/v1/users`：兼容阶段二练习，允许省略 role 或传 user，拒绝客服和管理员角色。
- `GET /api/v1/health`：返回统一响应；`GET /health` 保持原有 status 结构。
- `PATCH /api/v1/tickets/{ticket_id}`：允许部分更新 title、description、priority；只允许 open 且 assignee_id 为空的工单。所有字段先验证，全部通过后一次保存。
- `GET /api/v1/tickets`：沿用 page、page_size、status、priority，增加 keyword 和 sort_order。keyword 去除首尾空白，忽略大小写匹配标题，或精确匹配数字 ID；空白关键字不筛选。sort_order 为 asc 或 desc，按 ID 排序，默认 desc。顺序为筛选、排序、统计 total、分页。

## Schema 与分层

采用 TicketCreate、TicketUpdate、TicketRead，并保留原请求和响应类名的兼容别名。输入统一拒绝额外字段、去除字符串首尾空白；邮箱使用 EmailStr。更新请求至少提交一个允许字段，显式 null 不合法。响应模型仅列出公开字段。

Router 负责 HTTP 和参数；Schema 负责数据形状；Service 负责筛选及修改规则；MemoryStorage 负责保存和读取。未来 Repository 可替代当前存储职责，本阶段不添加空壳抽象。

## 配置 日志与异常

Settings 从 backend/.env 和 HELPFLOW_ 环境变量读取应用名称与 CORS 来源，保留默认本地来源。配置以应用创建时读取，提供 .env.example。

请求中间件记录方法、路径、状态和耗时，响应提供 X-Process-Time；不记录请求体、查询串或认证头。HTTPException（包含未知 URL 和方法错误）统一为 code、message、data，保留必要响应头。参数错误保留安全字段位置、说明与类型；未知异常记录堆栈并返回通用 500。

## 验证与实现步骤

1. 补充配置、Schema、独立 auth 和 health 路由，接入应用。
2. 为 Service 增加搜索排序和原子式内容更新，Router 传递经过校验的数据。
3. 完成 HTTP 异常转换和请求耗时中间件。
4. 添加隔离的阶段三接口测试，验证注册固定角色、重复邮箱、字段校验、局部更新、不允许编辑时的 409、失败不改变存储、筛选和分页顺序、异常脱敏及配置行为。
5. 运行全部阶段二与阶段三测试，更新 Apifox 学习指南和项目文件关系图。

不创建 Git 提交；所有变更留在工作区供用户查看。
