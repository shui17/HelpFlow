"""python -m scripts.import_knowledge ../knowledge --validate-only"""
import argparse
import asyncio
from pathlib import Path
from app.config import Settings
from app.db.session import create_database
from app.services.knowledge import parse_document, publish, deactivate
from app.services.rag_provider import ModelProvider


async def run(args):
    docs = []
    if args.path:
        path = Path(args.path)
        files = sorted(p for p in path.rglob("*") if p.suffix.lower() in (".md", ".txt")) if path.is_dir() else [path]
        docs = [parse_document(p) for p in files]
        if not docs:
            raise ValueError("未找到资料")
    if args.validate_only:
        print(f"Validated {len(docs)} documents, {sum(len(d['chunks']) for d in docs)} chunks; no model calls")
        return
    settings = Settings()
    engine, factory = create_database(settings.database_url.get_secret_value())
    try:
        async with factory() as session:
            if args.deactivate:
                await deactivate(session, args.deactivate)
                print("Deactivated")
            for doc in docs:
                print(doc["id"], await publish(session, ModelProvider(settings), doc))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--deactivate")
    args = parser.parse_args()
    if not args.path and not args.deactivate:
        parser.error("指定资料路径或 --deactivate 文档ID")
    if args.validate_only and args.deactivate:
        parser.error("校验与停用不能同时使用")
    asyncio.run(run(args))
