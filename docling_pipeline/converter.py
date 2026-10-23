from __future__ import annotations

from dataclasses import dataclass, field
from importlib import metadata
from typing import List, Optional


@dataclass
class ConvertedTable:
    index: int
    page: Optional[int]
    caption: str
    columns: List[str]
    rows: List[List[str]]


@dataclass
class ConvertedDocument:
    markdown: str
    tables: List[ConvertedTable] = field(default_factory=list)
    pages: int = 0
    docling_version: str = "unknown"


class DoclingConverter:
    """Thin wrapper around Docling. Docling is imported lazily so unit tests stay light."""

    def __init__(self, do_ocr: bool = False) -> None:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption

        options = PdfPipelineOptions(do_ocr=do_ocr, do_table_structure=True)
        self._converter = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
        )
        try:
            self._version = metadata.version("docling")
        except metadata.PackageNotFoundError:
            self._version = "unknown"

    def convert(self, pdf_path: str) -> ConvertedDocument:
        result = self._converter.convert(pdf_path)
        doc = result.document
        tables: List[ConvertedTable] = []
        for i, table in enumerate(doc.tables):
            df = table.export_to_dataframe(doc=doc)
            try:
                caption = table.caption_text(doc)
            except Exception:  # caption is optional metadata
                caption = ""
            tables.append(
                ConvertedTable(
                    index=i,
                    page=table.prov[0].page_no if table.prov else None,
                    caption=caption or "",
                    columns=[str(c) for c in df.columns],
                    rows=df.fillna("").astype(str).values.tolist(),
                )
            )
        return ConvertedDocument(
            markdown=doc.export_to_markdown(),
            tables=tables,
            pages=len(doc.pages),
            docling_version=self._version,
        )
