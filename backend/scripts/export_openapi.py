"""导出不含凭据的 OpenAPI 文件，供 Apifox 导入和接口核对。"""
import json
from pathlib import Path

from app.main import create_app
from app.config import Settings


def main():
    app = create_app(Settings(_env_file=None))
    schema = app.openapi()
    schema['servers'] = [{'url': 'http://localhost:8000', 'description': '本地开发'}]
    target = Path(__file__).resolve().parents[2] / 'docs' / 'api' / 'helpflow.openapi.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'已导出 {len(schema["paths"])} 个接口路径至 docs/api/helpflow.openapi.json')


if __name__ == '__main__':
    main()
