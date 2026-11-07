"""浏览器测试专用入口，仅在显式隔离库启用确定性的工具调用替身。"""
import json
import os
import asyncio
from sqlalchemy.engine import make_url
from app.config import Settings
from app.main import create_app
from app.services.rag_provider import ModelProvider
from tests.test_stage15 import tool, response

url = os.environ['HELPFLOW_TEST_DATABASE_URL']
if not (make_url(url).database or '').startswith('helpflow_stage5_test'):
    raise RuntimeError('Only an isolated test database is permitted')


async def post(self, kind, path, payload):
    results = [json.loads(m['content']) for m in payload['messages'] if m['role'] == 'tool']
    if not results:
        if 'browser-wait' in payload['messages'][1]['content']:
            await asyncio.sleep(2)
        return response(tool('get_ticket'), tool('read_records'))
    mode = json.loads(payload['messages'][1]['content'])['mode']
    if mode == 'internal_summary':
        return response(tool('propose_action', {'content': '问题：登录失败；已尝试：未知；结论：待核实；待办：核对邮箱。'}))
    if not any('sources' in item for item in results):
        return response(tool('search_knowledge', {'query': '登录邮箱'}))
    sources = next(item['sources'] for item in results if 'sources' in item)
    if not sources:
        return response(tool('finish', {'message': '知识不足，请人工核实', 'needs_input': True}))
    return response(tool('propose_action', {'content': '请核对注册邮箱。', 'citations': [sources[0]['chunk_id']]}))


async def embed(self, text):
    return [1., 0.]


ModelProvider.post = post
ModelProvider.embed = embed
ModelProvider.space = property(lambda _: 'browser-agent-space')
app = create_app(Settings(_env_file=None, database_url=url, agent_checkpoint_path='.local/browser-agent.sqlite'))
