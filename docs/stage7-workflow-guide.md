# 阶段七：工单业务、并发领取与时间线

本阶段承接阶段六 JWT 安全与权限，实现工单从创建到关闭的完整业务。此处沿用学习路线编号，与 PRD 整体开发阶段的编号不同。启动、数据库迁移和账号准备仍参考 stage5-database-guide.md、stage6-security-guide.md；已有五表支持本阶段，无新迁移。

## 接口

所有路径以 `/api/v1` 开头，全部需要 `Authorization: Bearer <access_token>`。

| 方法 | 路径 | 请求体与规则 |
| --- | --- | --- |
| POST | /tickets/{id}/cancel | 无请求体；创建者撤销 open 且未分配工单 |
| POST | /tickets/{id}/claim | 无请求体；启用客服领取 open 且未分配工单 |
| POST | /tickets/{id}/assign | `{"assignee_id": 3}`；管理员分配或重新分配至启用客服 |
| POST 或 PATCH | /tickets/{id}/status | `{"status":"in_progress"}`；按角色及状态规则流转 |
| GET | /tickets/{id}/activities | 有权查看该工单的用户获取时间线 |

新操作成功返回 HTTP 200 和统一响应外壳，创建工单及回复仍返回 201。缺少 Token 返回 401，角色或归属不符返回 403，不存在工单返回 404，业务冲突返回 409，参数校验失败返回 422。

工单返回数据增加 `updated_at`、`assigned_at`、`closed_at`，时间采用 UTC。领取、分配仅改变负责人和分配时间，不自动开始处理。重复分配给同一客服返回 409。closed 工单不能修改、回复、分配或重新打开。

## Apifox 手工验证

准备普通用户 A、B，客服 C、D，管理员 E，分别保存 Token。客服由管理员调整普通用户角色得到，管理员按阶段六初始化脚本创建。

1. A 创建工单并修改标题；活动列表应为 created、updated。B 查询工单与活动均应返回 403。
2. C 领取，确认状态仍为 open、负责人为 C、assigned_at 非空。D 再领取收到 409。A 此时修改或撤销收到 409。
3. E 分配给 D，确认状态不变，出现 reassigned，包含 C、D 的 ID；C 查询、回复或改状态被拒绝。
4. D 设置 in_progress 并回复，A 回复补充信息。D 设置 resolved。
5. A 设置 in_progress 重新打开，确认仍由 D 负责，活动为 reopened。
6. D 再次设置 resolved，A 设置 closed，确认 closed_at 非空。再次回复、分配或流转均返回 409。
7. E 和 A 查看活动列表；回复保持独立，不出现在活动列表中。活动记录应包括操作人及状态、负责人前后值，并按时间、ID 升序。
8. A 新建另一工单后直接撤销；活动应为 created、cancelled。再撤销或领取返回 409。
9. E 对新工单首次分配，活动为 assigned。分配给普通用户、禁用客服、不存在账号或当前负责人应失败，不新增活动。

并发验证：为 C、D 分别配置 Token，同时发起对同一新工单的 claim。必须一方 200、一方 409，工单只有一个负责人，只有一条 claimed 日志。先后点击只能验证重复领取；自动测试使用两个独立数据库 Session 并发执行。

## 事务与锁

领取使用数据库条件 UPDATE，根据影响行数判断成功；不是先查后普通更新。分配、撤销、修改及状态流转使用工单行锁。分配和领取还锁定目标客服用户行，与用户管理的禁用、降级共用行锁。所有业务变化和活动日志在同一事务中提交；日志插入或提交失败，负责人、状态和日志全部回滚。

读取时间线复用工单可见性规则。活动返回字段为 id、ticket_id、action、operator_id、old_status、new_status、old_assignee_id、new_assignee_id、description、created_at；不存在对应变化的前后值可以为空。不会为阶段七之前创建的工单自动补造历史日志。

## 自动验证

在 backend 中运行：

```powershell
uv run pytest -q
```

真实数据库测试需要显式设置 `HELPFLOW_TEST_DATABASE_URL`，驱动必须是 mysql+asyncmy，数据库名必须以 `helpflow_stage5_test` 开头。测试库需预先创建，测试会运行迁移、插入测试账号和工单，阶段五回归还会执行迁移升降级；不要指向业务库。未配置时数据库用例会跳过。

```powershell
$env:HELPFLOW_TEST_DATABASE_URL = 'mysql+asyncmy://<test-user>:<password>@127.0.0.1:3306/helpflow_stage5_test_stage7'
uv run pytest -q tests/test_stage7_workflow.py
```

阶段七用例覆盖完整请求流程、三角色权限、分配目标校验、并发领取唯一成功、失败操作无日志，以及日志插入失败和提交失败后的回滚。
