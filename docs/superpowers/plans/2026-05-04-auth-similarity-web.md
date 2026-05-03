# 인증 시스템 + similarity finder 웹화 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** MathSolution 메인 웹앱에 인증 시스템 + similarity finder 웹 탭을 도입하여 본인 + 친구 강사가 사용자별 작업 이력·API 키 분리하에 안전하게 사용 가능하게 한다.

**Architecture:** PostgreSQL + SQLAlchemy 2.0 + alembic. 인증은 argon2id + HttpOnly Cookie + CSRF Double-Submit 직접 구현. Railway 단일 컨테이너 배포(FastAPI가 frontend 정적 파일 serve). `AUTH_ENABLED` feature flag로 점진 도입(default false → 검증 후 true). similarity finder는 `tools/similarity_finder/comparator.py` → `backend/services/similarity_service.py` 이식 + FastAPI BackgroundTasks + DB 폴링.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, alembic, PostgreSQL 16, argon2-cffi, cryptography (Fernet), slowapi, React 18, React Router v6, Vite, Railway.

**정본 spec:** [docs/superpowers/specs/2026-05-04-auth-similarity-web-design.md](../specs/2026-05-04-auth-similarity-web-design.md) v3

**페르소나 분담:**
- 카리나 (1조): DB·인증 라우트·feature flag 미들웨어·프론트 인증·Railway 배포
- 원영 (2조): comparator.py → backend service 이식·TabSimilarity
- 이순신: argon2id·Cookie/CSRF·Fernet·rate limit·CORS·MASTER_ENC_KEY·침투 테스트
- 갈량: plan 작성·진행일지·리뷰

---

## Phase 의존성 그래프

```
Phase 1 (인프라)
    ↓
Phase 2 (인증)  ←  Phase 3 (similarity finder, 인증 미들웨어 사용)
    ↓                ↓
Phase 4 (사용자별 데이터, 인증 + similarity 둘 다 의존)
    ↓
Phase 5 (배포 + 침투 테스트)
```

병렬 가능: Phase 2 일부 (이순신의 유틸 작업) ↔ Phase 3 일부 (원영의 backend 이식)
직렬 강제: Phase 1 완료 → Phase 2 시작, Phase 4 → Phase 5

---

## File Structure

### 신규 생성
```
backend/
  auth/                          ← 인증 모듈 (신규)
    __init__.py
    crypto.py                    ← argon2id, Fernet, SHA-256 유틸
    csrf.py                      ← CSRF Double-Submit 미들웨어
    cookies.py                   ← Cookie 발급/검증
    middleware.py                ← AUTH_ENABLED 분기 + 라우트 보호
    routes.py                    ← /api/auth/* 라우트
    admin_routes.py              ← /api/admin/users 라우트
    bootstrap.py                 ← admin 자동 생성
  models/
    __init__.py                  ← (이미 있음)
    db.py                        ← SQLAlchemy 엔진·세션 (신규)
    user.py                      ← User 모델 (신규)
    auth_token.py                ← AuthToken 모델 (신규)
    user_api_key.py              ← UserApiKey 모델 (신규)
    work_history.py              ← WorkHistory 모델 (신규)
    login_attempt.py             ← LoginAttempt 모델 (신규)
  services/
    similarity_service.py        ← comparator.py 이식 (신규)
    user_api_key_service.py      ← API 키 CRUD + Fernet (신규)
    rate_limit_service.py        ← slowapi 설정 (신규)
  api/
    similarity.py                ← /api/similarity/* 라우트 (신규)
    user.py                      ← /api/user/* 라우트 (신규)
  alembic/                       ← 마이그레이션 (신규)
    env.py
    versions/
      0001_initial.py            ← 초기 5개 테이블
  tests/
    test_auth_crypto.py
    test_auth_routes.py
    test_csrf.py
    test_similarity_service.py
    test_user_api_keys.py
    conftest.py                  ← 테스트 fixtures
frontend/src/
  contexts/
    AuthContext.jsx              ← 인증 상태 전역 (신규)
  components/
    LoginPage.jsx                ← 로그인 화면 (신규)
    TabSimilarity.jsx            ← similarity 웹 탭 (신규)
    TabSettings.jsx              ← API 키·이력 설정 (신규)
  api/
    client.js                    ← HTTP 클라이언트 + CSRF 자동 (신규)
docs/
  AUTH_README.md                 ← 운영 문서 (신규)
```

### 수정
- `backend/main.py` — 인증 미들웨어 등록, 신규 라우터 추가, StaticFiles 통합
- `backend/requirements.txt` — SQLAlchemy, argon2-cffi, cryptography, slowapi, psycopg, alembic 추가
- `backend/Dockerfile` — frontend 빌드 stage 추가, alembic upgrade head 추가
- `backend/.env.example` — DATABASE_URL, MASTER_ENC_KEY, ADMIN_EMAIL, ADMIN_PASSWORD, ALLOWED_ORIGINS, AUTH_ENABLED 추가
- `docker-compose.yml` — postgres 서비스 추가
- `frontend/src/App.jsx` — AuthContext provider 통합, LoginPage 분기
- `frontend/src/main.jsx` — Router 설정
- `CLAUDE.md` — 인증·DB 운영 안내 추가
- `진행일지.md` — Phase 5 마감 시 항목 추가

---

# Phase 1: 인프라 (카리나, ~1일)

## Task 1.1: Docker compose에 PostgreSQL 추가

**담당:** 카리나
**의존성:** 없음
**파일:**
- Modify: `docker-compose.yml`
- Modify: `backend/.env.example`

- [ ] **Step 1: docker-compose.yml에 postgres 서비스 추가**

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: mathsol
      POSTGRES_PASSWORD: mathsol_dev_password
      POSTGRES_DB: mathsol
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U mathsol"]
      interval: 5s
      timeout: 5s
      retries: 10

  backend:
    # 기존 설정 유지하면서 depends_on 추가
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql+psycopg://mathsol:mathsol_dev_password@postgres:5432/mathsol
      AUTH_ENABLED: "false"

volumes:
  postgres_data:
```

- [ ] **Step 2: .env.example에 새 환경변수 추가**

```bash
# === 인증·DB (Phase 1+) ===
DATABASE_URL=postgresql+psycopg://mathsol:mathsol_dev_password@postgres:5432/mathsol
AUTH_ENABLED=false
MASTER_ENC_KEY=  # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ADMIN_EMAIL=admin@local.dev
ADMIN_PASSWORD=  # 첫 실행 시 자동 생성용
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:5174
```

- [ ] **Step 3: docker compose up -d postgres → health 확인**

```bash
docker compose up -d postgres
sleep 5
docker compose ps postgres
docker compose exec postgres pg_isready -U mathsol
```
Expected: `accepting connections`

- [ ] **Step 4: 커밋**

```bash
git add docker-compose.yml backend/.env.example
git commit -m "feat(infra): docker compose에 PostgreSQL 16 추가

- postgres:16-alpine 서비스 + healthcheck
- backend.depends_on postgres
- DATABASE_URL/AUTH_ENABLED/MASTER_ENC_KEY 등 새 환경변수 .env.example 추가

작업자: 카리나 (1조)"
```

**Success Criteria:**
- `docker compose ps postgres` 가 healthy 상태
- `psql ... -c "SELECT 1"` 로 연결 가능
- 기존 backend·frontend 컨테이너 정상 동작 (회귀 0)

---

## Task 1.2: SQLAlchemy 2.0 + psycopg 의존성 추가

**담당:** 카리나
**의존성:** 1.1
**파일:**
- Modify: `backend/requirements.txt`
- Create: `backend/models/db.py`

- [ ] **Step 1: requirements.txt에 의존성 추가**

```
sqlalchemy>=2.0.0,<3.0
psycopg[binary]>=3.2.0
alembic>=1.13.0
argon2-cffi>=23.1.0
cryptography>=42.0.0
slowapi>=0.1.9
```

- [ ] **Step 2: backend/models/db.py 작성**

```python
"""SQLAlchemy 2.0 엔진·세션 관리.

DATABASE_URL이 비어있으면(=AUTH_ENABLED=false 환경 가정) 엔진 생성하지 않고
None을 반환. 인증 관련 라우트는 AUTH_ENABLED 체크로 보호되므로 회귀 없음.
"""
import os
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None


def get_engine() -> Optional[Engine]:
    global _engine, _SessionLocal
    if _engine is not None:
        return _engine

    db_url = os.getenv("DATABASE_URL", "").strip()
    if not db_url:
        return None

    _engine = create_engine(db_url, pool_pre_ping=True, pool_size=5, max_overflow=10)
    _SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
    return _engine


def get_session() -> Session:
    """FastAPI Depends 용. AUTH_ENABLED=false 환경에선 호출되지 않음."""
    if _SessionLocal is None:
        get_engine()  # lazy init
    if _SessionLocal is None:
        raise RuntimeError("DATABASE_URL not configured")
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 3: Docker 재빌드 + smoke test**

```bash
docker compose up -d --build backend
sleep 5
docker compose logs --tail 20 backend
curl -sf http://localhost:8001/api/health
```
Expected: `{"status":"ok"}` + 로그에 import 에러 없음

- [ ] **Step 4: 커밋**

```bash
git add backend/requirements.txt backend/models/db.py
git commit -m "feat(infra): SQLAlchemy 2.0 + psycopg + alembic 의존성 추가

- requirements.txt: sqlalchemy>=2.0, psycopg[binary], alembic, argon2-cffi, cryptography, slowapi
- models/db.py: 엔진·세션 lazy init (DATABASE_URL 없으면 None 반환 — 회귀 0)

작업자: 카리나 (1조)"
```

**Success Criteria:**
- backend 컨테이너 startup OK
- /api/health 200
- DATABASE_URL 미설정 시 import error 없음 (점진 도입 검증)

---

## Task 1.3: alembic 초기화 + 첫 마이그레이션 (5 테이블)

**담당:** 카리나
**의존성:** 1.2
**파일:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/versions/0001_initial.py`
- Create: `backend/models/user.py`
- Create: `backend/models/auth_token.py`
- Create: `backend/models/user_api_key.py`
- Create: `backend/models/work_history.py`
- Create: `backend/models/login_attempt.py`

- [ ] **Step 1: alembic init**

```bash
docker compose exec backend bash -c "cd /app && alembic init alembic"
```

- [ ] **Step 2: alembic.ini 수정**

`sqlalchemy.url` 줄을 빈 값으로 두고 (env.py에서 환경변수 로드):
```ini
sqlalchemy.url =
```

- [ ] **Step 3: backend/alembic/env.py 작성**

```python
"""alembic 환경 설정 — 환경변수 DATABASE_URL 사용."""
import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Base + 모든 모델 import (autogenerate가 인지하도록)
from models.db import Base
from models.user import User  # noqa
from models.auth_token import AuthToken  # noqa
from models.user_api_key import UserApiKey  # noqa
from models.work_history import WorkHistory  # noqa
from models.login_attempt import LoginAttempt  # noqa

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", os.getenv("DATABASE_URL", ""))

target_metadata = Base.metadata


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 4: 5개 모델 파일 작성**

`backend/models/user.py`:
```python
from datetime import datetime
from sqlalchemy import BigInteger, Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)  # argon2id
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

`backend/models/auth_token.py`:
```python
from datetime import datetime
from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


class AuthToken(Base):
    __tablename__ = "auth_tokens"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

`backend/models/user_api_key.py`:
```python
from datetime import datetime
from sqlalchemy import BigInteger, DateTime, ForeignKey, LargeBinary, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


class UserApiKey(Base):
    __tablename__ = "user_api_keys"
    __table_args__ = (UniqueConstraint("user_id", "provider", name="uq_user_provider"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String, nullable=False)  # 'anthropic' | 'gemini'
    encrypted_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
```

`backend/models/work_history.py`:
```python
from datetime import datetime
from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


class WorkHistory(Base):
    __tablename__ = "work_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    work_type: Mapped[str] = mapped_column(String, nullable=False)  # 'generate' | 'similarity_search' | ...
    status: Mapped[str] = mapped_column(String, nullable=False, default="done")  # 'pending'|'running'|'done'|'failed'
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
```

`backend/models/login_attempt.py`:
```python
from datetime import datetime
from sqlalchemy import BigInteger, Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


class LoginAttempt(Base):
    __tablename__ = "login_attempts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email: Mapped[str] = mapped_column(String, nullable=False, index=True)
    ip: Mapped[str] = mapped_column(String, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
```

- [ ] **Step 5: alembic autogenerate 첫 마이그레이션**

```bash
docker compose exec backend bash -c "cd /app && alembic revision --autogenerate -m 'initial: 5 tables'"
```

- [ ] **Step 6: 생성된 0001_initial.py 검토 후 적용**

```bash
docker compose exec backend bash -c "cd /app && alembic upgrade head"
```

- [ ] **Step 7: 테이블 생성 검증**

```bash
docker compose exec postgres psql -U mathsol -d mathsol -c "\dt"
```
Expected: users, auth_tokens, user_api_keys, work_history, login_attempts, alembic_version 6 테이블 표시

- [ ] **Step 8: 커밋**

```bash
git add backend/alembic.ini backend/alembic/ backend/models/
git commit -m "feat(infra): alembic 초기화 + 5 테이블 마이그레이션

- alembic.ini, alembic/env.py, alembic/versions/0001_initial.py
- models/{user,auth_token,user_api_key,work_history,login_attempt}.py
- SQLAlchemy 2.0 Mapped/mapped_column 스타일

작업자: 카리나 (1조)"
```

**Success Criteria:**
- 6개 테이블(5 + alembic_version) 생성됨
- 인덱스·외래키·UNIQUE 제약 모두 적용됨
- alembic upgrade head 재실행 시 idempotent (변경 없음)

---

## Task 1.4: feature flag `AUTH_ENABLED` 미들웨어 스켈레톤

**담당:** 카리나
**의존성:** 1.2
**파일:**
- Create: `backend/auth/__init__.py`
- Create: `backend/auth/middleware.py`
- Modify: `backend/main.py`

- [ ] **Step 1: backend/auth/__init__.py (빈 파일)**

```python
"""인증 모듈 (Phase 2에서 채워짐).

AUTH_ENABLED=false 시 미들웨어가 우회 → 기존 baseline 동작.
"""
```

- [ ] **Step 2: backend/auth/middleware.py 작성**

```python
"""인증 미들웨어 — AUTH_ENABLED 분기.

Phase 1: 스켈레톤만. AUTH_ENABLED=true여도 우회 (Phase 2에서 검증 로직 추가).
"""
import os
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)


def is_auth_enabled() -> bool:
    return os.getenv("AUTH_ENABLED", "false").lower() in ("true", "1", "yes")


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if not is_auth_enabled():
            return await call_next(request)

        # 인증 면제 경로
        path = request.url.path
        if path.startswith("/api/auth/"):
            return await call_next(request)
        if path in ("/api/health", "/api/version"):
            return await call_next(request)
        if not path.startswith("/api/"):
            return await call_next(request)  # 정적 파일·기타

        # Phase 2에서 채울 자리: cookie 검증, CSRF, request.state.user 설정
        # Phase 1에선 통과
        return await call_next(request)
```

- [ ] **Step 3: backend/main.py에 미들웨어 등록**

```python
# 기존 imports 아래에 추가
from auth.middleware import AuthMiddleware

# CORSMiddleware 다음 줄에 추가
app.add_middleware(AuthMiddleware)
```

- [ ] **Step 4: Docker 재빌드 + 회귀 검증**

```bash
docker compose up -d --build backend
sleep 5
curl -sf http://localhost:8001/api/health
curl -sf -X POST http://localhost:8001/api/hwpx-analyze -F "file=@고등수학_1.다항식_3.인수분해_선택_중.hwpx" | python -c "import sys, json; d = json.load(sys.stdin); print('problems:', d.get('problem_count'))"
```
Expected: health 200, hwpx-analyze 1504개

- [ ] **Step 5: 커밋**

```bash
git add backend/auth/__init__.py backend/auth/middleware.py backend/main.py
git commit -m "feat(auth): AUTH_ENABLED feature flag 미들웨어 스켈레톤

- AuthMiddleware: AUTH_ENABLED=false면 우회 (Phase 1 회귀 0)
- AUTH_ENABLED=true 시에도 Phase 1에선 통과 (Phase 2에서 검증 로직 채움)
- /api/auth/*, /api/health, /api/version은 인증 면제

작업자: 카리나 (1조)"
```

**Success Criteria:**
- AUTH_ENABLED=false: 모든 기존 라우트 정상 (회귀 0 — hwpx-analyze 1504개 유지)
- AUTH_ENABLED=true: 동일 동작 (Phase 1 단계라 검증 로직 미구현)

---

## Task 1.5: 환경변수 정리 + 운영 문서 초안

**담당:** 카리나·갈량
**의존성:** 1.4
**파일:**
- Create: `docs/AUTH_README.md`

- [ ] **Step 1: docs/AUTH_README.md 작성**

```markdown
# 인증·DB 운영 가이드

## 환경변수

| 변수 | 기본값 | 설명 |
|---|---|---|
| `DATABASE_URL` | (Docker) postgres://... | PostgreSQL 연결 URL |
| `AUTH_ENABLED` | `false` | 인증 시스템 활성화 (점진 도입용) |
| `MASTER_ENC_KEY` | (필수, 비어있으면 시작 거부) | Fernet 마스터 키. `Fernet.generate_key()` 결과 |
| `ADMIN_EMAIL` | `admin@local.dev` | 첫 실행 시 admin 자동 생성 이메일 |
| `ADMIN_PASSWORD` | (없음) | 첫 실행 시 admin 자동 생성 패스워드. 미설정 시 생성 안 함 |
| `ALLOWED_ORIGINS` | `http://localhost:5173,...` | CORS 허용 도메인 (콤마 구분) |

## 마이그레이션

```bash
# 새 마이그레이션 생성
docker compose exec backend alembic revision --autogenerate -m "메시지"

# 적용
docker compose exec backend alembic upgrade head

# 롤백 (주의: 데이터 손실 가능)
docker compose exec backend alembic downgrade -1
```

## 점진 도입 절차

1. Phase 1~5 완료 → main에 머지 후에도 `AUTH_ENABLED=false` 유지
2. 본인 환경에서 `AUTH_ENABLED=true` 로컬 테스트 1주
3. Railway 환경변수에 `AUTH_ENABLED=true` 등록 → 친구 강사 공유

## MASTER_ENC_KEY 생성

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

이 키는 분실 시 모든 사용자 API 키 복호화 불가. 1Password 등에 백업.
```

- [ ] **Step 2: 커밋**

```bash
git add docs/AUTH_README.md
git commit -m "docs(auth): 인증·DB 운영 가이드 초안

- 환경변수 표
- 마이그레이션 명령
- 점진 도입 절차 (Phase 5 완료 후 1주 검증 → 친구 공유)
- MASTER_ENC_KEY 생성·백업 안내

작업자: 카리나·갈량"
```

**Phase 1 종료 검증:**
- [ ] postgres 컨테이너 healthy
- [ ] 5 테이블 생성 + alembic_version 추적
- [ ] AuthMiddleware 등록됨 (false 시 회귀 0)
- [ ] hwpx-analyze 1504개 회귀 검증 통과
- [ ] /api/health 200

---

# Phase 2: 인증 시스템 (카리나·이순신, ~2일)

## Task 2.1 [이순신]: argon2id 패스워드 해시 유틸 + 테스트

**담당:** 이순신
**의존성:** Phase 1
**병렬:** Task 2.2와 동시 가능
**파일:**
- Create: `backend/auth/crypto.py`
- Create: `backend/tests/test_auth_crypto.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_auth_crypto.py`:
```python
import pytest
from auth.crypto import hash_password, verify_password


def test_hash_and_verify_roundtrip():
    pw = "correct horse battery staple"
    hashed = hash_password(pw)
    assert verify_password(pw, hashed) is True


def test_verify_wrong_password():
    hashed = hash_password("right")
    assert verify_password("wrong", hashed) is False


def test_hash_is_argon2id():
    h = hash_password("anything")
    assert h.startswith("$argon2id$"), f"expected argon2id, got: {h[:20]}"


def test_two_hashes_differ_for_same_password():
    a = hash_password("same")
    b = hash_password("same")
    assert a != b, "argon2id should use random salt"
```

- [ ] **Step 2: 테스트 실행 → FAIL**

```bash
docker compose exec backend pytest tests/test_auth_crypto.py -v
```
Expected: 4 FAILED (`auth.crypto` not found)

- [ ] **Step 3: 구현**

`backend/auth/crypto.py`:
```python
"""인증·암호화 유틸 — argon2id, Fernet, SHA-256."""
import hashlib
import os
import secrets
from typing import Final

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

# argon2id 권장 파라미터 (외부 노출 환경)
_PH: Final = PasswordHasher(
    time_cost=3, memory_cost=64 * 1024, parallelism=4, hash_len=32, salt_len=16
)


def hash_password(plain: str) -> str:
    """argon2id 해시 (random salt 자동)."""
    return _PH.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """패스워드 검증. 일치 시 True, 불일치/오류 시 False."""
    try:
        _PH.verify(hashed, plain)
        return True
    except (VerifyMismatchError, Exception):
        return False


def generate_session_token() -> str:
    """평문 세션 토큰 (UUID v4 대신 secrets로 256-bit 엔트로피)."""
    return secrets.token_urlsafe(32)  # 256-bit


def hash_token(plain_token: str) -> str:
    """세션 토큰 SHA-256 해시 (DB 저장용)."""
    return hashlib.sha256(plain_token.encode()).hexdigest()


def generate_csrf_token() -> str:
    """CSRF 토큰 — Double-Submit Cookie pattern."""
    return secrets.token_urlsafe(24)


def _get_master_key() -> bytes:
    key = os.environ.get("MASTER_ENC_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "MASTER_ENC_KEY 환경변수가 비어있습니다. "
            'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 으로 생성 후 등록하세요.'
        )
    return key.encode()


def encrypt_api_key(plain: str) -> bytes:
    """사용자 API 키를 Fernet으로 암호화."""
    f = Fernet(_get_master_key())
    return f.encrypt(plain.encode())


def decrypt_api_key(encrypted: bytes) -> str:
    """복호화. MASTER_ENC_KEY가 바뀌면 InvalidToken 발생."""
    f = Fernet(_get_master_key())
    try:
        return f.decrypt(encrypted).decode()
    except InvalidToken as e:
        raise RuntimeError("API 키 복호화 실패 — MASTER_ENC_KEY 불일치 가능") from e
```

- [ ] **Step 4: 테스트 실행 → PASS**

```bash
docker compose exec backend pytest tests/test_auth_crypto.py -v
```
Expected: 4 passed

- [ ] **Step 5: Fernet 라운드트립 테스트 추가**

`tests/test_auth_crypto.py`에 추가:
```python
def test_encrypt_decrypt_roundtrip(monkeypatch):
    from cryptography.fernet import Fernet
    monkeypatch.setenv("MASTER_ENC_KEY", Fernet.generate_key().decode())
    from auth.crypto import encrypt_api_key, decrypt_api_key
    plain = "sk-ant-test-key"
    encrypted = encrypt_api_key(plain)
    assert encrypted != plain.encode()
    assert decrypt_api_key(encrypted) == plain


def test_encrypt_no_master_key(monkeypatch):
    monkeypatch.setenv("MASTER_ENC_KEY", "")
    from auth.crypto import encrypt_api_key
    with pytest.raises(RuntimeError, match="MASTER_ENC_KEY"):
        encrypt_api_key("any")


def test_token_hash_consistent():
    from auth.crypto import hash_token
    t = "abc123"
    assert hash_token(t) == hash_token(t)
    assert len(hash_token(t)) == 64  # SHA-256 hex
```

- [ ] **Step 6: 테스트 재실행 → 7 PASS**

```bash
docker compose exec backend pytest tests/test_auth_crypto.py -v
```

- [ ] **Step 7: 커밋**

```bash
git add backend/auth/crypto.py backend/tests/test_auth_crypto.py
git commit -m "feat(auth): argon2id + Fernet + SHA-256 암호화 유틸

- hash_password/verify_password (argon2id m=64MB t=3 p=4)
- generate_session_token/hash_token (256-bit + SHA-256)
- generate_csrf_token (Double-Submit용)
- encrypt_api_key/decrypt_api_key (Fernet AES-128-CBC + HMAC)
- MASTER_ENC_KEY 비어있으면 명시 에러

테스트 7개 모두 통과.

작업자: 이순신 (보안)"
```

**Success Criteria:**
- pytest 7 PASS
- 같은 패스워드를 두 번 해시하면 다른 결과 (random salt 검증)
- MASTER_ENC_KEY 미설정 시 즉시 에러 (silent fallback 없음)

---

## Task 2.2 [이순신]: CSRF Double-Submit 미들웨어

**담당:** 이순신
**의존성:** 2.1
**파일:**
- Create: `backend/auth/csrf.py`
- Create: `backend/tests/test_csrf.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
"""CSRF Double-Submit 검증 테스트."""
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from auth.csrf import CSRFMiddleware, CSRF_COOKIE_NAME, CSRF_HEADER_NAME


@pytest.fixture
def app():
    app = FastAPI()
    app.add_middleware(CSRFMiddleware)

    @app.get("/api/safe")
    async def safe():
        return {"ok": True}

    @app.post("/api/mutate")
    async def mutate():
        return {"ok": True}

    return app


def test_get_no_csrf_required(app):
    client = TestClient(app)
    r = client.get("/api/safe")
    assert r.status_code == 200


def test_post_without_csrf_blocked(app):
    client = TestClient(app)
    r = client.post("/api/mutate")
    assert r.status_code == 403


def test_post_with_matching_csrf_passes(app):
    client = TestClient(app)
    token = "matching_csrf_token"
    r = client.post(
        "/api/mutate",
        headers={CSRF_HEADER_NAME: token},
        cookies={CSRF_COOKIE_NAME: token},
    )
    assert r.status_code == 200


def test_post_with_mismatched_csrf_blocked(app):
    client = TestClient(app)
    r = client.post(
        "/api/mutate",
        headers={CSRF_HEADER_NAME: "x"},
        cookies={CSRF_COOKIE_NAME: "y"},
    )
    assert r.status_code == 403


def test_auth_login_csrf_exempt(app):
    @app.post("/api/auth/login")
    async def login():
        return {"ok": True}
    client = TestClient(app)
    r = client.post("/api/auth/login")
    assert r.status_code == 200
```

- [ ] **Step 2: 테스트 실행 → FAIL**

```bash
docker compose exec backend pytest tests/test_csrf.py -v
```

- [ ] **Step 3: 구현**

`backend/auth/csrf.py`:
```python
"""CSRF Double-Submit Cookie 미들웨어.

- GET/HEAD/OPTIONS: 검증 면제 (idempotent)
- /api/auth/login, /api/auth/logout: 면제 (CSRF cookie 없는 첫 요청)
- POST/PUT/DELETE/PATCH: header X-CSRF-Token ↔ cookie csrf_token 비교
"""
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "x-csrf-token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
EXEMPT_PATHS = {"/api/auth/login", "/api/auth/logout"}


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method in SAFE_METHODS:
            return await call_next(request)
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
        header_token = request.headers.get(CSRF_HEADER_NAME)

        if not cookie_token or not header_token or cookie_token != header_token:
            return JSONResponse(
                {"detail": "CSRF token missing or mismatch"}, status_code=403
            )

        return await call_next(request)
```

- [ ] **Step 4: 테스트 → PASS**

- [ ] **Step 5: 커밋**

```bash
git add backend/auth/csrf.py backend/tests/test_csrf.py
git commit -m "feat(auth): CSRF Double-Submit Cookie 미들웨어

- GET/HEAD/OPTIONS 면제, /api/auth/login·logout 면제
- POST/PUT/DELETE/PATCH는 header ↔ cookie 비교
- 미일치/누락 시 403

테스트 5개 통과.

작업자: 이순신 (보안)"
```

**Success Criteria:**
- pytest 5 PASS
- AUTH_ENABLED 와 무관하게 CSRF 미들웨어 동작 (Phase 2.5에서 main.py에 등록)

---

## Task 2.3 [카리나]: 인증 라우트 + cookie 발급/검증

**담당:** 카리나
**의존성:** 2.1, 2.2
**파일:**
- Create: `backend/auth/cookies.py`
- Create: `backend/auth/routes.py`
- Create: `backend/tests/test_auth_routes.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
"""인증 라우트 테스트."""
import os
import pytest
from fastapi.testclient import TestClient
from cryptography.fernet import Fernet


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("MASTER_ENC_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("AUTH_ENABLED", "true")


@pytest.fixture
def client(db_session):
    """conftest.py의 db_session 픽스처가 in-memory DB 제공."""
    from main import app
    from models.user import User
    from auth.crypto import hash_password
    user = User(email="alice@test.com", password_hash=hash_password("Pa55word!"), is_admin=False)
    db_session.add(user)
    db_session.commit()
    return TestClient(app)


def test_login_success(client):
    r = client.post("/api/auth/login", json={"email": "alice@test.com", "password": "Pa55word!"})
    assert r.status_code == 200
    assert "session_token" in r.cookies
    assert "csrf_token" in r.cookies
    assert "x-csrf-token" in {k.lower() for k in r.headers.keys()}


def test_login_wrong_password(client):
    r = client.post("/api/auth/login", json={"email": "alice@test.com", "password": "wrong"})
    assert r.status_code == 401


def test_login_unknown_email(client):
    r = client.post("/api/auth/login", json={"email": "ghost@test.com", "password": "x"})
    assert r.status_code == 401


def test_me_after_login(client):
    login = client.post("/api/auth/login", json={"email": "alice@test.com", "password": "Pa55word!"})
    csrf = login.cookies["csrf_token"]
    r = client.get("/api/auth/me", headers={"x-csrf-token": csrf})
    assert r.status_code == 200
    assert r.json()["email"] == "alice@test.com"


def test_me_without_login(client):
    r = client.get("/api/auth/me")
    # GET이라 CSRF 면제, 다만 인증 없으면 401
    assert r.status_code == 401


def test_logout_clears_cookie(client):
    login = client.post("/api/auth/login", json={"email": "alice@test.com", "password": "Pa55word!"})
    csrf = login.cookies["csrf_token"]
    r = client.post("/api/auth/logout", headers={"x-csrf-token": csrf}, cookies=login.cookies)
    assert r.status_code == 200
    # session_token cookie deleted
```

`backend/tests/conftest.py`:
```python
"""테스트 fixture — in-memory SQLite로 PostgreSQL 시뮬레이션."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.db import Base


@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def db_session(engine, monkeypatch):
    SessionLocal = sessionmaker(bind=engine)
    sess = SessionLocal()
    # models.db 의 _SessionLocal 을 monkey-patch
    import models.db as db_mod
    monkeypatch.setattr(db_mod, "_engine", engine)
    monkeypatch.setattr(db_mod, "_SessionLocal", SessionLocal)
    yield sess
    sess.close()
```

- [ ] **Step 2: 구현 — backend/auth/cookies.py**

```python
"""세션 cookie 발급·검증."""
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session
from starlette.responses import Response

from auth.crypto import (
    generate_csrf_token,
    generate_session_token,
    hash_token,
)
from auth.csrf import CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from models.auth_token import AuthToken

SESSION_COOKIE_NAME = "session_token"
SESSION_DAYS = 7


def issue_session(response: Response, db: Session, user_id: int) -> None:
    """세션 토큰 + CSRF 토큰을 발급해 cookie + 헤더에 set."""
    plain_session = generate_session_token()
    csrf = generate_csrf_token()

    expires = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)
    db.add(AuthToken(user_id=user_id, token_hash=hash_token(plain_session), expires_at=expires))
    db.commit()

    secure = True  # 프로덕션 항상 HTTPS. dev 환경에선 SameSite=Lax + Secure=False 필요할 수도
    common = dict(httponly=True, secure=secure, samesite="strict", max_age=SESSION_DAYS * 86400)

    response.set_cookie(SESSION_COOKIE_NAME, plain_session, **common)
    response.set_cookie(CSRF_COOKIE_NAME, csrf, httponly=False, secure=secure, samesite="strict", max_age=SESSION_DAYS * 86400)
    response.headers[CSRF_HEADER_NAME] = csrf


def revoke_session(response: Response, db: Session, plain_session: Optional[str]) -> None:
    """로그아웃 — DB에서 토큰 삭제 + cookie 만료."""
    if plain_session:
        db.query(AuthToken).filter(AuthToken.token_hash == hash_token(plain_session)).delete()
        db.commit()
    response.delete_cookie(SESSION_COOKIE_NAME)
    response.delete_cookie(CSRF_COOKIE_NAME)


def lookup_user(db: Session, plain_session: Optional[str]):
    """cookie 토큰으로 user 조회. 없거나 만료면 None."""
    if not plain_session:
        return None
    th = hash_token(plain_session)
    token = (
        db.query(AuthToken)
        .filter(AuthToken.token_hash == th, AuthToken.expires_at > datetime.now(timezone.utc))
        .one_or_none()
    )
    if not token:
        return None
    from models.user import User
    return db.query(User).filter(User.id == token.user_id).one_or_none()
```

- [ ] **Step 3: 구현 — backend/auth/routes.py**

```python
"""인증 라우트: /api/auth/login /logout /me /csrf"""
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from auth.cookies import (
    SESSION_COOKIE_NAME,
    issue_session,
    lookup_user,
    revoke_session,
)
from auth.crypto import generate_csrf_token, verify_password
from auth.csrf import CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from models.db import get_session
from models.user import User

router = APIRouter(prefix="/api/auth")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/login")
async def login(payload: LoginRequest, response: Response, db: Session = Depends(get_session)):
    user = db.query(User).filter(User.email == payload.email).one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    issue_session(response, db, user.id)
    return {"id": user.id, "email": user.email, "is_admin": user.is_admin}


@router.post("/logout")
async def logout(request: Request, response: Response, db: Session = Depends(get_session)):
    plain = request.cookies.get(SESSION_COOKIE_NAME)
    revoke_session(response, db, plain)
    return {"ok": True}


@router.get("/me")
async def me(request: Request, db: Session = Depends(get_session)):
    plain = request.cookies.get(SESSION_COOKIE_NAME)
    user = lookup_user(db, plain)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"id": user.id, "email": user.email, "is_admin": user.is_admin}


@router.get("/csrf")
async def get_csrf(response: Response):
    """페이지 새로고침 후 CSRF 토큰 재발급."""
    csrf = generate_csrf_token()
    response.set_cookie(CSRF_COOKIE_NAME, csrf, httponly=False, secure=True, samesite="strict")
    response.headers[CSRF_HEADER_NAME] = csrf
    return {"ok": True}
```

- [ ] **Step 4: backend/main.py에 라우터·미들웨어 등록**

```python
from auth.csrf import CSRFMiddleware
from auth.routes import router as auth_router

# 등록 순서: CORS → CSRF → Auth(Phase 1 스켈레톤)
app.add_middleware(CSRFMiddleware)
app.include_router(auth_router)
```

- [ ] **Step 5: 테스트 → PASS (6+)**

```bash
docker compose exec backend pytest tests/test_auth_routes.py -v
```

- [ ] **Step 6: 커밋**

```bash
git add backend/auth/ backend/tests/test_auth_routes.py backend/tests/conftest.py backend/main.py
git commit -m "feat(auth): /api/auth 라우트 + cookie 발급/검증

- POST /login: argon2id 검증 → session_token + csrf_token cookie + X-CSRF-Token 헤더
- POST /logout: 토큰 DB 삭제 + cookie Max-Age=0
- GET /me: cookie 검증 후 사용자 정보
- GET /csrf: 페이지 새로고침 시 CSRF 재발급
- HttpOnly + Secure + SameSite=Strict
- conftest.py: in-memory SQLite fixture

테스트 6개 통과.

작업자: 카리나 (1조)"
```

**Success Criteria:**
- 6+ pytest PASS
- 로그인 → cookie 받음 → /me 200
- 잘못된 패스워드 → 401
- 로그아웃 → cookie 삭제 + DB 토큰 삭제

---

## Task 2.4 [카리나]: 인증 미들웨어 — cookie 검증 + AUTH_ENABLED 분기

**담당:** 카리나
**의존성:** 2.3
**파일:**
- Modify: `backend/auth/middleware.py`

- [ ] **Step 1: middleware.py 갱신 — Phase 1 스켈레톤에 검증 로직 추가**

```python
"""인증 미들웨어 — AUTH_ENABLED 분기 + cookie 검증."""
import os
import logging
from fastapi import Request
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from auth.cookies import SESSION_COOKIE_NAME, lookup_user
from models.db import get_engine

logger = logging.getLogger(__name__)


def is_auth_enabled() -> bool:
    return os.getenv("AUTH_ENABLED", "false").lower() in ("true", "1", "yes")


_EXEMPT_PREFIXES = ("/api/auth/",)
_EXEMPT_EXACT = {"/api/health", "/api/version", "/api/system-info"}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if not is_auth_enabled():
            return await call_next(request)

        path = request.url.path

        if path in _EXEMPT_EXACT or any(path.startswith(p) for p in _EXEMPT_PREFIXES):
            return await call_next(request)
        if not path.startswith("/api/"):
            return await call_next(request)  # 정적 파일 등

        # cookie 인증 검증
        plain = request.cookies.get(SESSION_COOKIE_NAME)
        if not plain:
            return JSONResponse({"detail": "Not authenticated"}, status_code=401)

        engine = get_engine()
        if not engine:
            return JSONResponse({"detail": "DB not configured"}, status_code=503)

        from sqlalchemy.orm import sessionmaker
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()
        try:
            user = lookup_user(db, plain)
            if not user:
                return JSONResponse({"detail": "Invalid or expired session"}, status_code=401)
            request.state.user = user
            return await call_next(request)
        finally:
            db.close()
```

- [ ] **Step 2: 회귀 테스트 — AUTH_ENABLED=false 시 baseline 동일**

```bash
# AUTH_ENABLED=false (default) 상태로 hwpx-analyze 동작 확인
docker compose up -d --build backend
sleep 5
curl -sf -X POST http://localhost:8001/api/hwpx-analyze -F "file=@고등수학_1.다항식_3.인수분해_선택_중.hwpx" | python -c "import sys, json; d = json.load(sys.stdin); print('problems:', d.get('problem_count'))"
```
Expected: problems: 1504

- [ ] **Step 3: AUTH_ENABLED=true 시 보호 라우트 401 검증**

```bash
docker compose exec backend bash -c "AUTH_ENABLED=true python -c 'from auth.middleware import is_auth_enabled; print(is_auth_enabled())'"
# 결과: True

# 임시로 AUTH_ENABLED=true 설정 후 컨테이너 재시작
# (운영상 docker-compose.override.yml로 AUTH_ENABLED=true 설정)
```

- [ ] **Step 4: 커밋**

```bash
git add backend/auth/middleware.py
git commit -m "feat(auth): AuthMiddleware에 cookie 검증 추가

- AUTH_ENABLED=true 시: cookie 검증 → request.state.user
- 면제: /api/auth/*, /api/health, /api/version, /api/system-info
- AUTH_ENABLED=false 시: 우회 (회귀 0)

작업자: 카리나 (1조)"
```

**Success Criteria:**
- AUTH_ENABLED=false: hwpx-analyze 1504 (회귀 0)
- AUTH_ENABLED=true: 미인증 시 401

---

## Task 2.5 [카리나]: admin 자동 생성 + 사용자 관리 라우트

**담당:** 카리나
**의존성:** 2.4
**파일:**
- Create: `backend/auth/bootstrap.py`
- Create: `backend/auth/admin_routes.py`
- Modify: `backend/main.py`

- [ ] **Step 1: bootstrap.py — startup 시 admin 자동 생성**

```python
"""ADMIN_EMAIL + ADMIN_PASSWORD env 있으면 첫 실행 시 admin 자동 생성."""
import os
import logging
from sqlalchemy.orm import Session
from auth.crypto import hash_password
from models.db import get_engine
from models.user import User

logger = logging.getLogger(__name__)


def bootstrap_admin() -> None:
    email = os.getenv("ADMIN_EMAIL", "").strip()
    password = os.getenv("ADMIN_PASSWORD", "").strip()
    if not email or not password:
        logger.info("ADMIN_EMAIL/ADMIN_PASSWORD 미설정 — admin 자동 생성 안 함")
        return

    engine = get_engine()
    if not engine:
        logger.warning("DATABASE_URL 미설정 — admin 자동 생성 스킵")
        return

    from sqlalchemy.orm import sessionmaker
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == email).one_or_none()
        if existing:
            logger.info(f"admin {email} 이미 존재 — 생성 스킵")
            return
        admin = User(email=email, password_hash=hash_password(password), is_admin=True)
        db.add(admin)
        db.commit()
        logger.info(f"admin {email} 자동 생성 완료")
    finally:
        db.close()
```

- [ ] **Step 2: backend/main.py의 startup hook에 bootstrap 호출**

```python
@app.on_event("startup")
async def on_startup():
    # 기존 startup 코드 유지
    from auth.bootstrap import bootstrap_admin
    try:
        bootstrap_admin()
    except Exception as e:
        logger.error(f"admin bootstrap 실패: {e}")
```

- [ ] **Step 3: admin_routes.py — 사용자 관리**

```python
"""admin 전용 사용자 관리 라우트."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from auth.crypto import hash_password
from models.db import get_session
from models.user import User

router = APIRouter(prefix="/api/admin")


def require_admin(request: Request) -> User:
    user = getattr(request.state, "user", None)
    if not user or not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")
    return user


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str
    is_admin: bool = False


@router.get("/users")
async def list_users(_: User = Depends(require_admin), db: Session = Depends(get_session)):
    users = db.query(User).order_by(User.id).all()
    return [{"id": u.id, "email": u.email, "is_admin": u.is_admin, "created_at": u.created_at} for u in users]


@router.post("/users", status_code=201)
async def create_user(payload: CreateUserRequest, _: User = Depends(require_admin), db: Session = Depends(get_session)):
    if db.query(User).filter(User.email == payload.email).one_or_none():
        raise HTTPException(status_code=409, detail="Email already exists")
    new = User(email=payload.email, password_hash=hash_password(payload.password), is_admin=payload.is_admin)
    db.add(new)
    db.commit()
    db.refresh(new)
    return {"id": new.id, "email": new.email, "is_admin": new.is_admin}


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(user_id: int, current: User = Depends(require_admin), db: Session = Depends(get_session)):
    if current.id == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete self")
    target = db.query(User).filter(User.id == user_id).one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(target)
    db.commit()
```

- [ ] **Step 4: main.py에 admin_router 등록**

```python
from auth.admin_routes import router as admin_router
app.include_router(admin_router)
```

- [ ] **Step 5: 통합 테스트**

```bash
# Phase 2 통합: AUTH_ENABLED=true + ADMIN_EMAIL/PASSWORD 설정
docker compose down
echo "ADMIN_EMAIL=admin@local.dev" >> backend/.env
echo "ADMIN_PASSWORD=ChangeMe123!" >> backend/.env
echo "AUTH_ENABLED=true" >> backend/.env
docker compose up -d --build backend
sleep 5

# 1) admin 자동 생성 로그 확인
docker compose logs --tail 20 backend | grep -i admin

# 2) admin 로그인 + 친구 계정 생성
COOKIES=$(mktemp)
curl -sf -c $COOKIES -X POST http://localhost:8001/api/auth/login -H "Content-Type: application/json" -d '{"email":"admin@local.dev","password":"ChangeMe123!"}'
CSRF=$(awk '/csrf_token/ {print $7}' $COOKIES)
curl -sf -b $COOKIES -H "X-CSRF-Token: $CSRF" -X POST http://localhost:8001/api/admin/users -H "Content-Type: application/json" -d '{"email":"friend@test.com","password":"FriendPass1!"}'

# 3) 사용자 목록 조회
curl -sf -b $COOKIES http://localhost:8001/api/admin/users
```

- [ ] **Step 6: 커밋**

```bash
git add backend/auth/bootstrap.py backend/auth/admin_routes.py backend/main.py
git commit -m "feat(auth): admin 자동 생성 + /api/admin/users 관리 라우트

- bootstrap_admin: startup 시 ADMIN_EMAIL+ADMIN_PASSWORD env로 첫 admin 생성
- /api/admin/users GET/POST/DELETE — admin 권한 필수
- 자기 자신 삭제 방지

작업자: 카리나 (1조)"
```

**Success Criteria:**
- 첫 실행 시 admin 자동 생성 (env 있을 때)
- admin이 친구 계정 생성 가능
- 일반 사용자는 admin 라우트 접근 시 403

---

## Task 2.6 [이순신]: rate limit + 로그인 잠금

**담당:** 이순신
**의존성:** 2.5
**파일:**
- Create: `backend/services/rate_limit_service.py`
- Modify: `backend/auth/routes.py`
- Modify: `backend/main.py`

- [ ] **Step 1: rate_limit_service.py**

```python
"""slowapi rate limit 설정."""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
```

- [ ] **Step 2: main.py에 등록**

```python
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from services.rate_limit_service import limiter

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
app.add_middleware(SlowAPIMiddleware)


def _rate_limit_handler(request, exc):
    from starlette.responses import JSONResponse
    return JSONResponse({"detail": "Too many requests"}, status_code=429)
```

- [ ] **Step 3: 로그인 라우트에 rate limit + 5회 실패 잠금**

`backend/auth/routes.py` login 엔드포인트 갱신:
```python
from datetime import datetime, timedelta, timezone
from services.rate_limit_service import limiter
from models.login_attempt import LoginAttempt


@router.post("/login")
@limiter.limit("5/minute")
async def login(request: Request, payload: LoginRequest, response: Response, db: Session = Depends(get_session)):
    ip = request.client.host if request.client else "unknown"

    # 최근 1시간 내 실패 5회 이상이면 잠금
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    recent_failures = db.query(LoginAttempt).filter(
        LoginAttempt.email == payload.email,
        LoginAttempt.success == False,
        LoginAttempt.attempted_at >= one_hour_ago,
    ).count()
    if recent_failures >= 5:
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in 1 hour.")

    user = db.query(User).filter(User.email == payload.email).one_or_none()
    success = user and verify_password(payload.password, user.password_hash)

    db.add(LoginAttempt(email=payload.email, ip=ip, success=bool(success)))
    db.commit()

    if not success:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    issue_session(response, db, user.id)
    return {"id": user.id, "email": user.email, "is_admin": user.is_admin}
```

- [ ] **Step 4: 검증**

```bash
# 5회 실패 시 잠금 확인
for i in 1 2 3 4 5 6; do
  curl -s -X POST http://localhost:8001/api/auth/login -H "Content-Type: application/json" -d '{"email":"alice@test.com","password":"wrong"}' -w "%{http_code}\n" -o /dev/null
done
```
Expected: 401 401 401 401 401 429

- [ ] **Step 5: 커밋**

```bash
git add backend/services/rate_limit_service.py backend/auth/routes.py backend/main.py
git commit -m "feat(auth): rate limit + 로그인 5회 실패 1시간 잠금

- slowapi: 로그인 5회/분/IP
- login_attempts 테이블 활용 — 최근 1시간 5회 실패 시 429
- IP·이메일 기반 추적

작업자: 이순신 (보안)"
```

**Phase 2 종료 검증:**
- [ ] AUTH_ENABLED=true + admin 로그인 → cookie 받음
- [ ] /api/auth/me 200, 미인증 시 401
- [ ] CSRF Header 없이 POST → 403
- [ ] 5회 실패 → 6번째 429
- [ ] AUTH_ENABLED=false: 회귀 0 (1504개 분리 유지)

---

# Phase 3: similarity finder 웹화 (원영·카리나, ~2일)

## Task 3.1 [원영]: comparator.py → backend/services/similarity_service.py 이식

**담당:** 원영
**의존성:** Phase 1 (DB), Phase 2 무관 (병렬 가능)
**파일:**
- Create: `backend/services/similarity_service.py`
- Create: `backend/tests/test_similarity_service.py`

- [ ] **Step 1: 기존 comparator.py 분석 + Tkinter 의존성 제거**

`tools/similarity_finder/comparator.py` 의 핵심 함수 추출:
- `chunk_problems` (배치 분할)
- `build_user_message` (프롬프트 빌드)
- `parse_response` (Claude JSON 파싱)
- `merge_results` (중복 제거)
- `compute_cost` (토큰 비용 계산)
- `compare` (Claude API 호출 + 재시도 + 캐싱)

→ Tkinter import 제거, `os.environ['ANTHROPIC_API_KEY']` 의존성을 인자로 받도록 리팩토링

- [ ] **Step 2: backend/services/similarity_service.py 작성**

```python
"""similarity finder backend service.

원본: tools/similarity_finder/comparator.py
이식 시 변경:
- Tkinter 의존성 제거
- API 키를 매개변수로 (사용자별 키 사용 위함)
- HWPX 파싱은 backend/services/hwpx_service.py 재사용
"""
import logging
from typing import Optional

import anthropic
from services.hwpx_service import read_hwpx, split_problems

logger = logging.getLogger(__name__)


def chunk_problems(problems: list[dict], chunk_size: int = 10) -> list[list[dict]]:
    """문제 list를 청크로 분할."""
    return [problems[i : i + chunk_size] for i in range(0, len(problems), chunk_size)]


def build_user_message(reference: dict, candidates: list[dict]) -> str:
    """기준 문항 + 후보 문항으로 Claude 프롬프트 빌드."""
    lines = [
        "기준 문항:",
        f"  번호: {reference['number']}",
        f"  내용: {reference['content']}",
        "",
        "후보 문항:",
    ]
    for c in candidates:
        lines.append(f"  - 번호 {c['number']}: {c['content']}")
    lines.append("")
    lines.append("기준과 가장 유사한 후보 번호와 유사도(0~1)를 JSON으로 반환:")
    lines.append('  {"matches": [{"number": int, "similarity": float, "reason": str}]}')
    return "\n".join(lines)


def parse_response(text: str) -> list[dict]:
    """Claude 응답에서 JSON 추출."""
    import json
    import re
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return []
    try:
        data = json.loads(m.group())
        return data.get("matches", [])
    except json.JSONDecodeError:
        logger.warning(f"JSON 파싱 실패: {text[:200]}")
        return []


def compute_cost(input_tokens: int, output_tokens: int, model: str = "claude-sonnet-4-6") -> dict:
    """토큰 → USD → KRW 환산."""
    rates = {
        "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},  # per 1M tokens
        "claude-opus-4-7": {"input": 15.0, "output": 75.0},
    }
    r = rates.get(model, rates["claude-sonnet-4-6"])
    usd = (input_tokens * r["input"] + output_tokens * r["output"]) / 1_000_000
    krw = usd * 1380
    return {"input_tokens": input_tokens, "output_tokens": output_tokens, "usd": usd, "krw": krw}


def compare(
    reference: dict,
    candidates: list[dict],
    api_key: str,
    model: str = "claude-sonnet-4-6",
    max_retries: int = 3,
) -> dict:
    """Claude 호출 → 파싱 → 비용 계산. 재시도 + 캐싱."""
    client = anthropic.Anthropic(api_key=api_key)
    msg = build_user_message(reference, candidates)

    last_err = None
    for attempt in range(max_retries):
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=2048,
                messages=[{"role": "user", "content": msg}],
            )
            text = resp.content[0].text if resp.content else ""
            matches = parse_response(text)
            cost = compute_cost(resp.usage.input_tokens, resp.usage.output_tokens, model)
            return {"matches": matches, "cost": cost, "raw": text}
        except anthropic.APIError as e:
            last_err = e
            logger.warning(f"Claude API 시도 {attempt + 1} 실패: {e}")
            if attempt == max_retries - 1:
                raise
            import time
            time.sleep(2**attempt)  # exponential backoff

    raise RuntimeError(f"Claude API 모든 재시도 실패: {last_err}")


def search(reference_hwpx: bytes, candidate_hwpx_list: list[bytes], api_key: str) -> dict:
    """HWPX 파일들 → 청크 비교 → 결과 dict."""
    ref_text = read_hwpx(reference_hwpx)
    ref_problems = split_problems(ref_text)
    if not ref_problems:
        raise ValueError("기준 HWPX에서 문제를 추출하지 못함")
    reference = ref_problems[0]  # 첫 문제를 기준으로

    all_results = []
    total_cost_krw = 0.0

    for cand_bytes in candidate_hwpx_list:
        cand_text = read_hwpx(cand_bytes)
        cand_problems = split_problems(cand_text)
        for chunk in chunk_problems(cand_problems, chunk_size=10):
            result = compare(reference, chunk, api_key=api_key)
            all_results.extend(result["matches"])
            total_cost_krw += result["cost"]["krw"]

    return {"matches": all_results, "total_cost_krw": total_cost_krw, "count": len(all_results)}
```

- [ ] **Step 3: 단위 테스트**

`backend/tests/test_similarity_service.py`:
```python
from services.similarity_service import chunk_problems, parse_response, compute_cost


def test_chunk_problems_partial():
    problems = [{"number": i} for i in range(1, 24)]
    chunks = chunk_problems(problems, chunk_size=10)
    assert len(chunks) == 3
    assert len(chunks[-1]) == 3


def test_parse_response_extracts_json():
    text = '여기 결과: {"matches": [{"number": 5, "similarity": 0.92}]} 끝'
    matches = parse_response(text)
    assert matches == [{"number": 5, "similarity": 0.92}]


def test_parse_response_invalid():
    assert parse_response("no json here") == []


def test_compute_cost_sonnet():
    cost = compute_cost(1000, 500, "claude-sonnet-4-6")
    assert cost["usd"] > 0
    assert cost["krw"] == cost["usd"] * 1380
```

- [ ] **Step 4: 테스트 → PASS**

```bash
docker compose exec backend pytest tests/test_similarity_service.py -v
```

- [ ] **Step 5: 커밋**

```bash
git add backend/services/similarity_service.py backend/tests/test_similarity_service.py
git commit -m "feat(similarity): comparator.py를 backend/services/similarity_service.py로 이식

- chunk_problems, build_user_message, parse_response, compute_cost, compare, search
- Tkinter 의존성 제거
- API 키를 매개변수로 (사용자별 키 사용)
- HWPX 파싱은 backend/services/hwpx_service.py 재사용
- 재시도 (exponential backoff) + 토큰비용 계산

테스트 4개 통과.

작업자: 장원영 (2조)"
```

**Success Criteria:**
- 4 pytest PASS
- Tkinter import 0건

---

## Task 3.2 [원영]: similarity API 라우트 + BackgroundTasks

**담당:** 원영
**의존성:** 3.1, 4.1 (사용자 API 키 조회 — 임시로 env 키 사용해도 OK)
**파일:**
- Create: `backend/api/similarity.py`
- Modify: `backend/main.py`
- Modify: `backend/models/work_history.py`

- [ ] **Step 1: backend/api/similarity.py**

```python
"""similarity finder API — upload, search, jobs, export."""
import json
import os
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from models.db import get_session
from models.work_history import WorkHistory
from services.similarity_service import search

router = APIRouter(prefix="/api/similarity")


def _get_user_or_anonymous(request: Request) -> Optional[int]:
    """AUTH_ENABLED=false면 None, true면 request.state.user.id."""
    user = getattr(request.state, "user", None)
    return user.id if user else None


def _get_api_key(user_id: Optional[int], db: Session) -> str:
    """사용자별 API 키 → 없으면 env fallback (Phase 4에서 정식 구현)."""
    if user_id is not None:
        from models.user_api_key import UserApiKey
        from auth.crypto import decrypt_api_key
        rec = db.query(UserApiKey).filter(
            UserApiKey.user_id == user_id, UserApiKey.provider == "anthropic"
        ).one_or_none()
        if rec:
            return decrypt_api_key(rec.encrypted_key)
    # Fallback: env (개발 환경)
    return os.environ.get("ANTHROPIC_API_KEY", "")


@router.post("/upload")
async def upload(file: UploadFile, db: Session = Depends(get_session)):
    """HWPX 업로드 → 임시 분석 ID 반환. (Phase 1에선 메모리 저장, 실제론 work_history)"""
    data = await file.read()
    return {"upload_id": "temp", "size": len(data), "filename": file.filename}


def _run_search(work_id: int, ref_bytes: bytes, cand_bytes_list: list[bytes], api_key: str):
    """BackgroundTask 본체."""
    from sqlalchemy.orm import sessionmaker
    from models.db import get_engine
    SessionLocal = sessionmaker(bind=get_engine())
    db = SessionLocal()
    try:
        wh = db.query(WorkHistory).filter(WorkHistory.id == work_id).one()
        wh.status = "running"
        db.commit()

        result = search(ref_bytes, cand_bytes_list, api_key=api_key)

        wh.status = "done"
        wh.metadata_json = result
        db.commit()
    except Exception as e:
        wh.status = "failed"
        wh.metadata_json = {"error": str(e)}
        db.commit()
    finally:
        db.close()


@router.post("/search")
async def start_search(
    request: Request,
    background: BackgroundTasks,
    reference: UploadFile,
    candidates: list[UploadFile],
    db: Session = Depends(get_session),
):
    user_id = _get_user_or_anonymous(request)
    api_key = _get_api_key(user_id, db)
    if not api_key:
        raise HTTPException(status_code=400, detail="API 키 미설정 — Settings에서 등록하세요")

    ref_bytes = await reference.read()
    cand_bytes_list = [await c.read() for c in candidates]

    wh = WorkHistory(
        user_id=user_id or 0,
        work_type="similarity_search",
        status="pending",
    )
    db.add(wh)
    db.commit()
    db.refresh(wh)

    background.add_task(_run_search, wh.id, ref_bytes, cand_bytes_list, api_key)
    return {"job_id": wh.id, "status": "pending"}


@router.get("/jobs/{job_id}")
async def get_job(job_id: int, db: Session = Depends(get_session)):
    wh = db.query(WorkHistory).filter(WorkHistory.id == job_id).one_or_none()
    if not wh:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"id": wh.id, "status": wh.status, "result": wh.metadata_json, "created_at": wh.created_at}
```

- [ ] **Step 2: main.py 라우터 등록**

```python
from api.similarity import router as similarity_router
app.include_router(similarity_router)
```

- [ ] **Step 3: 통합 테스트 (curl)**

```bash
# AUTH_ENABLED=false + ANTHROPIC_API_KEY 환경변수 있는 환경
curl -sf -X POST http://localhost:8001/api/similarity/search \
  -F "reference=@고등수학_1.다항식_3.인수분해_선택_중_유사문항.hwpx" \
  -F "candidates=@고등수학_1.다항식_3.인수분해_선택_중.hwpx" \
  | python -c "import sys, json; print(json.load(sys.stdin))"

# job_id 받아서 상태 조회
curl -sf http://localhost:8001/api/similarity/jobs/1 | python -c "import sys, json; print(json.load(sys.stdin))"
```

- [ ] **Step 4: 커밋**

```bash
git add backend/api/similarity.py backend/main.py
git commit -m "feat(similarity): /api/similarity/* 라우트 + BackgroundTasks

- POST /upload, /search, GET /jobs/{id}
- WorkHistory.status로 진행 추적 (pending → running → done/failed)
- BackgroundTasks로 청크 비교 비동기 실행
- 사용자별 API 키 → 없으면 env fallback (Phase 4에서 정식)

작업자: 장원영 (2조)"
```

**Success Criteria:**
- POST /search → job_id 즉시 반환 (백그라운드 시작)
- GET /jobs/{id} → status 변화 (pending→running→done)
- 결과 JSON에 matches + total_cost_krw

---

## Task 3.3 [카리나]: 프론트 AuthContext + LoginPage + HTTP 클라이언트

**담당:** 카리나
**의존성:** 2.5
**파일:**
- Create: `frontend/src/contexts/AuthContext.jsx`
- Create: `frontend/src/components/LoginPage.jsx`
- Create: `frontend/src/api/client.js`
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1: api/client.js — CSRF 자동 첨부 + cookie credentials**

```javascript
/** HTTP 클라이언트 — CSRF 토큰 자동 첨부 + cookie credentials. */

function getCsrfToken() {
  const m = document.cookie.match(/csrf_token=([^;]+)/);
  return m ? m[1] : '';
}

const BASE = import.meta.env.VITE_API_URL || '';

export async function apiFetch(path, options = {}) {
  const headers = new Headers(options.headers || {});
  const method = (options.method || 'GET').toUpperCase();

  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    const csrf = getCsrfToken();
    if (csrf) headers.set('X-CSRF-Token', csrf);
  }

  const resp = await fetch(`${BASE}${path}`, {
    ...options,
    headers,
    credentials: 'include',  // cookie 전송
  });

  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`API ${resp.status}: ${text}`);
  }

  const ct = resp.headers.get('content-type') || '';
  return ct.includes('application/json') ? resp.json() : resp.text();
}

export const api = {
  get: (path) => apiFetch(path),
  post: (path, body) => apiFetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: typeof body === 'string' ? body : JSON.stringify(body),
  }),
  postForm: (path, formData) => apiFetch(path, { method: 'POST', body: formData }),
  delete: (path) => apiFetch(path, { method: 'DELETE' }),
};
```

- [ ] **Step 2: contexts/AuthContext.jsx**

```jsx
import React, { createContext, useContext, useEffect, useState } from 'react';
import { api } from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [authEnabled, setAuthEnabled] = useState(true);  // backend 응답으로 결정

  useEffect(() => {
    api.get('/api/auth/me')
      .then(u => { setUser(u); setAuthEnabled(true); })
      .catch(err => {
        // AUTH_ENABLED=false면 라우트 자체가 없거나 누구나 통과
        // 401이면 미인증, 그 외는 AUTH_ENABLED=false로 간주
        if (err.message.includes('401')) {
          setUser(null);
          setAuthEnabled(true);
        } else {
          setAuthEnabled(false);
        }
      })
      .finally(() => setLoading(false));
  }, []);

  const login = async (email, password) => {
    const u = await api.post('/api/auth/login', { email, password });
    setUser(u);
    return u;
  };

  const logout = async () => {
    await api.post('/api/auth/logout');
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, authEnabled, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
```

- [ ] **Step 3: components/LoginPage.jsx**

```jsx
import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';

export default function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(email, password);
    } catch (err) {
      setError('이메일 또는 비밀번호가 올바르지 않습니다.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 400, margin: '100px auto', padding: 20, border: '1px solid #ddd', borderRadius: 8 }}>
      <h1 style={{ textAlign: 'center', marginBottom: 24 }}>MathSolution 로그인</h1>
      <form onSubmit={onSubmit}>
        <div style={{ marginBottom: 16 }}>
          <label>이메일</label>
          <input
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            required
            style={{ width: '100%', padding: 8, marginTop: 4 }}
          />
        </div>
        <div style={{ marginBottom: 16 }}>
          <label>비밀번호</label>
          <input
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            required
            style={{ width: '100%', padding: 8, marginTop: 4 }}
          />
        </div>
        {error && <div style={{ color: 'red', marginBottom: 16 }}>{error}</div>}
        <button type="submit" disabled={loading} style={{ width: '100%', padding: 10 }}>
          {loading ? '로그인 중...' : '로그인'}
        </button>
      </form>
      <p style={{ marginTop: 16, fontSize: 12, color: '#666', textAlign: 'center' }}>
        계정이 필요하면 관리자(주공)에게 요청하세요.
      </p>
    </div>
  );
}
```

- [ ] **Step 4: App.jsx 갱신**

```jsx
import { AuthProvider, useAuth } from './contexts/AuthContext';
import LoginPage from './components/LoginPage';

function AuthGate({ children }) {
  const { user, loading, authEnabled } = useAuth();
  if (loading) return <div>로딩 중...</div>;
  if (authEnabled && !user) return <LoginPage />;
  return children;
}

function App() {
  return (
    <AuthProvider>
      <AuthGate>
        {/* 기존 메인 UI */}
      </AuthGate>
    </AuthProvider>
  );
}
```

- [ ] **Step 5: 통합 테스트 (브라우저)**

```bash
docker compose up -d --build frontend
# 브라우저에서 localhost:5173 접속
# AUTH_ENABLED=true 환경에서 로그인 화면 표시 확인
# admin 계정으로 로그인 → 메인 UI 표시
```

- [ ] **Step 6: 커밋**

```bash
git add frontend/src/contexts/ frontend/src/components/LoginPage.jsx frontend/src/api/client.js frontend/src/App.jsx
git commit -m "feat(auth-frontend): AuthContext + LoginPage + CSRF 자동 클라이언트

- AuthContext: useAuth() 훅, login/logout, authEnabled 자동 감지
- LoginPage: 이메일/비밀번호 폼
- api/client.js: cookie credentials + X-CSRF-Token 자동 첨부
- AuthGate: 인증 안 된 상태에선 LoginPage, 인증 후 메인 UI

작업자: 카리나 (1조)"
```

---

## Task 3.4 [원영·카리나]: TabSimilarity 컴포넌트

**담당:** 원영 (백엔드 통신) + 카리나 (UI)
**의존성:** 3.2, 3.3
**파일:**
- Create: `frontend/src/components/TabSimilarity.jsx`
- Modify: `frontend/src/App.jsx` (탭 추가)

- [ ] **Step 1: TabSimilarity.jsx**

```jsx
import React, { useState, useRef, useEffect } from 'react';
import { api, apiFetch } from '../api/client';

export default function TabSimilarity() {
  const [reference, setReference] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [job, setJob] = useState(null);
  const [polling, setPolling] = useState(false);

  useEffect(() => {
    if (!job || job.status === 'done' || job.status === 'failed') {
      setPolling(false);
      return;
    }
    const t = setInterval(async () => {
      try {
        const updated = await api.get(`/api/similarity/jobs/${job.job_id || job.id}`);
        setJob(updated);
      } catch {}
    }, 3000);
    return () => clearInterval(t);
  }, [job]);

  const onStart = async () => {
    if (!reference || candidates.length === 0) {
      alert('기준 + 후보 파일 모두 선택하세요');
      return;
    }
    const fd = new FormData();
    fd.append('reference', reference);
    candidates.forEach(c => fd.append('candidates', c));
    const result = await api.postForm('/api/similarity/search', fd);
    setJob(result);
    setPolling(true);
  };

  return (
    <div style={{ padding: 20 }}>
      <h2>유사문제 검색</h2>
      <div style={{ marginBottom: 16 }}>
        <label>기준 HWPX 파일 (1개)</label>
        <input type="file" accept=".hwpx" onChange={e => setReference(e.target.files[0])} />
      </div>
      <div style={{ marginBottom: 16 }}>
        <label>후보 HWPX 파일 (복수)</label>
        <input type="file" accept=".hwpx" multiple onChange={e => setCandidates([...e.target.files])} />
      </div>
      <button onClick={onStart} disabled={polling}>
        {polling ? '비교 중...' : '유사문제 검색 시작'}
      </button>

      {job && (
        <div style={{ marginTop: 24, padding: 16, border: '1px solid #ddd' }}>
          <h3>작업 #{job.id || job.job_id} — 상태: {job.status}</h3>
          {job.result && job.status === 'done' && (
            <div>
              <p>발견된 유사문항: {job.result.count}개</p>
              <p>예상 비용: ₩{Math.round(job.result.total_cost_krw || 0)}</p>
              <ul>
                {(job.result.matches || []).slice(0, 20).map((m, i) => (
                  <li key={i}>#{m.number} — 유사도 {(m.similarity * 100).toFixed(1)}% — {m.reason || ''}</li>
                ))}
              </ul>
            </div>
          )}
          {job.status === 'failed' && (
            <p style={{ color: 'red' }}>실패: {JSON.stringify(job.result)}</p>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: App.jsx에 탭 추가**

```jsx
// 기존 탭 list에 추가
const tabs = [
  // ...
  { key: 'similarity', label: '유사문제 검색', component: TabSimilarity },
];
```

- [ ] **Step 3: 통합 테스트 (브라우저)**

기준 HWPX 1개 + 후보 HWPX 1개 업로드 → 비교 시작 → 3초 폴링으로 결과 확인

- [ ] **Step 4: 커밋**

```bash
git add frontend/src/components/TabSimilarity.jsx frontend/src/App.jsx
git commit -m "feat(similarity-frontend): TabSimilarity 컴포넌트 + 탭 통합

- 기준 + 후보 HWPX 업로드
- /api/similarity/search 호출 → 3초 간격 폴링
- 결과: 매치 list + 토큰비용

작업자: 장원영·카리나"
```

**Phase 3 종료 검증:**
- [ ] AUTH_ENABLED=true로 로그인 → 유사문제 검색 탭 사용 → 결과 표시
- [ ] 회귀: 기존 7 탭 모두 정상

---

# Phase 4: 사용자별 데이터 (카리나·이순신, ~1.5일)

## Task 4.1 [카리나·이순신]: 사용자별 API 키 라우트

**담당:** 카리나 (라우트) + 이순신 (Fernet 통합)
**의존성:** 2.5, 4.0(Fernet은 2.1에서 이미 구현)
**파일:**
- Create: `backend/services/user_api_key_service.py`
- Create: `backend/api/user.py`
- Modify: `backend/main.py`
- Create: `backend/tests/test_user_api_keys.py`

- [ ] **Step 1: user_api_key_service.py**

```python
"""사용자별 API 키 CRUD + 암호화."""
from sqlalchemy.orm import Session
from auth.crypto import encrypt_api_key, decrypt_api_key
from models.user_api_key import UserApiKey


def upsert(db: Session, user_id: int, provider: str, plain_key: str) -> None:
    encrypted = encrypt_api_key(plain_key)
    existing = db.query(UserApiKey).filter(
        UserApiKey.user_id == user_id, UserApiKey.provider == provider
    ).one_or_none()
    if existing:
        existing.encrypted_key = encrypted
    else:
        db.add(UserApiKey(user_id=user_id, provider=provider, encrypted_key=encrypted))
    db.commit()


def get_decrypted(db: Session, user_id: int, provider: str) -> str | None:
    rec = db.query(UserApiKey).filter(
        UserApiKey.user_id == user_id, UserApiKey.provider == provider
    ).one_or_none()
    if not rec:
        return None
    return decrypt_api_key(rec.encrypted_key)


def list_providers(db: Session, user_id: int) -> list[str]:
    rows = db.query(UserApiKey.provider).filter(UserApiKey.user_id == user_id).all()
    return [r[0] for r in rows]


def delete(db: Session, user_id: int, provider: str) -> bool:
    deleted = db.query(UserApiKey).filter(
        UserApiKey.user_id == user_id, UserApiKey.provider == provider
    ).delete()
    db.commit()
    return deleted > 0
```

- [ ] **Step 2: api/user.py**

```python
"""사용자별 API 키·작업 이력 라우트."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from models.db import get_session
from models.user import User
from models.work_history import WorkHistory
from services import user_api_key_service as keys_svc

router = APIRouter(prefix="/api/user")


def require_user(request: Request) -> User:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


class ApiKeyRequest(BaseModel):
    api_key: str


@router.put("/api-keys/{provider}")
async def set_key(provider: str, body: ApiKeyRequest, user: User = Depends(require_user), db: Session = Depends(get_session)):
    if provider not in ("anthropic", "gemini"):
        raise HTTPException(status_code=400, detail="provider must be 'anthropic' or 'gemini'")
    keys_svc.upsert(db, user.id, provider, body.api_key)
    return {"provider": provider, "saved": True}


@router.delete("/api-keys/{provider}", status_code=204)
async def delete_key(provider: str, user: User = Depends(require_user), db: Session = Depends(get_session)):
    keys_svc.delete(db, user.id, provider)


@router.get("/api-keys")
async def list_keys(user: User = Depends(require_user), db: Session = Depends(get_session)):
    return {"providers": keys_svc.list_providers(db, user.id)}


@router.get("/history")
async def get_history(user: User = Depends(require_user), db: Session = Depends(get_session), limit: int = 50):
    rows = (
        db.query(WorkHistory)
        .filter(WorkHistory.user_id == user.id)
        .order_by(WorkHistory.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {"id": r.id, "work_type": r.work_type, "status": r.status, "created_at": r.created_at, "metadata": r.metadata_json}
        for r in rows
    ]
```

- [ ] **Step 3: main.py 등록 + 테스트**

```python
from api.user import router as user_router
app.include_router(user_router)
```

- [ ] **Step 4: 커밋**

```bash
git add backend/services/user_api_key_service.py backend/api/user.py backend/main.py
git commit -m "feat(user): 사용자별 API 키 + 작업 이력 라우트

- PUT/DELETE/GET /api/user/api-keys
- GET /api/user/history (사용자별 작업 50건)
- Fernet 암호화 (인증된 사용자만)

작업자: 카리나·이순신"
```

---

## Task 4.2 [카리나]: TabSettings 컴포넌트

**담당:** 카리나
**의존성:** 4.1
**파일:**
- Create: `frontend/src/components/TabSettings.jsx`

- [ ] **Step 1: TabSettings.jsx**

```jsx
import React, { useEffect, useState } from 'react';
import { api } from '../api/client';

export default function TabSettings() {
  const [providers, setProviders] = useState([]);
  const [history, setHistory] = useState([]);
  const [anthropicKey, setAnthropicKey] = useState('');
  const [geminiKey, setGeminiKey] = useState('');
  const [msg, setMsg] = useState('');

  const reload = async () => {
    const p = await api.get('/api/user/api-keys');
    setProviders(p.providers);
    const h = await api.get('/api/user/history');
    setHistory(h);
  };

  useEffect(() => { reload(); }, []);

  const saveKey = async (provider, key) => {
    if (!key.startsWith('sk-') && !key.startsWith('AIza')) {
      setMsg(`${provider} 키 형식이 이상합니다 (sk- 또는 AIza 시작)`);
      return;
    }
    await api.put = (path, body) => api.post(path.replace('/api/', '/api/'), body);  // PUT 추가 필요
    // 실제: fetch with method PUT
    const csrf = document.cookie.match(/csrf_token=([^;]+)/)?.[1];
    await fetch(`/api/user/api-keys/${provider}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
      credentials: 'include',
      body: JSON.stringify({ api_key: key }),
    });
    setMsg(`${provider} 키 저장됨`);
    reload();
  };

  return (
    <div style={{ padding: 20 }}>
      <h2>설정</h2>

      <section style={{ marginBottom: 32 }}>
        <h3>API 키</h3>
        <p>등록된 provider: {providers.join(', ') || '없음'}</p>
        <div style={{ marginBottom: 12 }}>
          <label>Anthropic 키 (sk-ant-...)</label>
          <input type="password" value={anthropicKey} onChange={e => setAnthropicKey(e.target.value)} style={{ width: 400 }} />
          <button onClick={() => saveKey('anthropic', anthropicKey)}>저장</button>
        </div>
        <div>
          <label>Gemini 키 (AIza...)</label>
          <input type="password" value={geminiKey} onChange={e => setGeminiKey(e.target.value)} style={{ width: 400 }} />
          <button onClick={() => saveKey('gemini', geminiKey)}>저장</button>
        </div>
        {msg && <p style={{ color: 'green' }}>{msg}</p>}
      </section>

      <section>
        <h3>작업 이력 (최근 50건)</h3>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr><th>ID</th><th>유형</th><th>상태</th><th>일시</th></tr>
          </thead>
          <tbody>
            {history.map(h => (
              <tr key={h.id}>
                <td>{h.id}</td>
                <td>{h.work_type}</td>
                <td>{h.status}</td>
                <td>{new Date(h.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
```

- [ ] **Step 2: api/client.js에 PUT 추가**

```javascript
export const api = {
  // ...기존
  put: (path, body) => apiFetch(path, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: typeof body === 'string' ? body : JSON.stringify(body),
  }),
};
```

- [ ] **Step 3: App.jsx에 탭 추가 + 커밋**

```bash
git add frontend/src/components/TabSettings.jsx frontend/src/api/client.js frontend/src/App.jsx
git commit -m "feat(settings-frontend): TabSettings — API 키 입력 + 작업 이력

작업자: 카리나"
```

---

## Task 4.3 [카리나]: 기존 라우트에 사용자별 키 통합

**담당:** 카리나
**의존성:** 4.1
**파일:**
- Modify: `backend/services/claude_service.py` (또는 호출처)

- [ ] **Step 1: claude_service.py 호출 시 user_id로 키 조회**

```python
# 기존: api_key = os.environ['ANTHROPIC_API_KEY']
# 변경:
def get_api_key_for_request(request, db) -> str:
    user = getattr(request.state, "user", None)
    if user:
        from services.user_api_key_service import get_decrypted
        key = get_decrypted(db, user.id, "anthropic")
        if key:
            return key
    return os.environ.get("ANTHROPIC_API_KEY", "")
```

기존 generate / solve_variant / refine / hwpx-* 라우트 모두 갱신.

- [ ] **Step 2: 커밋**

```bash
git add backend/services/claude_service.py backend/main.py
git commit -m "feat(user): 기존 Claude 호출 라우트에 사용자별 API 키 통합

- request.state.user → user_api_keys 조회 → 사용자 키로 호출
- 사용자 키 없으면 env fallback (개발 환경)

작업자: 카리나"
```

**Phase 4 종료 검증:**
- [ ] 사용자가 자기 키 등록 → 유사문항 생성 시 그 키로 청구됨
- [ ] /api/user/history 사용자별 분리 확인

---

# Phase 5: 배포 + 침투 테스트 (카리나·이순신·갈량, ~1일)

## Task 5.1 [카리나]: backend Dockerfile에 frontend 빌드 통합

**담당:** 카리나
**의존성:** Phase 4 완료
**파일:**
- Modify: `backend/Dockerfile`
- Modify: `backend/main.py`

- [ ] **Step 1: backend/Dockerfile multi-stage 빌드**

```dockerfile
# Stage 1: frontend 빌드
FROM node:20-alpine AS frontend-build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: backend
FROM python:3.14-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./

# frontend 빌드 산출물 복사
COPY --from=frontend-build /app/dist ./static

EXPOSE 8001
CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8001"]
```

- [ ] **Step 2: main.py에 StaticFiles**

```python
from fastapi.staticfiles import StaticFiles
import os

if os.path.isdir("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")
```

- [ ] **Step 3: 커밋**

```bash
git add backend/Dockerfile backend/main.py
git commit -m "feat(deploy): multi-stage Dockerfile + FastAPI StaticFiles

- frontend npm build → backend static/ 복사
- alembic upgrade head 컨테이너 시작 시 자동 실행
- 단일 컨테이너로 frontend + backend 동시 serve

작업자: 카리나"
```

---

## Task 5.2 [이순신]: CORS 도메인 제한 + HTTPS redirect

**담당:** 이순신
**의존성:** 5.1
**파일:**
- Modify: `backend/main.py`

- [ ] **Step 1: CORSMiddleware 갱신**

```python
import os

allowed_origins_raw = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:5174")
allowed_origins = [o.strip() for o in allowed_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,  # ← "*" 폐기
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["x-csrf-token"],
)
```

- [ ] **Step 2: 커밋**

```bash
git add backend/main.py
git commit -m "fix(security): CORS allow_origins=[*] → 환경변수 기반 도메인 제한

- ALLOWED_ORIGINS env (콤마 구분)
- allow_credentials=True
- expose_headers에 x-csrf-token (프론트가 헤더 읽도록)

작업자: 이순신"
```

---

## Task 5.3 [카리나]: Railway 프로젝트 생성 + 배포

**담당:** 카리나
**의존성:** 5.1, 5.2
**비주얼 작업** — Railway 대시보드에서 직접

- [ ] **Step 1: Railway CLI 설치 또는 dashboard 접속**

```bash
# CLI 설치 (선택)
npm i -g @railway/cli
railway login
```

- [ ] **Step 2: Railway 프로젝트 생성**

Railway dashboard:
1. New Project → Deploy from GitHub repo
2. Repo 선택: `inbeom4567/MSSC_BEOM`
3. Branch: `main` (또는 worktree 머지 후 main)

- [ ] **Step 3: PostgreSQL 1-click 추가**

Railway → Add Service → Database → PostgreSQL
→ DATABASE_URL 자동 주입

- [ ] **Step 4: 환경변수 등록**

| 변수 | 값 |
|---|---|
| `AUTH_ENABLED` | `true` (배포 후 친구 공유 시) |
| `MASTER_ENC_KEY` | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` 결과 |
| `ADMIN_EMAIL` | 주공 이메일 |
| `ADMIN_PASSWORD` | 강력한 임시 비밀번호 (첫 로그인 후 변경) |
| `ALLOWED_ORIGINS` | `https://your-app.up.railway.app` |
| `ANTHROPIC_API_KEY` | (선택) fallback 키 |
| `GEMINI_API_KEY` | (선택) fallback 키 |

- [ ] **Step 5: 첫 배포 후 검증**

```bash
curl -sf https://your-app.up.railway.app/api/health
```
Expected: `{"status":"ok"}`

브라우저로 접속 → 로그인 화면 확인 → admin 로그인 → 모든 탭 동작

- [ ] **Step 6: 갈량의 진행일지에 Railway URL + 배포 일시 기록**

---

## Task 5.4 [이순신]: 침투 테스트 7항목 검증

**담당:** 이순신
**의존성:** 5.3
**문서:** Phase 5 침투 테스트 보고서

- [ ] **Step 1: SQL Injection** — `email='admin' OR '1'='1` 시도 → 401 확인
- [ ] **Step 2: XSS** — 사용자 이메일 필드에 `<script>alert(1)</script>` → React escape 확인
- [ ] **Step 3: CSRF** — 헤더 누락 POST → 403 확인
- [ ] **Step 4: IDOR** — 사용자 A로 로그인 후 사용자 B의 work_history GET 시도 → 403 또는 빈 결과
- [ ] **Step 5: brute force** — 6번째 로그인 → 429
- [ ] **Step 6: API 키 노출** — DB 직접 조회로 평문 0건 확인
- [ ] **Step 7: HTTPS** — http:// → https:// redirect 확인

각 항목 결과를 `docs/superpowers/plans/2026-05-04-pentest-report.md` 작성.

- [ ] **Step 8: 커밋**

```bash
git add docs/superpowers/plans/2026-05-04-pentest-report.md
git commit -m "docs(security): Phase 5 침투 테스트 보고서

7항목 검증 결과 + 발견 결함 + 조치 사항.

작업자: 이순신"
```

---

## Task 5.5 [갈량]: 진행일지 + CLAUDE.md 갱신 + PR 작성

**담당:** 갈량
**의존성:** 5.4
**파일:**
- Modify: `진행일지.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: 진행일지에 Phase 1~5 마감 항목 추가**
- [ ] **Step 2: CLAUDE.md에 인증·DB 운영 안내 + 새 환경변수 표 추가**
- [ ] **Step 3: PR 생성**

```bash
gh pr create --title "feat: 인증 시스템 + similarity finder 웹화 + Railway 배포" \
  --body "$(cat <<'EOF'
## Summary

- 인증 시스템 (argon2id + HttpOnly Cookie + CSRF Double-Submit)
- PostgreSQL + alembic
- similarity finder 웹화 (Tkinter → React 탭)
- 사용자별 API 키 (Fernet 암호화) + 작업 이력
- Railway 배포 (단일 컨테이너, FastAPI StaticFiles)
- 침투 테스트 7항목 검증

## 분량
약 6.5~8.5일 (실제: ?)

## 회귀
AUTH_ENABLED=false 시 baseline과 동일 동작 (hwpx-analyze 1504개 유지).

## 정본
- spec: docs/superpowers/specs/2026-05-04-auth-similarity-web-design.md v3
- plan: docs/superpowers/plans/2026-05-04-auth-similarity-web.md
- pentest: docs/superpowers/plans/2026-05-04-pentest-report.md

## Test plan
- [ ] AUTH_ENABLED=false: 7 탭 회귀 0
- [ ] AUTH_ENABLED=true + 로그인: similarity 탭 정상 동작
- [ ] 침투 테스트 7항목 통과
- [ ] Railway 배포 health 200
- [ ] admin 자동 생성 동작

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

**Phase 5 종료 검증:**
- [ ] Railway 배포 URL 접속 가능
- [ ] HTTPS 자동
- [ ] 친구 강사 URL 공유 → 로그인 가능
- [ ] 침투 테스트 7항목 PASS
- [ ] 회귀: AUTH_ENABLED=false 시 baseline 동일

---

# 종합 검증 (전체 plan 종료 시)

- [ ] `git log --oneline` 으로 Phase별 커밋 그룹 깔끔
- [ ] 진행일지 갱신
- [ ] CLAUDE.md 갱신
- [ ] PR 생성 + main 머지
- [ ] Railway 운영 URL 동작
- [ ] 메모리 갱신: `project_auth_similarity_progress.md`

---

## 분량 추정 vs 실제

| Phase | 추정 | 담당 |
|---|---|---|
| 1 인프라 | 1일 | 카리나 |
| 2 인증 | 2일 | 카리나·이순신 |
| 3 similarity 웹화 | 2일 | 원영·카리나 |
| 4 사용자별 데이터 | 1.5일 | 카리나·이순신 |
| 5 배포 + 침투 | 1일 | 카리나·이순신·갈량 |
| **총** | **6.5~8.5일** | |

병렬 가능: Phase 2의 이순신 작업 ↔ Phase 3의 원영 backend 이식

---

## 변경 이력

| 일자 | 버전 | 변경 |
|---|---|---|
| 2026-05-04 | v1 | 신설 — design doc v3 + brainstorming Phase 2 결정 반영. 5 Phase × ~25 Task. TDD + 회귀 검증 강조 |
