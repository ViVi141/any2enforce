"""Diagnostics: language-agnostic error / warning / info records with source spans."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .ir import Span

ERROR = "error"
WARNING = "warning"
INFO = "info"


@dataclass
class Diagnostic:
    level: str  # error | warning | info
    code: str  # stable machine-readable id, e.g. "unsupported-lambda"
    message: str
    span: Optional[Span] = None
    out_span: Optional[Span] = None  # location in generated EnforceScript, when known
    note: Optional[str] = None

    def render_text(self) -> str:
        loc = ""
        if self.span:
            loc = f"{self.span.file}:{self.span.line}:{self.span.col} "
        out = ""
        if self.out_span:
            out = f"  -> output {self.out_span.file}:{self.out_span.line}"
        note = f"\n    note: {self.note}" if self.note else ""
        return f"{loc}[{self.level}] {self.code}: {self.message}{note}{out}"

    def to_json(self) -> dict:
        return {
            "level": self.level,
            "code": self.code,
            "message": self.message,
            "span": _span_json(self.span),
            "out_span": _span_json(self.out_span),
            "note": self.note,
        }


def _span_json(span: Optional[Span]):
    if span is None:
        return None
    return {"file": span.file, "line": span.line, "col": span.col}


class DiagnosticSink:
    """Collector shared by all pipeline stages."""

    def __init__(self) -> None:
        self.items: List[Diagnostic] = []

    def add(self, level: str, code: str, message: str,
            span: Optional[Span] = None, note: Optional[str] = None) -> None:
        self.items.append(Diagnostic(level, code, message, span, note=note))

    def error(self, code: str, message: str, span=None, note=None) -> None:
        self.add(ERROR, code, message, span, note)

    def warning(self, code: str, message: str, span=None, note=None) -> None:
        self.add(WARNING, code, message, span, note)

    def info(self, code: str, message: str, span=None, note=None) -> None:
        self.add(INFO, code, message, span, note)

    @property
    def errors(self) -> List[Diagnostic]:
        return [d for d in self.items if d.level == ERROR]

    def render_text(self) -> str:
        return "\n".join(d.render_text() for d in self.items)

    def to_json(self) -> List[dict]:
        return [d.to_json() for d in self.items]
