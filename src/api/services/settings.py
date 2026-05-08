import os

_raw = os.getenv("MODULES", "base,op,os,alertas")
enabled_modules: frozenset[str] = frozenset(m.strip() for m in _raw.split(",") if m.strip())


def is_enabled(module: str) -> bool:
    return module in enabled_modules
