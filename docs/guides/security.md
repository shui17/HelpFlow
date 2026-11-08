# HelpFlow 身份认证、权限与安全

本文说明账号注册与登录、JWT、角色权限和管理员初始化。

## 启动

在 backend 目录执行 `uv sync --locked`，复制 `.env.example` 为 `.env`，填入数据库连接。使用 `python -c "import secrets; print(secrets.token_urlsafe(48))"` 在本地生成随机密钥，填入 `HELPFLOW_JWT_SECRET_KEY`。密钥至少 32 字节，无默认值；缺少时应用启动失败。不要提交 `.env`。

执行 `uv run alembic upgrade head`，再执行 `uv run python -m scripts.init_admin --username 管理员 --email admin@example.com`，通过隐藏输入设置密码。脚本重复执行不会重置现有管理员，也不会将既有普通用户自动升级。早期数据中的无效占位密码不能登录，请注册新账号；已有数据保持不变。

执行 `uv run uvicorn app.main:app --reload`。启动前应执行全部数据库迁移。

## Apifox 验证

环境设置 `base_url=http://localhost:8000/api/v1`，以及 `user_token`、`agent_token`、`admin_token`。

1. `POST {{base_url}}/auth/register`：发送 `username`、`email`、`password`、`confirm_password`。用户名 2–30 字；密码 8–64 字，至少含字母和数字；密码空白原样保留。禁止提交 role、is_active 等字段。
2. `POST /auth/login`：JSON 发送 email、password，返回 `data.access_token`、`token_type=bearer`、`expires_in=7200`。在 Apifox 后置脚本中可使用 `pm.environment.set("user_token", pm.response.json().data.access_token)`；另两角色分别保存到对应变量。
3. 后续请求使用 Bearer `{{user_token}}`。`GET /auth/me` 返回数据库当前身份。管理员登录后使用 `PATCH /users/{id}/role`，提交 `{"role":"agent"}` 将新注册账号设为客服。
4. `POST /tickets` 只发送 title、description、priority；`POST /tickets/{id}/comments` 只发送 content。creator_id、author_id 从登录身份取得，提交伪造 ID 返回 422。
5. 注册第二个普通用户，尝试访问第一个用户的详情、修改和回复，均应 403。列表仅显示本人数据。客服可查看 open 且无负责人的工单或自己负责的工单；处理和回复仅允许当前负责人。管理员可查看全部工单，但不能回复或改变处理结果。
6. 管理员使用 `GET /users?page=1&page_size=10&role=agent&is_active=true` 查询用户，支持 keyword 搜索用户名或邮箱。`GET /users/{id}` 查询单个用户。普通用户访问这些接口返回 403。
7. `PATCH /users/{id}/status` 提交 `{"is_active":false}`；目标账号即使持有未过期 Token，下一次请求也返回 403/20003。不能禁用自己，不能修改管理员角色，不能降级或禁用仍有未关闭工单的客服。角色、状态修改与用户管理日志同事务提交；重复设置原值不新增日志。
8. `PATCH /auth/password` 提交 current_password、new_password、confirm_password。成功后所有旧 Token 返回 401，使用新密码重新登录。后端通过密钥 HMAC 绑定密码版本，Token 不携带密码哈希。
9. 缺少、伪造、过期 Token 均返回 401/20002 和 WWW-Authenticate: Bearer；登录密码错误为 401/20001，当前密码错误为 400/20004。

登录邮箱转小写，未知邮箱与错误密码返回相同提示。响应 Schema 不暴露 password_hash；参数错误不回显输入值。密码计算在线程池中执行，避免阻塞异步事件循环。JWT 固定 HS256，强制校验 sub、role、iat、exp、pwdv；权限使用数据库当前角色。认证查询事务在业务写事务之前结束。

## 代码职责与权限边界

`app/security.py` 负责密码和 JWT，`app/dependencies.py` 负责认证和角色依赖，`app/services/tickets.py` 负责工单归属，`app/services/users.py` 负责管理限制和事务。原公开 `POST /users` 已移除，注册统一使用 `/auth/register`。状态修改保留既有 PATCH 路径。

客服领取、管理员分配、撤销及工单时间线见 [工单流程](ticket-workflow.md)。管理员不可通过普通用户管理接口创建其他管理员。改密会撤销旧 Token；账号禁用期间 Token 被拒绝，重新启用后仍未过期且密码未改变的 Token 可继续使用。

## 自动验证

在 backend 目录运行 `uv run pytest -q`。不指定数据库时，真实数据库用例跳过。设置 `HELPFLOW_TEST_DATABASE_URL` 后会运行隔离 MySQL 集成测试，只允许 `mysql+asyncmy` 且库名以 `helpflow_stage5_test` 开头。该测试库应为空或专用于测试，迁移测试会执行字段降级与升级。

早期 HTTP 测试显式替换身份与 Service，仅验证传输层；`tests/test_security.py` 通过真实认证、真实 Service 和 MySQL 验证权限与事务。实现参考 [PyJWT 使用文档](https://pyjwt.readthedocs.io/en/latest/usage.html) 和 [pwdlib API](https://frankie567.github.io/pwdlib/reference/pwdlib/)。
