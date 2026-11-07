import asyncio
import hashlib
import json
from typing import Literal
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from app.db.session import SessionDependency
from app.dependencies import CurrentUser
from app.models import Ticket, Comment, User, Activity
from app.models.knowledge import KnowledgeDocument
from app.errors import AppError
from app.schemas import ApiResponse
from app.services.rag_provider import ModelProvider
from app.services.knowledge import retrieve
from app.pagination import EntityId

router = APIRouter(prefix="/tickets", tags=["reply-assistant"])


class Source(BaseModel):
    chunk_id: str
    document_id: str
    version: int
    title: str
    content: str
    score: float


class Suggestion(BaseModel):
    status: Literal["ok", "insufficient_evidence"]
    draft: str = Field(max_length=2000)
    sources: list[Source]


async def context_snapshot(session, ticket_id, user_id):
    async with session.begin():
        user = await session.get(User, user_id, populate_existing=True)
        ticket = await session.get(Ticket, ticket_id, populate_existing=True)
        if not user or not user.is_active or user.role != "agent" or not ticket or ticket.assignee_id != user.id:
            raise AppError(403, 40002, "仅当前负责客服可以生成建议")
        if ticket.status == "closed":
            raise AppError(409, 40014, "工单已关闭")
        comments = (await session.scalars(select(Comment).where(Comment.ticket_id == ticket_id, Comment.visibility == "public").order_by(Comment.id.desc()).limit(8))).all()
        latest_activity = await session.scalar(select(Activity.id).where(Activity.ticket_id == ticket_id).order_by(Activity.id.desc()).limit(1))
        content = {"title": ticket.title, "description": ticket.description[:5000],
                   "comments": [{"id": c.id, "content": c.content[:1000]} for c in reversed(comments)]}
        signature = hashlib.sha256(json.dumps([content, ticket.status, ticket.assignee_id, latest_activity, user.password_hash], ensure_ascii=False).encode()).hexdigest()
        return content, signature


@router.post("/{ticket_id}/reply-suggestion", response_model=ApiResponse[Suggestion])
async def suggest(ticket_id: EntityId, request: Request, session: SessionDependency, user: CurrentUser):
    active = request.app.state.rag_active
    user_id = user.id
    if user_id in active or len(active) >= 4:
        raise AppError(429, 50019, "正在生成建议，请稍后重试")
    active.add(user_id)
    try:
        content, fingerprint = await context_snapshot(session, ticket_id, user_id)
        provider = ModelProvider(request.app.state.settings)
        provider.configured("generation")
        provider.configured("embedding")
        async with asyncio.timeout(request.app.state.settings.rag_timeout * 2 + 5):
            sources = await retrieve(session, provider, json.dumps(content, ensure_ascii=False), request.app.state.settings)
            result = await provider.generate(content, sources) if sources else {"status": "insufficient_evidence", "draft": "", "sources": []}
        _, current = await context_snapshot(session, ticket_id, user_id)
        if fingerprint != current:
            raise AppError(409, 40015, "工单内容或权限已变化，请刷新后重新生成")
        async with session.begin():
            for source in sources:
                doc = await session.get(KnowledgeDocument, source["document_id"], populate_existing=True)
                if not doc or doc.active_version != source["version"]:
                    raise AppError(409, 40016, "参考资料已更新，请重新生成")
        return ApiResponse(data=Suggestion.model_validate(result))
    except TimeoutError:
        raise AppError(504, 50020, "生成建议超时，请稍后重试") from None
    finally:
        active.discard(user_id)
