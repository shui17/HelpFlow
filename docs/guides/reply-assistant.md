# RAG 回复助手

需要模型自主查询工单、整理内部摘要并在确认后写入时，参见[客服任务助手](task-assistant.md)。


当前负责客服在未关闭工单的详情生成建议，核对来源后采用到回复框，再主动发送。管理员和普通用户没有生成权限。生成不写入公开回复、不触发首次响应 SLA，不读取内部备注，也不索引历史工单。

## 数据库准备

备份数据库后，在 backend 目录执行 `uv sync --locked`、`uv run alembic upgrade head` 和 `uv run alembic check`。知识表对应迁移 `005_knowledge`，实际部署应升级到当前 head；回退会删除知识资料与向量。

## 模型配置

按 `.env.example` 将生成和 Embedding 的 URL、模型、Key 分别填入本地 `.env`。DeepSeek 用于生成；Embedding 服务须另行提供兼容 `/embeddings` 的接口。URL 应包含供应商要求的 `/v1` 前缀，程序仅追加 `/embeddings` 或 `/chat/completions`。官方 DeepSeek 默认地址无需 `/v1`。

密钥只保留在后端，不发到聊天、不提交 Git。尚无凭据时应用可启动，生成按钮返回明确配置提示，人工回复仍可用。不会用假回复模拟上线成功。

生成请求采用非思考模式和 JSON 输出，参数依据 [DeepSeek 官方 Chat Completions 文档](https://api-docs.deepseek.com/api/create-chat-completion/)。供应商兼容性仍以真实调用结果为准。

## 资料管理

从 backend 执行：

```powershell
uv run python -m scripts.import_knowledge ../knowledge --validate-only
uv run python -m scripts.import_knowledge ../knowledge
uv run python -m scripts.import_knowledge --deactivate login-failed
uv run python -m scripts.evaluate_rag
```

校验不连接模型或数据库。在线导入调用 Embedding，可能产生供应商费用。Markdown 使用简单元数据头，TXT 使用同名 JSON 元数据文件；必填 id、title、version、status=approved、audience=public。示例位于根目录 knowledge。

同版本同内容重复导入跳过；同版本内容或模型变化拒绝。更新时增加版本，全部向量成功后才切换有效版本。停用后重复导入旧版本不会重新激活，需发布新版本。切换向量服务或模型后需对所有有效文档提高版本重新导入；不要在重建完成前使用生成入口。

向量由 MySQL JSON 保存，小规模检索使用应用内余弦相似度。最多检索1000个有效分块，超过时明确报错；Top K 默认4、阈值默认0.5，须根据真实模型评测校准。相似度并非正确概率。第一版并发限制为每进程4个、每用户1个在途请求，多进程部署应在网关增加共享限流。

## 接口与验证

`POST /api/v1/tickets/{id}/reply-suggestion` 无请求正文；返回统一响应中的 status、draft、sources。status 为 ok 或 insufficient_evidence。来源含文档ID、版本、chunk_id、标题、片段和相似度。生成前后检查权限与上下文变化，引用只能来自本次检索。资料内容和工单正文视为不可信输入，仍须人工核对草稿。

固定评测集在 `knowledge/evaluation.json`。评测命令输出真实 Embedding 检索命中情况，不等于生成答案准确率；需另外人工核对草稿与依据、拒答和注入样例。真实模型已完成下述基础人工验证，token 使用、调用耗时与系统性质量指标尚未测量。


## 质量与容量边界

检索阈值需针对实际模型和知识资料校准，开发样例不能代替独立评估。当前仍存在无答案问题召回相关但不足以作答的资料的情况；客服必须核对正文依据，拒绝无依据的承诺。更换模型或扩充知识后应重新评估。检索上限、并发限制和供应商错误处理见上文配置。
