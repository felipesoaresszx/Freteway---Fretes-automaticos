"""Leitores com preservação de página e layout."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DocumentPage:
    number:int
    text:str
    method:str


def read_pdf(path:Path)->list[DocumentPage]:
    from pypdf import PdfReader
    pages=[]
    for number,page in enumerate(PdfReader(str(path)).pages,start=1):
        # Layout preserva separadores entre células; o modo simples concatena
        # valores próximos em matrizes largas.
        text=page.extract_text(extraction_mode="layout") or ""
        method="pdf_layout"
        if not text.strip() and page.images:
            import pytesseract
            text="\n".join(pytesseract.image_to_string(image.image,lang="por",config="--psm 6") for image in page.images)
            method="ocr"
        pages.append(DocumentPage(number,text,method))
    return pages
