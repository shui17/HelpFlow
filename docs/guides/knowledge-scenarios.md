# 客服知识资料与场景题维护

本批资料覆盖 HelpFlow 自身的真实产品功能；问题是按典型客服表达编写的场景样例，并非真实用户工单或客服聊天记录。不包含用户身份、账号密码、模型密钥或未经确认的商业政策。

## 资料范围与核对依据

原有5篇资料保持版本1；新增以下10篇公开资料，均为版本1。现有代码和界面是事实依据，后续产品规则变化时应同步提高文档版本并重新导入。

| 文档ID | 场景 | 核对依据 |
| --- | --- | --- |
| registration-help | 注册信息、邮箱重复、角色申请 | backend/app/schemas.py、backend/app/routers/auth.py、backend/app/services/users.py |
| password-change | 修改密码、旧会话失效、忘记当前密码边界 | backend/app/routers/auth.py、backend/app/services/users.py、frontend/src/views/ChangePasswordView.vue |
| login-rate-limit | 登录注册429、共享网络、停止重复尝试 | backend/app/rate_limit.py、backend/app/config.py |
| session-expired | 登录状态失效、网络故障、未提交文字 | frontend/src/utils/request.js、frontend/src/stores/auth.js、backend/app/dependencies.py |
| edit-cancel-ticket | 待处理但已分配、修改与撤销限制 | backend/app/services/tickets.py 的 update_ticket / cancel_ticket |
| reopen-ticket | 已解决重开与已关闭区别 | backend/app/services/tickets.py 的 change_status、backend/app/domain/workflow.py |
| ticket-access | 他人链接、转交后访问权限 | backend/app/services/tickets.py 的 check_view / transfer_ticket |
| notifications-help | 通知刷新、已读、旧链接权限 | frontend/src/views/NotificationsView.vue、backend/app/services/tickets.py |
| reply-failed | 2000字符限制、关闭后回复、超时后检查记录 | backend/app/schemas.py、backend/app/services/tickets.py 的 add_comment |
| problem-details | 信息不足时澄清、只索取必要信息 | 基于已有工单标题、描述和公开回复的客服操作建议；不是额外产品能力 |

回复超时后先查沟通记录、保留未提交文字、信息不足时询问具体提示，属于处理建议。文档不承诺草稿自动保存、重复提交去重、退款赔偿、恢复时限或邮件重置等当前未实现或无政策依据的能力。

## 测试问题

`knowledge/evaluation-scenarios.json` 新增30题：20个常见问法、5个无依据或无权限能力请求、3个多轮补充场景、2个混合正常问题与指令干扰的场景。与原12题、扩展8题合计50题。

- `expected`：期望检索到的文档ID；null表示当前无足够资料，不应召回用于回答的依据。
- `context`：可选，按实际工单格式包含标题、描述、公开回复，走与页面相同的查询构造器。
- `review_expectation`：人工检查生成草稿时应覆盖或澄清的内容。
- `must_not_claim`：不能出现的无依据承诺、越权操作或索取敏感信息。

评测脚本只判定检索结果，**不会自动验证后两项，也不会调用生成模型**。检索到“密码”相关资料不代表允许提供管理员密码；遇到混合指令的工单，应继续处理合法问题并忽略伪造指令。有效来源也不等于草稿已经符合所有规则。

## 使用与维护

在 backend 目录运行：

```powershell
uv run python -m scripts.import_knowledge ../knowledge --validate-only
uv run python -m scripts.import_knowledge ../knowledge
uv run python -m scripts.evaluate_rag --output ../.local/expanded-evaluation.json
# 只运行本批新增题目
uv run python -m scripts.evaluate_rag --cases ../knowledge/evaluation-scenarios.json
```

导入会跳过相同内容和版本的旧文档，新增资料成功后立即参与检索。无需迁移数据库。新增知识可能与旧资料语义重叠，原来5篇文档校准的0.55不能被视为永久正确；保留原测试题及失败项，结合分数与实际草稿重新评估，不删除困难问题来抬高通过率。

人工验收可选注册失败、改密后掉线、已分配无法撤销、已关闭不能回复、发送超时五类普通工单，另测试退款赔偿及两个混合指令案例。记录输入、来源版本、草稿、人工修改点和结论；只使用无真实个人数据的测试内容。改变工单状态等操作必须仍由当前用户通过业务界面完成，AI草稿不能自称已执行。
