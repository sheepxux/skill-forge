import hashlib
import json
import re
from pathlib import Path


DEFAULT_REPLAY_FILE = Path.home() / ".openclaw" / "workspace" / ".learnings" / "skill-replay-cases.jsonl"

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
TOKEN_RE = re.compile(r"\b(?:sk|tvly|ntn|xox[baprs])-?[A-Za-z0-9_\-]{12,}\b")
LONG_SECRET_RE = re.compile(r"\b[A-Za-z0-9_\-]{32,}\b")
URL_QUERY_RE = re.compile(r"(https?://[^\s?]+)\?[^\s]+")


def stable_id(*parts: str) -> str:
    digest = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
    return digest[:16]


def redact_text(text: str) -> str:
    text = EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    text = TOKEN_RE.sub("[REDACTED_TOKEN]", text)
    text = LONG_SECRET_RE.sub("[REDACTED_SECRET]", text)
    text = URL_QUERY_RE.sub(r"\1?[REDACTED_QUERY]", text)
    return text


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def append_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
