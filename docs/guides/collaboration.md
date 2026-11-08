# 客服协作与通知运行指南

客服协作功能包含客服转交、内部备注、持久化通知及聚合统计复用。升级范围和事务设计见 升级需求，接口契约见 [OpenAPI](../api/helpflow.openapi.json)。

## 升级与演示

先备份业务数据库，在 backend 执行 `uv run alembic upgrade head` 和 `uv run alembic check`，然后重新启动后端和前端。协作功能对应迁移 `003_collaboration`；当前部署应升级至 head，包含后续迁移。已有回复保持公开；已有业务记录不会补发历史通知。

在专用 helpflow_demo 前缀演示库运行 `uv run python -m scripts.seed_demo`，会在原有演示数据外增加“演示：客服协作转交”，包含内部备注、转交原因、新负责人回复和通知。已有账号密码及同名工单不覆盖。客服二可继续处理该工单；客服一转交后不能再访问。

浏览器演示：用户新建工单 → 客服一领取 → 添加内部备注 → 转交给客服二并填写原因 → 客服二从站内通知进入 → 查看内部备注 → 开始处理、公开回复、标记解决 → 用户从通知进入并确认关闭。用户界面不显示内部备注或转交原因。通知页支持加载更早记录、标记已读和工单跳转。

## 接口

以下路径均加 `/api/v1` 前缀，均要求登录。

| 方法与路径 | 输入或结果 | 权限 |
| --- | --- | --- |
| GET /tickets/agents | keyword、limit；只返回 id、username | 客服、管理员 |
| POST /tickets/{id}/transfer | assignee_id、reason | 当前负责客服 |
| GET /tickets/{id}/notes | before_id、limit；默认最近50条，页内升序 | 当前负责客服、管理员 |
| POST /tickets/{id}/notes | content，1至2000字 | 当前负责客服、管理员，未关闭 |
| GET /notifications | before_id、limit；默认最近20条，倒序 | 本人通知 |
| GET /notifications/unread-count | 未读整数 | 本人通知 |
| PATCH /notifications/{id}/read | 返回通知及首次 read_at | 本人通知，可重复 |
| GET /tickets/summary | counts 与最多5条 recent | 当前角色数据范围 |

列表 limit 最大100。自转交返回400；空白原因返回422；关闭或负责人已变化返回409；非法目标账号返回409。无权读取内部备注返回403，访问他人的通知已读接口返回404。

## 自动验证

在进程环境设置独立 `HELPFLOW_TEST_DATABASE_URL`，库名必须以 helpflow_stage5_test 开头。禁止使用业务库或演示库。

```powershell
cd backend
uv run pytest -q --tb=short
uv run python -m tests.seed_browser
cd ../frontend
npm test
npm run build
npm run test:e2e
```

新增 tests/test_stage12.py 验证隐私、转交竞争、通知去重和事务回滚。迁移往返测试会创建、迁移并删除随机命名的 helpflow_stage5_test_migration_ 临时库，测试账号需要拥有创建和删除测试库的权限。浏览器初始化新增 browser-agent2@example.com，默认密码仍为 BrowserTest123；配置和端口沿用 README。
