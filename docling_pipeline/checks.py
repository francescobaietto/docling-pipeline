"""Deterministic helpers: number parsing and structural checks on extracted tables."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence

_CURRENCY = re.compile(r"[$€£¥\s\u00a0]")
_THOUSANDS_COMMA = re.compile(r"^\d{1,3}(,\d{3})+$")
_THOUSANDS_DOT = re.compile(r"^\d{1,3}(\.\d{3}){2,}$")
_PLAIN = re.compile(r"^\d+(\.\d+)?$")
_EMPTY_MARKERS = {"", "-", "–", "—", "n/a", "na", "nm"}


def parse_number(text: Any) -> Optional[float]:
    """Parse a financial-statement cell into a float, or None if it is not a number.

    Handles currency symbols, parentheses as negatives, percent signs, and both
    1,234.56 and 1.234,56 conventions. Dashes return None (zero vs missing is
    ambiguous and must be decided by the consumer).
    """
    s = str(text).strip().replace("\u2212", "-")
    if s.lower() in _EMPTY_MARKERS:
        return None
    s = _CURRENCY.sub("", s).rstrip("%")
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative, s = True, s[1:-1]
    if s.startswith("-"):
        negative, s = True, s[1:]
    if not s:
        return None
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        if _THOUSANDS_COMMA.match(s):
            s = s.replace(",", "")
        elif re.match(r"^\d+,\d{1,2}$", s):
            s = s.replace(",", ".")
        else:
            return None
    elif "." in s and _THOUSANDS_DOT.match(s):
        s = s.replace(".", "")
    if not _PLAIN.match(s):
        return None
    value = float(s)
    return -value if negative else value


def check_table(columns: Sequence[str], rows: Sequence[Sequence[str]]) -> Dict[str, Any]:
    """Cheap structural sanity checks. Flags tables that probably need a human look."""
    issues: List[str] = []
    if not rows:
        issues.append("no rows")
    if len(columns) < 2:
        issues.append("fewer than 2 columns")
    if rows and any(len(r) != len(columns) for r in rows):
        issues.append("ragged rows")
    cells = [c for r in rows for c in r[1:]]
    numeric = sum(1 for c in cells if parse_number(c) is not None)
    ratio = round(numeric / len(cells), 3) if cells else 0.0
    return {
        "rows": len(rows),
        "columns": len(columns),
        "numeric_ratio": ratio,
        "issues": issues,
        "ok": not issues,
    }


def summarize(pages: int, markdown: str, table_checks: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    flagged = sum(1 for c in table_checks if not c["ok"])
    return {
        "pages": pages,
        "markdown_chars": len(markdown),
        "tables": len(table_checks),
        "tables_flagged": flagged,
        "ok": pages > 0 and len(markdown.strip()) > 0,
    }
