"""Structured logging for OpenCode Status Bar using loguru."""

from __future__ import annotations
import os
import secrets
import sys
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Generator
from loguru import logger

_req_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_sess_id: ContextVar[str | None] = ContextVar("session_id", default=None)
LOG_DIR = Path.home() / "Library" / "Logs" / "OpenCodeStatusBar"
FMT = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> | <cyan>{file}:{line}</cyan> | {message}{extra[context]}"


def _patch(r: dict) -> None:
    req, sess = _req_id.get(), _sess_id.get()
    p = ([f"req={req}"] if req else []) + ([f"session={sess}"] if sess else [])
    r["extra"]["context"] = f" [{', '.join(p)}]" if p else ""
    r["extra"]["request_id"], r["extra"]["session_id"] = req, sess


def setup_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    dbg = os.getenv("OPENCODE_DEBUG", "").lower() in ("1", "true")
    lvl = os.getenv("OPENCODE_LOG_LEVEL", "DEBUG" if dbg else "INFO").upper()
    logger.remove()
    logger.configure(patcher=_patch)
    if os.getenv("OPENCODE_LOG_CONSOLE", "1" if dbg else "0") == "1":
        logger.add(sys.stderr, format=FMT, level=lvl, colorize=True, diagnose=False)
    logger.add(
        LOG_DIR / "opencode-status-bar.log",
        format=FMT,
        level=lvl,
        rotation="10 MB",
        retention=5,
        compression="gz",
        diagnose=False,
    )
    logger.add(
        LOG_DIR / "opencode-status-bar.json",
        level=lvl,
        rotation="20 MB",
        retention=3,
        compression="gz",
        serialize=True,
        diagnose=False,
    )


setup_logging()


@contextmanager
def log_context(
    request_id: str | None = None,
    session_id: str | None = None,
    auto_request_id: bool = False,
    auto_session_id: bool = False,
) -> Generator[dict[str, str | None], None, None]:
    req, sess = (
        request_id or (secrets.token_hex(4) if auto_request_id else None),
        session_id or (secrets.token_hex(6) if auto_session_id else None),
    )
    rt, st = _req_id.set(req) if req else None, _sess_id.set(sess) if sess else None
    try:
        yield {"request_id": req, "session_id": sess}
    finally:
        if rt:
            _req_id.reset(rt)
        if st:
            _sess_id.reset(st)


def get_request_id() -> str | None:
    return _req_id.get()


def get_session_id() -> str | None:
    return _sess_id.get()


def setup_logger(name: str = "opencode") -> Any:
    return logger


def get_logger(name: str | None = None) -> Any:
    return logger


def debug(msg: str, *a: Any, **k: Any) -> None:
    logger.opt(depth=1).debug(msg, *a, **k)


def info(msg: str, *a: Any, **k: Any) -> None:
    logger.opt(depth=1).info(msg, *a, **k)


def warn(msg: str, *a: Any, **k: Any) -> None:
    logger.opt(depth=1).warning(msg, *a, **k)


def warning(msg: str, *a: Any, **k: Any) -> None:
    logger.opt(depth=1).warning(msg, *a, **k)


def error(msg: str, *a: Any, **k: Any) -> None:
    logger.opt(depth=1).error(msg, *a, **k)


def critical(msg: str, *a: Any, **k: Any) -> None:
    logger.opt(depth=1).critical(msg, *a, **k)


def exception(msg: str, *a: Any, **k: Any) -> None:
    logger.opt(depth=1, exception=True).error(msg, *a, **k)


log = logger
__all__ = [
    "debug",
    "info",
    "warn",
    "warning",
    "error",
    "critical",
    "exception",
    "setup_logger",
    "setup_logging",
    "get_logger",
    "log_context",
    "get_request_id",
    "get_session_id",
    "logger",
    "log",
]
