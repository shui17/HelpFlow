import asyncio

import pytest

from app.config import Settings
from scripts.seed_demo import seed


def test_seed_rejects_business_database_before_connecting():
    settings = Settings(_env_file=None,
        database_url='mysql+asyncmy://unused@127.0.0.1:1/helpflow')
    with pytest.raises(ValueError, match='helpflow_demo'):
        asyncio.run(seed(settings, 'DemoPassword123'))


def test_seed_rejects_invalid_password_before_connecting():
    settings = Settings(_env_file=None,
        database_url='mysql+asyncmy://unused@127.0.0.1:1/helpflow_demo_test')
    with pytest.raises(ValueError):
        asyncio.run(seed(settings, 'short'))
