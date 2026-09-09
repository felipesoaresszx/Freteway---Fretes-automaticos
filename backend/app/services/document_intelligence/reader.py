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
    for page_number, page in enumerate(PdfReader(str(path)).pages, 1):
        page_best, best_score = [], -1
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


def read_pdf(path: Path) -> list[DocumentPage]:
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    scanned_words = None
    pages = []
    for number, page in enumerate(reader.pages, start=1):
        text = page.extract_text(extraction_mode="layout") or ""
        method = "pdf_layout"
        if not text.strip() and page.images:
            scanned_words = scanned_words if scanned_words is not None else read_pdf_words(path)
            words = [word for word in scanned_words if word.page == number]
            rows = []
            for word in sorted(words, key=lambda item: (item.y, item.x)):
                row = next((item for item in rows if abs(item[0] - word.y) <= max(8, word.height * .65)), None)
                if row is None:
                    row = [word.y, []]
                    rows.append(row)
                row[1].append(word)
            text = "\n".join(" ".join(w.text for w in sorted(row[1], key=lambda item: item.x)) for row in rows)
            method = "ocr"
        pages.append(DocumentPage(number, text, method))
    return pages
