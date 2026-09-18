from pathlib import Path


def extract_image(path: str | Path) -> str:
    import pytesseract
    from PIL import Image

    with Image.open(path) as image:
        return pytesseract.image_to_string(image, lang="por")
