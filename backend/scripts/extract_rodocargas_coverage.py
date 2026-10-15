"""Extract locality cells and their coloured backgrounds; no OCR guessing."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pymupdf


def extract(source: Path, state: str) -> dict:
    cities = []
    with pymupdf.open(source) as document:
        for page_number, page in enumerate(document, 1):
            coloured = [drawing['rect'] for drawing in page.get_drawings()
                        if drawing.get('fill') and drawing['fill'][0] > .9
                        and .5 < drawing['fill'][1] < .9 and drawing['fill'][2] < .7]
            tables = page.find_tables().tables
            for table in tables:
                if table.col_count < 5 or table.row_count < 5:
                    continue
                for row, values in zip(table.rows, table.extract()):
                    for cell, value in zip(row.cells, values):
                        if not cell or not value or not value.strip():
                            continue
                        rect = pymupdf.Rect(cell)
                        center = pymupdf.Point((rect.x0 + rect.x1) / 2, (rect.y0 + rect.y1) / 2)
                        cities.append({'city': ' '.join(value.split()),
                                       'served': not any(center in background for background in coloured),
                                       'page': page_number, 'bbox': list(cell)})
    return {'state': state, 'source_document': source.name,
            'sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'cities': cities}


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[2]
    documents = root / 'tabelas_trans'
    result = [extract(next(documents.glob('cidades do Piau*.pdf')), 'PI'),
              extract(documents / 'cidades_maranhao PDF.pdf', 'MA')]
    output = root / 'backend/data/tariffs/rodocargas/coverage.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for state in result:
        print(state['state'], len(state['cities']), 'served', sum(city['served'] for city in state['cities']))
