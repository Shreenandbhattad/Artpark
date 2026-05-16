import time
import hashlib
from config import CACHE_TTL

_store: dict[str, tuple[float, dict]] = {}
_data_version: str = ""

def set_version(v: str) -> None:
    global _data_version, _store
    if v != _data_version:
        _store.clear()  # invalidate
        _data_version = v

def make_key(question: str, domain: str) -> str:
    raw = f"{domain}:{_data_version}:{question.strip().lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]

def get(key: str):
    if key not in _store:
        return None
    exp, val = _store[key]
    if time.time() > exp:
        del _store[key]
        return None  # expired
    return val

def put(key: str, val: dict) -> None:
    _store[key] = (time.time() + CACHE_TTL, val)

def size() -> int:
    return len(_store)
