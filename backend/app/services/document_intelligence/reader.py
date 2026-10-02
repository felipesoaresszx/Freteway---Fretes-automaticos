"""Document readers preserving pages, word coordinates and OCR provenance."""
import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DocumentPage:
    number: int
    text: str
    method: str


@dataclass(frozen=True)
class DocumentWord:
    page: int
    text: str
    x: float
    y: float
    width: float
    height: float
    confidence: float


def _pymupdf_words(path: Path) -> list[DocumentWord]:
    """Extract text and coordinates from PDFs that pypdf cannot interpret."""
    try:
        import pymupdf
    except ImportError:
        # Older PyMuPDF releases expose the module as ``fitz``.
        try:
            import fitz as pymupdf
        except ImportError as exc:
            raise RuntimeError("PyMuPDF is required to read this PDF") from exc

    words: list[DocumentWord] = []
    with pymupdf.open(str(path)) as pdf:
        for page_number, page in enumerate(pdf, 1):
            page_words = [DocumentWord(page_number, str(item[4]), float(item[0]), float(item[1]),
                                       float(item[2] - item[0]), float(item[3] - item[1]), 1.0)
                           for item in page.get_text("words") if str(item[4]).strip()]
            if page_words:
                words.extend(page_words)
                continue
            # Text-free pages may be scans. Render the page rather than
            # relying on pypdf to decode embedded image XObjects.
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
            from PIL import Image
            import io
            image = Image.open(io.BytesIO(pixmap.tobytes("png"))).convert("RGB")
            words.extend(_ocr_image(image, page_number))
    return words


def _ocr_image(image, page: int) -> list[DocumentWord]:
    import pytesseract
    try:
        data = pytesseract.image_to_data(image, lang="por", config="--psm 6", output_type=pytesseract.Output.DICT)
        return [DocumentWord(page, str(text).strip(), float(data["left"][i]), float(data["top"][i]),
                float(data["width"][i]), float(data["height"][i]), max(0.0, float(data["conf"][i])) / 100)
                for i, text in enumerate(data["text"]) if str(text).strip()]
    except pytesseract.TesseractNotFoundError:
        if shutil.which("powershell") is None:
            raise RuntimeError("Tesseract OCR is required to read scanned PDFs")
        script = Path(__file__).with_name("windows_ocr.ps1")
        with tempfile.TemporaryDirectory() as temp:
            image_path, output_path = Path(temp) / "page.png", Path(temp) / "ocr.json"
            image.save(image_path)
            subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
                            "-ImagePath", str(image_path), "-OutputPath", str(output_path)], check=True,
                           capture_output=True, text=True, timeout=60)
            lines = json.loads(output_path.read_text(encoding="utf-8"))
        return [DocumentWord(page, word["text"], float(word["x"]), float(word["y"]),
                float(word["width"]), float(word["height"]), .9)
                for line in lines for word in line.get("words", []) if word.get("text")]


def read_pdf_words(path: Path) -> list[DocumentWord]:
    from pypdf import PdfReader
    all_words = []
    markers = ("ORIGEM", "FORMATO", "GRIS", "ADV", "PED", "GENERAL")
    try:
        pages = PdfReader(str(path)).pages
    except Exception:
        return _pymupdf_words(path)
    for page_number, page in enumerate(pages, 1):
        page_best, best_score = [], -1
        try:
            # Prefer embedded text and its coordinates when available. This
            # also avoids OCR on decorative images embedded in digital PDFs.
            page_text_words = _pymupdf_page_words(path, page_number)
            if page_text_words:
                all_words.extend(page_text_words)
                continue
        except Exception:
            pass
        for source in page.images:
            original = source.image.convert("RGB")
            for angle in (0, 90, 270):
                image = original.rotate(angle, expand=True)
                if max(image.size) > 2600:
                    image.thumbnail((2600, 2600))
                words = _ocr_image(image, page_number)
                normalized = " ".join(word.text.upper() for word in words)
                score = sum(marker in normalized for marker in markers)
                if score > best_score:
                    best_score, page_best = score, words
                if score >= 4:
                    break
            if best_score >= 4:
                break
        all_words.extend(page_best)
    return all_words


def _pymupdf_page_words(path: Path, page_number: int) -> list[DocumentWord]:
    try:
        import pymupdf
    except ImportError:
        import fitz as pymupdf
    with pymupdf.open(str(path)) as pdf:
        page = pdf[page_number - 1]
        return [DocumentWord(page_number, str(item[4]), float(item[0]), float(item[1]),
                             float(item[2] - item[0]), float(item[3] - item[1]), 1.0)
                for item in page.get_text("words") if str(item[4]).strip()]


def read_pdf(path: Path) -> list[DocumentPage]:
    from pypdf import PdfReader
    try:
        reader = PdfReader(str(path))
        scanned_words = None
        pages: list[DocumentPage] = []
        for number, page in enumerate(reader.pages, start=1):
            text = page.extract_text(extraction_mode="layout") or ""
            method = "pdf_layout"
            if not text.strip() and page.images:
                scanned_words = scanned_words if scanned_words is not None else read_pdf_words(path)
                words = [word for word in scanned_words if word.page == number]
                rows: list[list[DocumentWord]] = []
                for word in sorted(words, key=lambda item: (item.y, item.x)):
                    row = next((item for item in rows if abs(item[0].y - word.y) <= max(8, word.height * .65)), None)
                    if row is None:
                        row = []
                        rows.append(row)
                    row.append(word)
                text = "\n".join(" ".join(w.text for w in sorted(row, key=lambda item: item.x)) for row in rows)
                method = "ocr"
            pages.append(DocumentPage(number, text, method))
        return pages
    except Exception:
        words = _pymupdf_words(path)
        if not words:
            raise ValueError("PDF não contém texto legível")
        pages = []
        for number in sorted({word.page for word in words}):
            page_words = sorted((word for word in words if word.page == number), key=lambda item: (item.y, item.x))
            rows: list[list[DocumentWord]] = []
            for word in page_words:
                row = next((item for item in rows if abs(item[0].y - word.y) <= max(2, word.height * .65)), None)
                if row is None:
                    row = []
                    rows.append(row)
                row.append(word)
            text = "\n".join(" ".join(w.text for w in sorted(row, key=lambda item: item.x)) for row in rows)
            pages.append(DocumentPage(number, text, "pymupdf"))
        return pages
    return pages
