"""仅为Agent浏览器隔离库准备测试账号和确定性向量资料。"""
import asyncio
import os
from app.db.session import create_database
from app.services.knowledge import publish
from tests.seed_browser import seed


class Embedding:
    space = 'browser-agent-space'

    async def embed(self, text):
        return [1., 0.]


async def main():
    await seed()  # 内含独立测试数据库名校验。
    engine, factory = create_database(os.environ['HELPFLOW_TEST_DATABASE_URL'])
    try:
        async with factory() as session:
            await publish(session, Embedding(), {'id': 'browser-login', 'version': 1,
                'title': '浏览器测试登录说明', 'digest': 'b'*64, 'chunks': ['请核对注册邮箱。']})
    finally:
        await engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())
