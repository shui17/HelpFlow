from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class StrictInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class CreateTask(StrictInput):
    request_id: str = Field(min_length=8, max_length=64, pattern=r'^[a-zA-Z0-9_-]+$')
    mode: Literal['internal_summary','public_reply']
    instruction: str = Field(min_length=1, max_length=2000)


class ProposalVersion(StrictInput):
    version: int = Field(ge=1)


class EditProposal(ProposalVersion):
    content: str = Field(min_length=1, max_length=2000)


class EmptyTool(StrictInput):
    pass


class ReadRecords(StrictInput):
    before_id: int | None = Field(default=None, gt=0)


class SearchKnowledge(StrictInput):
    query: str = Field(min_length=1, max_length=2000)


class Propose(StrictInput):
    content: str = Field(min_length=1, max_length=2000)
    citations: list[str] = Field(default_factory=list, max_length=8)


class Finish(StrictInput):
    message: str = Field(min_length=1, max_length=2000)
    needs_input: bool = False


TOOL_MODELS = {'get_ticket':EmptyTool,'read_records':ReadRecords,'search_knowledge':SearchKnowledge,
               'propose_action':Propose,'finish':Finish}
DESCRIPTIONS = {
    'get_ticket':'查询绑定工单的标题、描述、状态与负责人。执行提案前必须先查询。',
    'read_records':'分页查询绑定工单最近沟通记录；返回覆盖范围和更早游标。公开回复模式只返回公开记录。',
    'search_knowledge':'检索审核过的公开FAQ；公开回复提案必须引用本轮实际取得的chunk_id。',
    'propose_action':'仅提出当前模式对应的备注或公开回复草稿，不写入工单，需客服确认。事实不足时先澄清。',
    'finish':'结束只读查询或请求补充信息，不执行业务写入。'}


def tool_specs():
    return [{'type':'function','function':{'name':name,'description':DESCRIPTIONS[name],
             'parameters':model.model_json_schema()}} for name,model in TOOL_MODELS.items()]
