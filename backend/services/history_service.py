import json
import uuid
from datetime import datetime
from pathlib import Path

HISTORY_DIR = Path(__file__).resolve().parent.parent / "history"
HISTORY_DIR.mkdir(exist_ok=True)
INDEX_FILE = HISTORY_DIR / "index.json"


def _load_index() -> list:
    if INDEX_FILE.exists():
        return json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    return []


def _save_index(index: list):
    INDEX_FILE.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def save_history(entry: dict) -> str:
    """히스토리 항목 저장. entry_id 반환."""
    entry_id = str(uuid.uuid4())[:8]
    now = datetime.now().isoformat(timespec="seconds")

    record = {
        "id": entry_id,
        "created_at": now,
        "type": entry.get("type", "generate"),       # "generate" | "solve" | "refine"
        "variant_type": entry.get("variant_type"),    # "number" | "idea"
        "difficulty": entry.get("difficulty"),         # "easier" | "similar" | "harder"
        "model": entry.get("model", "sonnet"),
        "custom_prompt": entry.get("custom_prompt", ""),
        "result": entry.get("result", ""),
        "usage": entry.get("usage", {}),
    }

    # 결과 파일 저장
    detail_file = HISTORY_DIR / f"{entry_id}.json"
    detail_file.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    # 인덱스에 요약 추가
    index = _load_index()
    summary = {
        "id": entry_id,
        "created_at": now,
        "type": record["type"],
        "variant_type": record.get("variant_type"),
        "difficulty": record.get("difficulty"),
        "model": record["model"],
        "custom_prompt": record.get("custom_prompt", ""),
        "cost_krw": record["usage"].get("cost_krw", 0),
        "preview": record["result"][:80] + "..." if len(record["result"]) > 80 else record["result"],
    }
    index.insert(0, summary)  # 최신이 맨 앞
    _save_index(index)

    return entry_id


def get_history_list() -> list:
    """히스토리 요약 목록 반환 (최신순)."""
    return _load_index()


def get_history_detail(entry_id: str) -> dict | None:
    """히스토리 상세 내용 반환."""
    detail_file = HISTORY_DIR / f"{entry_id}.json"
    if not detail_file.exists():
        return None
    return json.loads(detail_file.read_text(encoding="utf-8"))


def delete_history(entry_id: str) -> bool:
    """히스토리 항목 삭제."""
    detail_file = HISTORY_DIR / f"{entry_id}.json"
    if detail_file.exists():
        detail_file.unlink()

    index = _load_index()
    index = [item for item in index if item["id"] != entry_id]
    _save_index(index)
    return True
