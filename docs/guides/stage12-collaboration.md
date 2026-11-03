# 阶段12运行与验证

阶段12代码包含客服转交、内部备注、持久化通知及聚合统计复用。升级范围和事务设计见 [升级需求](../upgrades/v1.1-collaboration-requirements.md)，接口契约见 [OpenAPI](../api/helpflow.openapi.json)。

## 升级与演示

先备份业务数据库，在 backend 执行 `uv run alembic upgrade head` 和 `uv run alembic check`，然后重新启动后端和前端。迁移版本应为 003_collaboration。已有回复保持公开；已有业务记录不会补发历史通知。

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

## 统计测量

在 backend 执行以下命令。脚本仅接受显式测试库，创建临时测量用户及250张工单，预热后交替测量五轮，最后删除本次测量数据。输出不包含连接凭据。

```powershell
uv run python -m scripts.benchmark_summary --tickets 250
```

输出 docs/guides/stage12-summary-measurement.json，包含分页遍历与聚合的请求数、响应体字节、每轮及中位耗时、状态数一致性检查、三条概览 SQL 的 EXPLAIN。测量通过进程内 TestClient 发起 HTTP 请求，包含真实本机 MySQL 往返，传输量仅为未压缩响应体；不能当作外部网络或高并发负载测试结果。当前仓库在本次开发前已使用聚合接口，因此基线为重现分页遍历方式，不宣称阶段12首次引入聚合。

2026-11-03 本机 MySQL 8.0.46，250张工单、每页100条，预热后交替测量五轮。两种方式状态数量完全一致。

| 方式 | HTTP请求数 | 响应体总字节 | 五轮中位耗时 |
| --- | --- | --- | --- |
| 遍历全部分页 | 3 | 184391 | 20.898 ms |
| 聚合及最近5条 | 1 | 3841 | 5.341 ms |

原始记录见 [测量与查询计划](stage12-summary-measurement.json)。状态计数使用 ix_tickets_creator_created，EXPLAIN 显示 Using temporary；最近工单查询使用同一索引并出现 Using filesort。该小样本不足以证明所有数据规模都可省略排序或临时表，也不证明并发吞吐量。

## 本次验证状态

2026-11-03，在隔离 MySQL 8.0.46 中完成最终验证。

| 检查 | 结果 |
| --- | --- |
| 后端全量测试 | 86项通过、无跳过，包含7项阶段12用例 |
| 迁移 | 独立空库升级、回退至001、重新升级及 Alembic 元数据一致性检查通过 |
| 前端单元测试 | 21项通过 |
| 前端生产构建 | 成功 |
| Chrome 浏览器流程 | 2项通过：原三角色闭环、阶段12备注与转交通知闭环 |
| SQL 聚合测量 | 250张工单，五轮状态统计一致，实测及 EXPLAIN 已保存 |

测试修复了 MySQL 秒级 DATETIME 与首次已读响应微秒不一致的问题，重复已读返回同一时间。浏览器验证覆盖转交后旧负责人无法访问、新负责人读取历史备注和回复、普通用户仅看到公开内容并关闭工单；同时修复客服搜索加载时输入控件被卸载的问题。

验证使用专用测试库，未迁移现有业务库。本地验证不等于远端 CI 已运行；远端结果以提交后的 Actions 为准。
