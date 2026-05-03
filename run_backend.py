"""백엔드 런처 - 경로 문제 없이 uvicorn을 올바른 디렉토리에서 실행"""
import os
import sys

backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
os.chdir(backend_dir)
sys.path.insert(0, backend_dir)

import uvicorn
uvicorn.run("main:app", host="127.0.0.1", port=8001)
