# 유사문제 찾기 GUI 앱 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기준 문제 HWPX와 문제집 HWPX를 입력받아 유사 문제 번호(쌍둥이 + 유형유사)를 찾아주는 로컬 Tkinter GUI 앱 구현.

**Architecture:** `tools/similarity_finder/` 독립 폴더에 GUI(main.py) + Claude 래퍼(comparator.py) + 프롬프트. 기존 `backend/services/hwpx_service.py`의 `read_hwpx`, `split_problems` 재활용. Claude Sonnet 4.6 기본 + Opus 4.7 재확인 옵션, prompt caching 적용.

**Tech Stack:** Python 3.14, Tkinter (stdlib), anthropic==0.86.0 (sync client), pytest (테스트), threading.

---

## File Structure

| 경로 | 역할 |
|------|------|
| `tools/similarity_finder/__init__.py` | 패키지 마커 (빈 파일) |
| `tools/similarity_finder/prompt.txt` | Claude 시스템 프롬프트 |
| `tools/similarity_finder/comparator.py` | Claude API 래퍼, 프롬프트 빌더, JSON 파서, 배치 로직 |
| `tools/similarity_finder/main.py` | Tkinter GUI 진입점 |
| `tools/similarity_finder/run.bat` | Windows 더블클릭 실행 스크립트 |
| `tools/similarity_finder/.gitignore` | logs/ 제외 |
| `tools/similarity_finder/tests/test_comparator.py` | comparator 단위 테스트 (pure 함수) |

**재활용 파일 (수정 없음):**
- `backend/services/hwpx_service.py` — `read_hwpx(bytes) -> str`, `split_problems(str) -> list[{"number": int, "text": str}]`
- `backend/.env` — `ANTHROPIC_API_KEY`

---

## Task 1: 프로젝트 스켈레톤 + 프롬프트 파일

**Files:**
- Create: `tools/similarity_finder/__init__.py`
- Create: `tools/similarity_finder/tests/__init__.py`
- Create: `tools/similarity_finder/.gitignore`
- Create: `tools/similarity_finder/prompt.txt`

- [ ] **Step 1: 디렉터리 + 빈 `__init__.py` 2개 생성**

```bash
mkdir -p tools/similarity_finder/tests tools/similarity_finder/logs
```

`tools/similarity_finder/__init__.py`:
```python
```

`tools/similarity_finder/tests/__init__.py`:
```python
```

- [ ] **Step 2: `.gitignore` 작성**

`tools/similarity_finder/.gitignore`:
```
logs/
*.log
__pycache__/
*.pyc
```

- [ ] **Step 3: 시스템 프롬프트 작성**

`tools/similarity_finder/prompt.txt`:
```
너는 고등학교 수학 문제 유사도 판정기다.

입력:
- 원본 문제 1개 (선생님이 기준으로 삼는 문제)
- 문제집 N개 (각각 번호가 붙어있음)

판정 기준:
[쌍둥이] — 같은 개념·구조·풀이 방법이며 숫자·변수만 다른 수준. 변형문항 관계.
[유형유사] — 같은 단원·개념·난이도이나 문제 구조가 조금 달라 쌍둥이는 아님.
[관련없음] — 개념이 다르거나 난이도 차이가 큼. 출력에서 제외.

출력은 JSON 한 덩어리만. 다른 텍스트 금지:
{
  "쌍둥이": [{"번호": 12, "이유": "..."}],
  "유형유사": [{"번호": 5, "이유": "..."}]
}

이유는 한 줄 (30자 이내, 한국어).
쌍둥이/유형유사 어느 쪽에도 해당하지 않으면 출력에서 제외한다.
```

- [ ] **Step 4: 커밋**

```bash
git add tools/similarity_finder/
git commit -m "feat(similarity-finder): 프로젝트 스켈레톤 + 시스템 프롬프트"
```

---

## Task 2: comparator.build_user_message — 프롬프트 빌더 (TDD)

**Files:**
- Test: `tools/similarity_finder/tests/test_comparator.py`
- Create: `tools/similarity_finder/comparator.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tools/similarity_finder/tests/test_comparator.py`:
```python
"""comparator 단위 테스트."""
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가 (comparator 임포트용)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from tools.similarity_finder.comparator import build_user_message


def test_build_user_message_basic():
    original = "이차함수 f(x) = x^2 - 2x의 최솟값은?"
    problems = [
        {"number": 1, "text": "일차함수 문제"},
        {"number": 3, "text": "이차함수 f(x) = x^2 + 4x의 최솟값은?"},
    ]
    result = build_user_message(original, problems)
    assert "# 원본 문제" in result
    assert "이차함수 f(x) = x^2 - 2x의 최솟값은?" in result
    assert "# 문제집 (총 2문제)" in result
    assert "## 1번" in result
    assert "## 3번" in result
    assert "일차함수 문제" in result
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd "c:/Users/tnaak/OneDrive/바탕 화면/MathSolution" && python -m pytest tools/similarity_finder/tests/test_comparator.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_user_message'` 또는 모듈 없음

- [ ] **Step 3: 최소 구현**

`tools/similarity_finder/comparator.py`:
```python
"""유사문제 찾기 comparator — Claude API 래퍼 + 프롬프트 빌더 + JSON 파서."""
from __future__ import annotations


def build_user_message(original: str, problems: list[dict]) -> str:
    """원본 문제 + 문제집을 Claude에게 보낼 사용자 메시지로 조립.

    Args:
        original: 원본 HWPX에서 추출한 텍스트.
        problems: split_problems() 결과. 각 항목 {"number": int, "text": str}.

    Returns:
        Claude user message 전체 문자열.
    """
    lines = ["# 원본 문제", original.strip(), "", f"# 문제집 (총 {len(problems)}문제)"]
    for p in problems:
        lines.append(f"## {p['number']}번")
        lines.append(p['text'].strip())
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tools/similarity_finder/tests/test_comparator.py -v`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add tools/similarity_finder/comparator.py tools/similarity_finder/tests/test_comparator.py
git commit -m "feat(similarity-finder): build_user_message 프롬프트 빌더"
```

---

## Task 3: comparator.parse_response — JSON 파서 (TDD)

**Files:**
- Modify: `tools/similarity_finder/tests/test_comparator.py`
- Modify: `tools/similarity_finder/comparator.py`

- [ ] **Step 1: 실패하는 테스트 추가**

`tools/similarity_finder/tests/test_comparator.py`에 추가:
```python
from tools.similarity_finder.comparator import parse_response


def test_parse_response_valid_json():
    raw = '{"쌍둥이": [{"번호": 12, "이유": "동일 구조"}], "유형유사": [{"번호": 5, "이유": "같은 단원"}]}'
    result = parse_response(raw)
    assert result["쌍둥이"] == [{"번호": 12, "이유": "동일 구조"}]
    assert result["유형유사"] == [{"번호": 5, "이유": "같은 단원"}]


def test_parse_response_with_markdown_fence():
    raw = '```json\n{"쌍둥이": [], "유형유사": []}\n```'
    result = parse_response(raw)
    assert result == {"쌍둥이": [], "유형유사": []}


def test_parse_response_missing_keys_fills_empty():
    raw = '{"쌍둥이": [{"번호": 1, "이유": "."}]}'
    result = parse_response(raw)
    assert result["쌍둥이"] == [{"번호": 1, "이유": "."}]
    assert result["유형유사"] == []


def test_parse_response_invalid_raises():
    import pytest
    with pytest.raises(ValueError):
        parse_response("아무 JSON도 아님")
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tools/similarity_finder/tests/test_comparator.py -v`
Expected: FAIL — `cannot import name 'parse_response'`

- [ ] **Step 3: 구현 추가**

`tools/similarity_finder/comparator.py`에 추가:
```python
import json
import re


def parse_response(raw: str) -> dict:
    """Claude 응답에서 JSON을 추출해 {"쌍둥이": [...], "유형유사": [...]} 반환.

    마크다운 코드펜스(```json ... ```)를 벗기고, 키가 누락되면 빈 리스트로 채움.
    유효한 JSON이 없으면 ValueError.
    """
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    else:
        brace = re.search(r"\{.*\}", text, re.DOTALL)
        if brace:
            text = brace.group(0)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Claude 응답을 JSON으로 파싱 실패: {e}")

    if not isinstance(data, dict):
        raise ValueError(f"응답이 객체가 아님: {type(data).__name__}")

    return {
        "쌍둥이": data.get("쌍둥이", []),
        "유형유사": data.get("유형유사", []),
    }
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tools/similarity_finder/tests/test_comparator.py -v`
Expected: 5 passed

- [ ] **Step 5: 커밋**

```bash
git add tools/similarity_finder/comparator.py tools/similarity_finder/tests/test_comparator.py
git commit -m "feat(similarity-finder): parse_response JSON 파서"
```

---

## Task 4: comparator.chunk_problems — 배치 분할 (TDD)

**Files:**
- Modify: `tools/similarity_finder/tests/test_comparator.py`
- Modify: `tools/similarity_finder/comparator.py`

- [ ] **Step 1: 실패하는 테스트 추가**

`tools/similarity_finder/tests/test_comparator.py`에 추가:
```python
from tools.similarity_finder.comparator import chunk_problems, merge_results


def test_chunk_problems_under_limit():
    problems = [{"number": i, "text": f"p{i}"} for i in range(50)]
    chunks = chunk_problems(problems, chunk_size=100)
    assert len(chunks) == 1
    assert len(chunks[0]) == 50


def test_chunk_problems_exact_boundary():
    problems = [{"number": i, "text": f"p{i}"} for i in range(200)]
    chunks = chunk_problems(problems, chunk_size=100)
    assert len(chunks) == 2
    assert len(chunks[0]) == 100
    assert len(chunks[1]) == 100


def test_chunk_problems_partial_last():
    problems = [{"number": i, "text": f"p{i}"} for i in range(250)]
    chunks = chunk_problems(problems, chunk_size=100)
    assert [len(c) for c in chunks] == [100, 100, 50]


def test_merge_results_combines_and_dedupes():
    a = {"쌍둥이": [{"번호": 1, "이유": "a"}], "유형유사": [{"번호": 5, "이유": "b"}]}
    b = {"쌍둥이": [{"번호": 2, "이유": "c"}], "유형유사": [{"번호": 5, "이유": "dup"}]}
    merged = merge_results([a, b])
    assert sorted(x["번호"] for x in merged["쌍둥이"]) == [1, 2]
    # 유형유사에 중복 번호(5)는 첫 번째만 유지
    assert [x["번호"] for x in merged["유형유사"]] == [5]
    assert merged["유형유사"][0]["이유"] == "b"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tools/similarity_finder/tests/test_comparator.py -v`
Expected: FAIL — `cannot import name 'chunk_problems'`

- [ ] **Step 3: 구현 추가**

`tools/similarity_finder/comparator.py`에 추가:
```python
def chunk_problems(problems: list[dict], chunk_size: int = 100) -> list[list[dict]]:
    """문제집이 너무 크면 chunk_size 단위로 분할."""
    if not problems:
        return []
    return [problems[i:i + chunk_size] for i in range(0, len(problems), chunk_size)]


def merge_results(chunk_results: list[dict]) -> dict:
    """배치 결과들을 병합. 번호 중복은 첫 번째 발견만 유지."""
    merged = {"쌍둥이": [], "유형유사": []}
    seen = {"쌍둥이": set(), "유형유사": set()}
    for result in chunk_results:
        for bucket in ("쌍둥이", "유형유사"):
            for item in result.get(bucket, []):
                num = item.get("번호")
                if num is None or num in seen[bucket]:
                    continue
                seen[bucket].add(num)
                merged[bucket].append(item)
    return merged
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tools/similarity_finder/tests/test_comparator.py -v`
Expected: 9 passed

- [ ] **Step 5: 커밋**

```bash
git add tools/similarity_finder/comparator.py tools/similarity_finder/tests/test_comparator.py
git commit -m "feat(similarity-finder): chunk_problems + merge_results 배치 로직"
```

---

## Task 5: comparator.compare — Claude API 통합

**Files:**
- Modify: `tools/similarity_finder/comparator.py`

> **참고:** 이 태스크는 실제 Claude API를 호출하므로 TDD 대신 mock 테스트 + 수동 검증. API 키 로드 방식은 `backend/services/claude_service.py`의 패턴을 따름.

- [ ] **Step 1: mock 테스트 작성**

`tools/similarity_finder/tests/test_comparator.py`에 추가:
```python
from unittest.mock import MagicMock, patch


def test_compare_calls_claude_and_parses():
    fake_response = MagicMock()
    fake_response.content = [MagicMock(text='{"쌍둥이":[{"번호":1,"이유":"test"}],"유형유사":[]}')]

    from tools.similarity_finder import comparator
    with patch.object(comparator, "_load_client") as mock_load:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = fake_response
        mock_load.return_value = mock_client

        result = comparator.compare(
            original="문제 원본",
            problems=[{"number": 1, "text": "p1"}],
            model="claude-sonnet-4-6",
        )

        assert result["쌍둥이"] == [{"번호": 1, "이유": "test"}]
        assert result["유형유사"] == []
        assert mock_client.messages.create.called


def test_compare_auto_batches_large_input():
    """501개 문제는 6개 청크로 분할되어 6번 호출."""
    fake_response = MagicMock()
    fake_response.content = [MagicMock(text='{"쌍둥이":[],"유형유사":[]}')]

    from tools.similarity_finder import comparator
    with patch.object(comparator, "_load_client") as mock_load:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = fake_response
        mock_load.return_value = mock_client

        problems = [{"number": i, "text": f"p{i}"} for i in range(501)]
        comparator.compare(original="x", problems=problems, model="claude-sonnet-4-6")

        assert mock_client.messages.create.call_count == 6
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tools/similarity_finder/tests/test_comparator.py -v`
Expected: FAIL — `cannot import name 'compare'` / `_load_client`

- [ ] **Step 3: 구현 추가**

`tools/similarity_finder/comparator.py`에 추가:
```python
import os
from pathlib import Path

import anthropic


_SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompt.txt"
_BACKEND_ENV_PATH = Path(__file__).resolve().parent.parent.parent / "backend" / ".env"


def _load_system_prompt() -> str:
    return _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


def _load_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    if _BACKEND_ENV_PATH.exists():
        for line in _BACKEND_ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("ANTHROPIC_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("ANTHROPIC_API_KEY가 backend/.env 또는 환경변수에 없습니다.")


def _load_client():
    return anthropic.Anthropic(api_key=_load_api_key())


def compare(
    original: str,
    problems: list[dict],
    model: str = "claude-sonnet-4-6",
    chunk_size: int = 100,
    progress_callback=None,
) -> dict:
    """원본 문제와 문제집을 비교해 유사 문제 번호 반환.

    Args:
        original: 원본 문제 텍스트 (`read_hwpx` 결과).
        problems: `split_problems` 결과 리스트.
        model: claude-sonnet-4-6 또는 claude-opus-4-7.
        chunk_size: 한 번에 보낼 최대 문제 수.
        progress_callback: 진행 알림 callable(str). 없으면 무시.

    Returns:
        {"쌍둥이": [{"번호": int, "이유": str}, ...], "유형유사": [...]}
    """
    system = _load_system_prompt()
    client = _load_client()
    chunks = chunk_problems(problems, chunk_size=chunk_size)

    chunk_results = []
    for idx, chunk in enumerate(chunks, 1):
        if progress_callback:
            progress_callback(f"Claude 호출 중 ({idx}/{len(chunks)})…")

        user_message = build_user_message(original, chunk)
        raw_text = _call_claude(client, system, user_message, model)
        chunk_results.append(parse_response(raw_text))

    return merge_results(chunk_results)


def _call_claude(client, system: str, user: str, model: str, retry: bool = True) -> str:
    """Claude 호출 + JSON 파싱 실패 시 1회 재시도."""
    try:
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
        )
        return response.content[0].text
    except Exception:
        if retry:
            return _call_claude(client, system, user, model, retry=False)
        raise
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tools/similarity_finder/tests/test_comparator.py -v`
Expected: 11 passed

- [ ] **Step 5: 커밋**

```bash
git add tools/similarity_finder/comparator.py tools/similarity_finder/tests/test_comparator.py
git commit -m "feat(similarity-finder): compare 함수 Claude API 통합 + 배치"
```

---

## Task 6: main.py — Tkinter 기본 레이아웃

**Files:**
- Create: `tools/similarity_finder/main.py`

- [ ] **Step 1: 기본 창 + 위젯 배치 구현**

`tools/similarity_finder/main.py`:
```python
"""유사문제 찾기 GUI — Tkinter 기반."""
from __future__ import annotations

import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# backend/services/hwpx_service import을 위한 경로 추가
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from services.hwpx_service import read_hwpx, split_problems  # noqa: E402

sys.path.insert(0, str(PROJECT_ROOT))
from tools.similarity_finder import comparator  # noqa: E402


class SimilarityFinderApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("유사문제 찾기")
        self.root.geometry("700x600")

        self.original_path = tk.StringVar()
        self.problems_path = tk.StringVar()
        self.model_var = tk.StringVar(value="claude-sonnet-4-6")
        self.last_result: dict | None = None
        self.is_searching = False

        self._build_ui()

    def _build_ui(self):
        frm = ttk.Frame(self.root, padding=10)
        frm.pack(fill=tk.BOTH, expand=True)

        # 원본 파일
        ttk.Label(frm, text="원본 문제 (1문제):").grid(row=0, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.original_path, width=60).grid(row=1, column=0, padx=(0, 5), sticky="we")
        ttk.Button(frm, text="파일 선택", command=self._pick_original).grid(row=1, column=1)

        # 문제집 파일
        ttk.Label(frm, text="문제집 (여러 문제):").grid(row=2, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(frm, textvariable=self.problems_path, width=60).grid(row=3, column=0, padx=(0, 5), sticky="we")
        ttk.Button(frm, text="파일 선택", command=self._pick_problems).grid(row=3, column=1)

        # 모델 라디오
        model_frame = ttk.Frame(frm)
        model_frame.grid(row=4, column=0, columnspan=2, sticky="w", pady=10)
        ttk.Label(model_frame, text="모델:").pack(side=tk.LEFT)
        ttk.Radiobutton(model_frame, text="Sonnet (기본)", variable=self.model_var,
                        value="claude-sonnet-4-6").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(model_frame, text="Opus (정밀)", variable=self.model_var,
                        value="claude-opus-4-7").pack(side=tk.LEFT)

        # 검색 버튼
        self.search_btn = ttk.Button(frm, text="유사 문제 찾기", command=self._on_search)
        self.search_btn.grid(row=5, column=0, columnspan=2, pady=5, sticky="we")

        # 진행 상태
        self.status_var = tk.StringVar(value="대기 중")
        ttk.Label(frm, textvariable=self.status_var).grid(row=6, column=0, columnspan=2, sticky="w", pady=(5, 0))
        self.progress = ttk.Progressbar(frm, mode="indeterminate")
        self.progress.grid(row=7, column=0, columnspan=2, sticky="we", pady=(0, 10))

        # 결과 영역
        ttk.Label(frm, text="결과:").grid(row=8, column=0, sticky="w")
        self.result_text = tk.Text(frm, height=18, wrap=tk.WORD)
        self.result_text.grid(row=9, column=0, columnspan=2, sticky="nsew")
        scroll = ttk.Scrollbar(frm, command=self.result_text.yview)
        scroll.grid(row=9, column=2, sticky="ns")
        self.result_text.config(yscrollcommand=scroll.set, state=tk.DISABLED)

        # 하단 버튼
        btn_frame = ttk.Frame(frm)
        btn_frame.grid(row=10, column=0, columnspan=2, sticky="we", pady=5)
        self.copy_btn = ttk.Button(btn_frame, text="결과 복사", command=self._copy_result, state=tk.DISABLED)
        self.copy_btn.pack(side=tk.LEFT, padx=(0, 5))
        self.opus_btn = ttk.Button(btn_frame, text="Opus로 재확인", command=self._retry_opus, state=tk.DISABLED)
        self.opus_btn.pack(side=tk.LEFT)

        # grid 확장 설정
        frm.columnconfigure(0, weight=1)
        frm.rowconfigure(9, weight=1)

    def _pick_original(self):
        path = filedialog.askopenfilename(
            title="원본 문제 HWPX 선택",
            filetypes=[("HWPX 파일", "*.hwpx"), ("HWP 파일", "*.hwp"), ("모든 파일", "*.*")],
        )
        if path:
            self.original_path.set(path)

    def _pick_problems(self):
        path = filedialog.askopenfilename(
            title="문제집 HWPX 선택",
            filetypes=[("HWPX 파일", "*.hwpx"), ("HWP 파일", "*.hwp"), ("모든 파일", "*.*")],
        )
        if path:
            self.problems_path.set(path)

    def _on_search(self):
        messagebox.showinfo("미구현", "검색 기능은 다음 태스크에서 구현됩니다.")

    def _copy_result(self):
        pass

    def _retry_opus(self):
        pass


def main():
    root = tk.Tk()
    SimilarityFinderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: GUI 수동 실행 확인**

Run: `cd "c:/Users/tnaak/OneDrive/바탕 화면/MathSolution" && python -m tools.similarity_finder.main`
Expected: Tkinter 창이 열리고, 파일 선택 버튼 2개가 동작. "유사 문제 찾기" 버튼 누르면 "미구현" 다이얼로그. 창 닫으면 정상 종료.

- [ ] **Step 3: 커밋**

```bash
git add tools/similarity_finder/main.py
git commit -m "feat(similarity-finder): Tkinter GUI 기본 레이아웃"
```

---

## Task 7: main.py — 검색 로직 (파싱 + 스레드 + 진행표시)

**Files:**
- Modify: `tools/similarity_finder/main.py`

- [ ] **Step 1: 입력 검증 + 백그라운드 검색 구현**

`tools/similarity_finder/main.py`의 `_on_search`를 아래로 교체:

```python
    def _on_search(self):
        if self.is_searching:
            return

        original_path = self.original_path.get().strip()
        problems_path = self.problems_path.get().strip()

        if not original_path or not problems_path:
            messagebox.showwarning("입력 부족", "두 파일을 모두 선택해주세요.")
            return

        if original_path.lower().endswith(".hwp") or problems_path.lower().endswith(".hwp"):
            messagebox.showerror(
                "HWP 미지원",
                "구버전 HWP 파일은 지원하지 않습니다.\n한글에서 HWPX로 저장한 뒤 다시 시도하세요.",
            )
            return

        self._set_searching(True)
        self._clear_result()
        threading.Thread(
            target=self._run_search,
            args=(original_path, problems_path, self.model_var.get()),
            daemon=True,
        ).start()

    def _set_searching(self, flag: bool):
        self.is_searching = flag
        if flag:
            self.search_btn.config(state=tk.DISABLED)
            self.copy_btn.config(state=tk.DISABLED)
            self.opus_btn.config(state=tk.DISABLED)
            self.progress.start(10)
        else:
            self.search_btn.config(state=tk.NORMAL)
            self.progress.stop()

    def _clear_result(self):
        self.result_text.config(state=tk.NORMAL)
        self.result_text.delete("1.0", tk.END)
        self.result_text.config(state=tk.DISABLED)
        self.last_result = None

    def _update_status(self, msg: str):
        self.root.after(0, lambda: self.status_var.set(msg))

    def _run_search(self, original_path: str, problems_path: str, model: str):
        try:
            self._update_status("원본 파싱 중…")
            original_bytes = Path(original_path).read_bytes()
            original_text = read_hwpx(original_bytes)

            # 원본에 문제가 2개 이상이면 첫 번째만 사용 (경고)
            original_problems = split_problems(original_text)
            if len(original_problems) > 1:
                use_first = messagebox.askokcancel(
                    "다중 문제 감지",
                    f"원본 파일에 문제가 {len(original_problems)}개 감지되었습니다.\n첫 번째 문제만 사용하시겠습니까?",
                )
                if not use_first:
                    self._update_status("취소됨")
                    self._set_searching(False)
                    return
                original_text = original_problems[0]["text"]

            self._update_status("문제집 파싱 중…")
            problems_bytes = Path(problems_path).read_bytes()
            problems_text = read_hwpx(problems_bytes)
            problems = split_problems(problems_text)

            if not problems or (len(problems) == 1 and problems[0]["number"] == 1 and "-1번-" not in problems_text):
                messagebox.showerror("문제 감지 실패", "문제집에서 '-N번-' 구분자를 찾지 못했습니다.")
                self._update_status("실패")
                self._set_searching(False)
                return

            self._update_status(f"총 {len(problems)}문제 발견. Claude 호출 시작…")
            result = comparator.compare(
                original=original_text,
                problems=problems,
                model=model,
                progress_callback=self._update_status,
            )
            self._log_request(original_text, problems, model, result)
            self.last_result = result
            self.root.after(0, lambda: self._render_result(result, problems_count=len(problems)))

        except Exception as exc:
            err = f"{type(exc).__name__}: {exc}"
            trace = traceback.format_exc()
            self.root.after(0, lambda: messagebox.showerror("검색 실패", f"{err}\n\n자세한 내용은 로그를 확인하세요."))
            self._log_error(trace)
            self._update_status(f"오류: {err}")
        finally:
            self._set_searching(False)

    def _log_request(self, original: str, problems: list[dict], model: str, result: dict):
        log_dir = Path(__file__).parent / "logs"
        log_dir.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        (log_dir / f"{stamp}.log").write_text(
            f"MODEL={model}\nPROBLEMS={len(problems)}\n\n=== ORIGINAL ===\n{original}\n\n=== RESULT ===\n{result}\n",
            encoding="utf-8",
        )

    def _log_error(self, trace: str):
        log_dir = Path(__file__).parent / "logs"
        log_dir.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        (log_dir / f"error_{stamp}.log").write_text(trace, encoding="utf-8")

    def _render_result(self, result: dict, problems_count: int):
        # 다음 태스크에서 구현
        self.result_text.config(state=tk.NORMAL)
        self.result_text.insert(tk.END, str(result))
        self.result_text.config(state=tk.DISABLED)
        self._update_status(f"완료 (총 {problems_count}문제 비교)")
```

- [ ] **Step 2: 수동 실행 확인 (API 키 필요)**

Run: `python -m tools.similarity_finder.main`
- 두 파일 선택 없이 검색 → 경고
- `.hwp` 경로 입력 → 에러 다이얼로그
- 프로젝트 루트의 `유사문항_1775116253945.hwpx`를 원본으로, 다른 HWPX를 문제집으로 선택 → 검색 시작, 진행 상태 표시, 결과 창에 raw dict 출력
Expected: 정상 작동, 로그 파일이 `tools/similarity_finder/logs/`에 생성됨

- [ ] **Step 3: 커밋**

```bash
git add tools/similarity_finder/main.py
git commit -m "feat(similarity-finder): 검색 로직 + 파싱 + 백그라운드 스레드"
```

---

## Task 8: main.py — 결과 렌더링 + 복사/재확인 버튼

**Files:**
- Modify: `tools/similarity_finder/main.py`

- [ ] **Step 1: `_render_result`, `_copy_result`, `_retry_opus` 구현**

`tools/similarity_finder/main.py`의 3개 메서드를 아래로 교체:

```python
    def _render_result(self, result: dict, problems_count: int):
        self.result_text.config(state=tk.NORMAL)
        self.result_text.delete("1.0", tk.END)

        twins = result.get("쌍둥이", [])
        similar = result.get("유형유사", [])

        if not twins and not similar:
            self.result_text.insert(tk.END, "유사한 문제를 찾지 못했습니다.\n")
        else:
            self.result_text.insert(tk.END, f"🎯 쌍둥이급 (숫자만 변형) — {len(twins)}개\n", "heading")
            if twins:
                for item in twins:
                    self.result_text.insert(tk.END, f"  • {item.get('번호')}번 — {item.get('이유', '')}\n")
            else:
                self.result_text.insert(tk.END, "  (없음)\n")

            self.result_text.insert(tk.END, f"\n📚 유형 유사 — {len(similar)}개\n", "heading")
            if similar:
                for item in similar:
                    self.result_text.insert(tk.END, f"  • {item.get('번호')}번 — {item.get('이유', '')}\n")
            else:
                self.result_text.insert(tk.END, "  (없음)\n")

        self.result_text.tag_config("heading", font=("Malgun Gothic", 11, "bold"))
        self.result_text.config(state=tk.DISABLED)

        self.copy_btn.config(state=tk.NORMAL)
        self.opus_btn.config(state=tk.NORMAL if self.model_var.get() == "claude-sonnet-4-6" else tk.DISABLED)
        self._update_status(f"완료 (총 {problems_count}문제 비교)")

    def _copy_result(self):
        text = self.result_text.get("1.0", tk.END).strip()
        if not text:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self._update_status("결과가 클립보드에 복사됨")

    def _retry_opus(self):
        if self.is_searching:
            return
        self.model_var.set("claude-opus-4-7")
        self._on_search()
```

- [ ] **Step 2: 수동 실행 확인**

Run: `python -m tools.similarity_finder.main`
- 동일 검색을 돌려 결과가 예쁘게 렌더링되는지 확인 (쌍둥이/유형유사 섹션 분리, 굵은 제목)
- 결과 복사 버튼 클릭 → 메모장에 붙여넣기 잘 되는지
- "Opus로 재확인" 버튼이 Sonnet 사용 시엔 활성, Opus 사용 시엔 비활성
- Opus 재확인 클릭 → 모델 바꾸고 재검색
Expected: 모두 정상 작동

- [ ] **Step 3: 커밋**

```bash
git add tools/similarity_finder/main.py
git commit -m "feat(similarity-finder): 결과 렌더링 + 복사/Opus 재확인 버튼"
```

---

## Task 9: API 키 검증 + 종료 확인 다이얼로그

**Files:**
- Modify: `tools/similarity_finder/main.py`

- [ ] **Step 1: 시작 시 API 키 검증 + 종료 프로토콜 추가**

`tools/similarity_finder/main.py`의 `__init__`와 `main`을 아래처럼 수정:

```python
class SimilarityFinderApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("유사문제 찾기")
        self.root.geometry("700x600")

        self.original_path = tk.StringVar()
        self.problems_path = tk.StringVar()
        self.model_var = tk.StringVar(value="claude-sonnet-4-6")
        self.last_result: dict | None = None
        self.is_searching = False

        self._build_ui()
        self._verify_api_key()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _verify_api_key(self):
        try:
            comparator._load_api_key()
        except RuntimeError as e:
            messagebox.showerror("API 키 누락", str(e))
            self.root.destroy()

    def _on_close(self):
        if self.is_searching:
            if not messagebox.askokcancel("검색 중", "검색이 진행 중입니다. 종료하시겠습니까?"):
                return
        self.root.destroy()


def main():
    root = tk.Tk()
    app = SimilarityFinderApp(root)
    if root.winfo_exists():
        root.mainloop()
```

- [ ] **Step 2: 수동 테스트**

`.env`에서 `ANTHROPIC_API_KEY`를 임시로 주석 처리하고 실행 → 에러 다이얼로그 후 앱 종료 확인. 복원 후 정상 실행 확인. 검색 중 창 닫기 → 확인 다이얼로그.

- [ ] **Step 3: 커밋**

```bash
git add tools/similarity_finder/main.py
git commit -m "feat(similarity-finder): API 키 검증 + 종료 프로토콜"
```

---

## Task 10: run.bat + README + End-to-End 수동 테스트

**Files:**
- Create: `tools/similarity_finder/run.bat`

- [ ] **Step 1: 실행 배치 파일 생성**

`tools/similarity_finder/run.bat`:
```bat
@echo off
cd /d "%~dp0\..\.."
python -m tools.similarity_finder.main
pause
```

- [ ] **Step 2: 전체 pytest 재실행**

Run: `python -m pytest tools/similarity_finder/tests/ -v`
Expected: 11 passed

- [ ] **Step 3: 실사용 E2E 테스트**

프로젝트 루트에 실제 HWPX 샘플이 있으므로 사용:
- 원본: `유사문항_1775116253945.hwpx`
- 문제집: `유사문항_1775116804527.hwpx`

(실제로는 선생님이 준비한 1문제 HWPX + 몇백 문제 HWPX로 테스트)

`run.bat` 더블클릭 → GUI 열림 → 파일 2개 선택 → 검색 → 결과 확인 → 복사 → Opus 재확인.

확인 사항:
- 검색이 1~2분 내 완료되는가
- 쌍둥이/유형유사 번호가 합리적인가
- 로그 파일이 `tools/similarity_finder/logs/`에 생성되었는가
- 결과 복사가 클립보드에 반영되는가

- [ ] **Step 4: 진행일지 업데이트 + 커밋**

`진행일지.md`의 2026-04-21 섹션에 항목 추가:
```markdown
- **유사문제 찾기 GUI 앱 완성** (`tools/similarity_finder/`)
  - Tkinter GUI: HWPX 2개 → 쌍둥이/유형유사 번호 자동 탐지
  - Claude Sonnet 4.6 기본, Opus 4.7 재확인 버튼
  - prompt caching, 500+ 문제 시 자동 배치 분할
  - 로그 자동 저장, 독립 실행(`run.bat` 더블클릭)
```

```bash
git add tools/similarity_finder/run.bat 진행일지.md
git commit -m "feat(similarity-finder): run.bat 실행 스크립트 + 진행일지 업데이트"
```

---

## Self-Review Checklist

- [x] **Spec 요구사항 커버:**
  - 쌍둥이/유형유사 2단계 분류 → Task 3, 8
  - 로컬 GUI (Tkinter) → Task 6~9
  - Sonnet 기본 + Opus 재확인 → Task 5, 8
  - prompt caching → Task 5 (`cache_control: ephemeral`)
  - 500개 초과 자동 배치 → Task 4, 5
  - HWP 거부 안내 → Task 7
  - API 키 검증 → Task 9
  - 로그 저장 → Task 7
  - 스레드 기반 GUI 멈춤 방지 → Task 7
  - 결과 복사 → Task 8
  - 종료 확인 → Task 9
- [x] **Placeholder 없음:** 모든 코드 전체 제시, TBD 없음
- [x] **타입 일관성:** `build_user_message`, `parse_response`, `chunk_problems`, `merge_results`, `compare` 시그니처 전 태스크 동일
- [x] **파일 경로 명시:** 모든 Create/Modify 파일 절대 경로 기준 상대경로로 명시
