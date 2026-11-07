"""实际 Embedding 检索评测；不把命中率当作回答准确率。"""
import asyncio
import json
from pathlib import Path
from app.config import Settings
from app.db.session import create_database
from app.services.rag_provider import ModelProvider
from app.services.knowledge import retrieve


async def main():
    settings = Settings()
    engine, factory = create_database(settings.database_url.get_secret_value())
    cases = json.loads((Path(__file__).parents[2] / 'knowledge/evaluation.json').read_text(encoding='utf-8'))
    try:
        async with factory() as session:
            for case in cases:
                sources = await retrieve(session, ModelProvider(settings), case['question'], settings)
                found = [s['document_id'] for s in sources]
                print(json.dumps(case | {'retrieved':found,'retrieval_pass':case['expected'] in found if case['expected'] else not found}, ensure_ascii=False))
    finally:
        await engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())
