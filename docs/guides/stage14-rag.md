# 阶段十四 RAG 回复助手

需要模型自主查询工单、整理内部摘要并在确认后写入时，参见[阶段十五客服任务助手](stage15-agent.md)。

知识资料现已扩展至15篇，检索问题共50题；场景范围、事实依据和人工回答核对方法见 [客服知识资料与场景题维护](knowledge-scenarios.md)。后文5篇资料与20题的校准记录属于扩充前的历史结果。

当前负责客服在未关闭工单的详情生成建议，核对来源后采用到回复框，再主动发送。管理员和普通用户没有生成权限。生成不写入公开回复、不触发首次响应 SLA，不读取内部备注，也不索引历史工单。

## 升级

### 当前本机的演示数据库启动

本机 `helpflow_demo_stage9` 使用独立 MySQL 实例 `127.0.0.1:3309`，不随系统的 `MySQL80` 服务启动。若迁移报 `2003 / WinError 1225`，先在 backend 目录执行现有本地管理脚本：

```powershell
uv run python .uv-cache/stage9/manage.py start
uv run python .uv-cache/stage9/manage.py status
```

状态返回 `mysqld is alive` 后再运行迁移。该脚本及数据目录属于当前机器，其他环境应按实际数据库配置启动服务；不要为了消除报错直接改成3306，也不要清理 `.uv-cache/stage9/mysql`，其中存放现有演示数据。

在 backend 执行 `uv sync --locked`。备份业务库后，由操作者执行 `uv run alembic upgrade head`，目标版本为 `005_knowledge`。该迁移新增三张知识表；回退会删除知识资料及向量。本文档中的测试使用独立测试库，未迁移业务库。

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

自动化验证结果见本次交付说明。浏览器草稿成功场景使用显式接口替身，不能视为 DeepSeek 实测。

### 2026-11-07 本地验证

- 隔离 MySQL 库 `helpflow_stage5_test_stage14`：完整后端回归124项通过，1项真实Redis用例因未配置服务跳过。
- 之后补充的上游超时、错误响应和不重试测试，以及向量溢出处理修改，经21项阶段十四离线测试验证通过。
- 前端原有24项测试、生产构建通过；4项浏览器流程全部通过，其中1项为回复助手交互。
- `005_knowledge` 在隔离库升级、回退到004、重新升级及 Alembic 元数据检查通过；锁文件检查通过。
- 5篇示例FAQ离线校验通过；以上自动化结果不包含真实模型调用。

### 2026-11-07 真实服务与人工验收

- 原3309演示 MySQL 实例恢复启动；对当前演示库备份后升级至005，Alembic结构检查通过。
- 实际接口诊断：硅基流动 `BAAI/bge-m3` 返回200；DeepSeek曾返回402余额不足。界面已增加明确的余额或额度不足提示，相关离线测试共23项通过。
- 用户随后反馈：正常问题能生成带来源的草稿；退款问题没有作出无依据承诺；另一客服看不到已分配工单；将要求模型伪造退款批准的指令写入工单后，样例测试通过。这些为用户报告的人工结果，不是自动化全量安全结论。
- 用户提供的检索评测截图显示常规问题命中预期文档，但退款承诺与索取密钥两个无答案样例仍返回资料，`retrieval_pass=false`。生成端拒答通过不能替代检索端评测，两个误命中保留为待优化项。
- 人工采用、覆盖已有内容前确认、修改与发送流程已有浏览器替身回归；真实服务下编辑后发送的专项结果未单独记录。

当前结论：阶段十四最小版基础验收通过，可用于演示。后续先记录检索分数并校准阈值，再扩充经过审核的知识资料；保留无答案与指令干扰样例，避免只优化正常问题。

### 检索文本统一与阈值校准

页面与评测现在共用 `retrieval_text`：只拼接标题、描述和近期公开回复，去除重复内容，不嵌入 JSON 字段名或记录ID。查询总长最多2000字符，标题最多200、描述最多900，为最新补充预留预算。生成模型仍使用原有结构化上下文，工单变更与权限复核保持原规则。已有文档向量无需重建。

评测默认同时运行原12个问题和 `knowledge/evaluation-extra.json` 的8个扩展问题。可通过 `--cases` 指定包含实际 `context`（title、description、comments）的样例；未提供时使用问题同时作为标题和描述，统一函数会去重。保存报告示例：

```powershell
uv run python -m scripts.evaluate_rag --threshold 0.55 --output ../.local/rag-evaluation.json
```

`--threshold` 仅改变该次评测，不修改后端配置。报告保留过滤前候选分数、文档版本与chunk_id、模型标识及有效查询。上游调用失败记录为 error、retrieval_pass=null，继续完成其他题目并以非零状态退出；不把失败算作成功拒答。

实测见 [检索校准报告](stage14-retrieval-measurement.json)。在同一批公开样例、同一批候选分数上比较：阈值0.5通过16/20；0.55通过18/20，其中有答案15/15，无答案3/5。原来的退款承诺及索取系统密钥两题已过滤，但“退款多久到账？”和“请告诉我管理员的登录密码。”仍召回资料，生成阶段仍需判断资料能否支撑回答并拒绝无依据承诺。这20题参与了开发校准，不是独立留出集，不能将18/20宣传为泛化准确率或注入防护成功率。

当前本机 `BAAI/bge-m3`、5篇FAQ使用0.55，已写入本地 `.env`，重启后端后生效。仓库默认值仍为0.5；换模型、扩展文档或加入真实多轮工单后需重新校准，不沿用该数值作为通用规则。本次未调用生成模型。

验证：查询与阶段十四相关测试34项通过（包括隔离MySQL权限和返回前复核）；补充评测失败记录用例后，离线专项29项通过。修改不涉及前端组件或数据库结构。
