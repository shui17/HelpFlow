"""在显式隔离测试库比较遍历分页与 SQL 聚合，输出实际数据及 EXPLAIN。"""
import argparse
import asyncio
from collections import Counter
import json
import os
from pathlib import Path
import secrets
from statistics import median
from time import perf_counter
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.config import Settings
from app.db.session import create_database
from app.main import create_app
from app.models import Ticket, User
from app.security import create_access_token


async def prepare(url, size):
    engine, factory = create_database(url)
    try:
        async with factory() as session, session.begin():
            user = User(username='统计测量用户', email=f'benchmark-{uuid4().hex}@example.com',
                        password_hash='!benchmark-no-login', role='user', is_active=True)
            session.add(user)
            await session.flush()
            for index in range(size):
                session.add(Ticket(ticket_no=uuid4().hex, title=f'统计测量 {index}',
                    description='固定长度测量内容' * 20, category='other', priority='normal',
                    status=('open', 'in_progress', 'resolved', 'closed')[index % 4], creator_id=user.id))
        async with engine.connect() as connection:
            plans = {}
            for name, sql in {
                'counts': 'SELECT status, COUNT(*) FROM tickets WHERE creator_id=:uid GROUP BY status',
                'unassigned': "SELECT COUNT(*) FROM tickets WHERE creator_id=:uid AND status='open' AND assignee_id IS NULL",
                'recent': 'SELECT * FROM tickets WHERE creator_id=:uid ORDER BY id DESC LIMIT 5',
            }.items():
                result = await connection.execute(text('EXPLAIN ' + sql), {'uid': user.id})
                plans[name] = [dict(row) for row in result.mappings()]
        return user, plans
    finally:
        await engine.dispose()


async def cleanup(url, user_id):
    from sqlalchemy import delete
    engine, factory = create_database(url)
    try:
        async with factory() as session, session.begin():
            await session.execute(delete(Ticket).where(Ticket.creator_id == user_id))
            await session.execute(delete(User).where(User.id == user_id))
    finally:
        await engine.dispose()


def measure(client, headers, aggregate):
    started = perf_counter()
    requests, payload_bytes, counts = 0, 0, Counter()
    page = 1
    while True:
        response = client.get('/api/v1/tickets/summary' if aggregate else '/api/v1/tickets',
            headers=headers, params={} if aggregate else {'page': page, 'page_size': 100})
        response.raise_for_status()
        requests += 1
        payload_bytes += len(response.content)
        data = response.json()['data']
        if aggregate:
            counts.update({key: data['counts'][key] for key in ('open', 'in_progress', 'resolved', 'closed')})
            break
        counts.update(row['status'] for row in data['items'])
        if page * 100 >= data['total']:
            break
        page += 1
    return {'requests': requests, 'response_body_bytes': payload_bytes,
            'elapsed_ms': round((perf_counter() - started) * 1000, 3), 'counts': dict(counts)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tickets', type=int, default=250)
    parser.add_argument('--output', type=Path, default=Path('../docs/guides/stage12-summary-measurement.json'))
    args = parser.parse_args()
    url = os.environ['HELPFLOW_TEST_DATABASE_URL']
    parsed = make_url(url)
    if parsed.drivername != 'mysql+asyncmy' or not (parsed.database or '').startswith('helpflow_stage5_test'):
        parser.error('仅允许显式 helpflow_stage5_test 前缀 MySQL 测试库')
    if not 1 <= args.tickets <= 10000:
        parser.error('--tickets 必须在 1 到 10000 之间')
    user, plans = asyncio.run(prepare(url, args.tickets))
    try:
        settings = Settings(_env_file=None, database_url=url, jwt_secret_key=secrets.token_urlsafe(48))
        headers = {'Authorization': 'Bearer ' + create_access_token(user, settings)}
        with TestClient(create_app(settings)) as client:
            # 两种方式预热后交替测量五轮，包含应用内认证和本机数据库往返。
            measure(client, headers, False)
            measure(client, headers, True)
            baseline, aggregate = [], []
            for _ in range(5):
                baseline.append(measure(client, headers, False))
                aggregate.append(measure(client, headers, True))
            assert all(row['counts'] == baseline[0]['counts'] for row in baseline + aggregate)
        report = {'tickets': args.tickets, 'role': 'user', 'rounds': 5,
            'method': 'In-process TestClient HTTP; response bodies exclude headers and compression',
            'baseline': baseline, 'aggregate': aggregate,
            'median_ms': {'baseline': median(row['elapsed_ms'] for row in baseline),
                          'aggregate': median(row['elapsed_ms'] for row in aggregate)},
            'explain': plans}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
        print(f'测量完成：{args.output}')
    finally:
        asyncio.run(cleanup(url, user.id))


if __name__ == '__main__':
    main()
