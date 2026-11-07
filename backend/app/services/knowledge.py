"""资料解析、版本发布与有上限的精确向量检索。"""
import hashlib
import json
import re
from pathlib import Path
from sqlalchemy import select, and_, func
from sqlalchemy.dialects.mysql import insert
from app.models.knowledge import KnowledgeDocument as Document, KnowledgeVersion as Version, KnowledgeChunk as Chunk
from app.services.rag_provider import vector
from app.errors import AppError


def retrieval_text(context):
    """仅嵌入公开正文；为最新补充留预算，排除 JSON 字段和 ID。"""
    fields = [(context.get('title', ''), 200), (context.get('description', ''), 900)]
    fields.extend((c.get('content', ''), 800) for c in reversed(context.get('comments', [])))
    parts, seen, remaining = [], set(), 2000
    for value, limit in fields:
        value = value.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        separator = 1 if parts else 0
        length = min(limit, remaining - separator)
        if length <= 0:
            break
        parts.append(value[:length])
        remaining -= len(parts[-1]) + separator
    return '\n'.join(parts)


def parse_document(path):
    path = Path(path)
    if path.stat().st_size > 100_000:
        raise ValueError("文档不能超过100KB")
    raw = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() == ".md":
        match = re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n(.*)\Z", raw, re.S)
        if not match:
            raise ValueError("Markdown 需要元数据头")
        # 仅支持简单 key: value，不执行或解释 YAML 对象。
        meta = dict(line.split(":", 1) for line in match[1].splitlines() if line.strip())
        meta = {k.strip(): v.strip() for k, v in meta.items()}
        body = match[2].strip()
    elif path.suffix.lower() == ".txt":
        meta = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
        body = raw.strip()
    else:
        raise ValueError("仅支持 Markdown 或 TXT")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,99}", str(meta.get("id", ""))):
        raise ValueError("文档ID必须是小写字母、数字或连字符")
    if meta.get("status") != "approved" or meta.get("audience") != "public":
        raise ValueError("仅导入审核通过的公开资料")
    version = int(meta.get("version", 0))
    title = str(meta.get("title", "")).strip()
    if not 1 <= version <= 2_147_483_647 or not 1 <= len(title) <= 200 or not body:
        raise ValueError("标题、版本或正文无效")
    chunks = []
    for section in re.split(r"\n(?=##? )|\n\s*\n", body):
        for start in range(0, len(section), 800):
            text = section[start:start+800].strip()
            if text:
                chunks.append(text)
    digest = hashlib.sha256(json.dumps([title, body], ensure_ascii=False).encode()).hexdigest()
    return {"id": meta["id"], "version": version, "title": title, "digest": digest, "chunks": chunks}


def active_query():
    return select(Chunk, Version).join(Document, Document.id == Chunk.document_id).join(Version,
        and_(Version.document_id == Chunk.document_id, Version.version == Chunk.version)).where(Document.active_version == Chunk.version)


async def publish(session, provider, doc):
    key = (doc["id"], doc["version"])
    async with session.begin():
        existing = await session.get(Version, key)
        if existing:
            if existing.digest != doc["digest"] or existing.embedding_space != provider.space:
                raise ValueError("版本内容或向量模型已变化，请提高文档版本")
            return "unchanged"
    vectors = [await provider.embed(text) for text in doc["chunks"]]
    if len({len(v) for v in vectors}) != 1:
        raise ValueError("向量维度不一致")
    async with session.begin():
        # 锁定文档，包括并发首次导入；唯一键使重放可安全收敛。
        await session.execute(insert(Document).values(id=doc["id"]).on_duplicate_key_update(id=doc["id"]))
        parent = await session.scalar(select(Document).where(Document.id == doc["id"]).with_for_update().execution_options(populate_existing=True))
        existing = await session.get(Version, key)
        if existing:
            if existing.digest != doc["digest"] or existing.embedding_space != provider.space:
                raise ValueError("同版本内容冲突")
            return "unchanged"
        maximum = await session.scalar(select(func.max(Version.version)).where(Version.document_id == doc["id"]))
        if maximum is not None and doc["version"] <= maximum:
            raise ValueError("新版本必须大于已有版本")
        session.add(Version(document_id=doc["id"], version=doc["version"], title=doc["title"], digest=doc["digest"], embedding_space=provider.space))
        for index, (content, embedding) in enumerate(zip(doc["chunks"], vectors)):
            chunk_id = hashlib.sha256(f'{doc["id"]}:{doc["version"]}:{index}:{content}'.encode()).hexdigest()
            session.add(Chunk(id=chunk_id, document_id=doc["id"], version=doc["version"], content=content, vector=embedding))
        parent.active_version = doc["version"]
    return "published"


async def deactivate(session, document_id):
    async with session.begin():
        doc = await session.get(Document, document_id, with_for_update=True)
        if doc is None:
            raise ValueError("文档不存在")
        doc.active_version = None


async def retrieve(session, provider, text, settings):
    async with session.begin():
        rows = (await session.execute(active_query().limit(1001))).all()
        if len(rows) > 1000:
            raise AppError(503, 50017, "知识库超过小规模检索上限，请联系管理员")
        candidates = [(c.id, c.document_id, c.version, v.title, c.content, c.vector, v.embedding_space) for c, v in rows]
    if not candidates:
        return []
    query = await provider.embed(text)
    ranked = []
    for cid, did, version, title, content, values, space in candidates:
        try:
            values = vector(values)
            if space != provider.space or len(values) != len(query):
                raise ValueError()
        except ValueError:
            raise AppError(503, 50018, "知识索引与当前模型不兼容，请重新导入新版本") from None
        score = sum(a*b for a, b in zip(query, values))
        if score >= settings.rag_min_score:
            ranked.append({"chunk_id": cid, "document_id": did, "version": version, "title": title, "content": content, "score": score})
    return sorted(ranked, key=lambda s: (-s["score"], s["chunk_id"]))[:settings.rag_top_k]
