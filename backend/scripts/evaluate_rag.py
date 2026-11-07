"""实际 Embedding 检索评测；不把命中率当作回答准确率。"""
import asyncio
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from app.config import Settings
from app.db.session import create_database
from app.services.rag_provider import ModelProvider
from app.services.knowledge import retrieve, retrieval_text
from app.errors import AppError


def evaluate_case(case, sources, threshold, top_k):
    selected = [s for s in sources if s['score'] >= threshold][:top_k]
    found = [s['document_id'] for s in selected]
    return case | {'retrieved':found,
        'retrieval_pass':case['expected'] in found if case['expected'] else not found,
        'candidate_scores':[{k:s[k] for k in ('document_id','version','chunk_id','score')} for s in sources]}


async def main(args):
    settings = Settings()
    threshold = settings.rag_min_score if args.threshold is None else args.threshold
    if not -1 <= threshold <= 1:
        raise ValueError('阈值必须在[-1,1]内')
    engine, factory = create_database(settings.database_url.get_secret_value())
    provider = ModelProvider(settings)
    scoring = settings.model_copy(update={'rag_min_score':-1, 'rag_top_k':8})
    rows = []
    try:
        async with factory() as session:
            for file in args.cases:
                for case in json.loads(Path(file).read_text(encoding='utf-8')):
                    context = case.get('context', {'title':case['question'], 'description':case['question'], 'comments':[]})
                    query = retrieval_text(context)
                    try:
                        sources = await retrieve(session, provider, query, scoring)
                        result = evaluate_case(case, sources, threshold, settings.rag_top_k)
                    except AppError as error:
                        result = case | {'retrieval_pass':None, 'error_code':error.code,
                                         'error':error.message, 'candidate_scores':[]}
                    result.update({'query':query, 'dataset':Path(file).name})
                    rows.append(result)
                    print(json.dumps(result, ensure_ascii=False), flush=True)
        summary = {'total':len(rows), 'passed':sum(r['retrieval_pass'] is True for r in rows),
            'errors':sum(r['retrieval_pass'] is None for r in rows),
            'answerable':sum(r['expected'] is not None for r in rows),
            'answerable_passed':sum(r['retrieval_pass'] is True for r in rows if r['expected'] is not None),
            'unanswerable':sum(r['expected'] is None for r in rows),
            'unanswerable_passed':sum(r['retrieval_pass'] is True for r in rows if r['expected'] is None)}
        report = {'measured_at':datetime.now(timezone.utc).isoformat(),
            'embedding_model':settings.rag_embedding_model, 'embedding_space':provider.space,
            'query_format':'public-text-v1', 'threshold':threshold, 'top_k':settings.rag_top_k,
            'summary':summary, 'results':rows}
        if args.output:
            Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print(json.dumps({'summary':summary, 'threshold':threshold}, ensure_ascii=False))
        if summary['errors']:
            raise SystemExit(1)
    finally:
        await engine.dispose()


if __name__ == '__main__':
    root = Path(__file__).parents[2] / 'knowledge'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', nargs='+', default=[str(root/name) for name in
        ('evaluation.json', 'evaluation-extra.json', 'evaluation-scenarios.json')])
    parser.add_argument('--threshold', type=float, help='仅本次评测使用，不修改应用配置')
    parser.add_argument('--output', help='保存含分数的 JSON 报告')
    asyncio.run(main(parser.parse_args()))
