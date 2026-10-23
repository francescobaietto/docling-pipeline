"""Generates tests/fixtures/sample_table.pdf: a tiny synthetic PDF with a ruled table.

Written by hand (no third-party library, no copyrighted content) so the integration
test has a deterministic input. Run: python -m tests.make_fixture
"""
from pathlib import Path

ROWS = [
    ["Item", "2025", "2026"],
    ["Revenue", "90,234", "109,896"],
    ["Operating income", "30,606", "39,696"],
    ["Net income", "34,540", "62,578"],
]


def build_pdf() -> bytes:
    col_x = [72, 250, 350, 450]
    top, row_h = 700, 24
    ops = []
    for i in range(len(ROWS) + 1):
        y = top - i * row_h
        ops.append(f"{col_x[0]} {y} m {col_x[-1]} {y} l S")
    for x in col_x:
        ops.append(f"{x} {top} m {x} {top - len(ROWS) * row_h} l S")
    ops.append("BT /F1 14 Tf 72 740 Td (Sample financial table) Tj ET")
    for r, row in enumerate(ROWS):
        y = top - r * row_h - 16
        for c, text in enumerate(row):
            ops.append(f"BT /F1 11 Tf {col_x[c] + 6} {y} Td ({text}) Tj ET")
    content = "\n".join(ops).encode("latin-1")

    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n".encode() + b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(out)


if __name__ == "__main__":
    target = Path(__file__).parent / "fixtures" / "sample_table.pdf"
    target.write_bytes(build_pdf())
    print(f"written {target}")
