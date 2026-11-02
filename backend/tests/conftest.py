import os
import secrets

# 测试进程临时密钥，不写入文件或作为应用默认值。
os.environ.setdefault("HELPFLOW_JWT_SECRET_KEY", secrets.token_urlsafe(48))
