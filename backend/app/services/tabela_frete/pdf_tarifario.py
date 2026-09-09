"""Semantic, coordinate-based parser for scanned tariff matrices."""
from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import Counter
from pathlib import Path

from app.services.tabela_frete.analise import AnaliseDocumentoError

FORMATO = "tariff_matrix_v1"
UF_NAMES = {"SAO PAULO": "SP", "PARANA": "PR", "SANTA CATARINA": "SC", "RIO GRANDE DO SUL": "RS",
            "MINAS GERAIS": "MG", "RIO DE JANEIRO": "RJ"}
CLASSIFICATIONS = ("GRANDE CAPITAL", "INTERIOR IV", "INTERIOR III", "INTERIOR II", "INTERIOR I", "INTERIOR")


def _key(value) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    result = "".join(c for c in text if not unicodedata.combining(c)).upper()
    return re.sub(r"\s+", " ", result).replace("CA ITAL", "CAPITAL").strip()


def _lines(words, tolerance=12):
    rows = []
    for word in sorted(words, key=lambda item: (item.y, item.x)):
        row = next((r for r in rows if abs(r[0] - word.y) <= tolerance), None)
        if row is None:
            row = [word.y, []]
            rows.append(row)
        row[1].append(word)
    return sorted(rows)


def _number(words, decimals, *, percentage=False):
    raw = "".join(w.text for w in sorted(words, key=lambda item: item.x)).upper().replace("O", "0").replace("I", "1").replace("S", "5")
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return None
    value = int(digits) / (10 ** decimals)
    return value / 100 if percentage else value


def _column_centers(words, header_y):
    header = [w for w in words if abs(w.y - header_y) < 25]
    weight_tokens = sorted((w for w in header if "KG" in _key(w.text)), key=lambda w: w.x)
    if len(weight_tokens) < 5:
        raise AnaliseDocumentoError("Cinco cabeçalhos de peso não foram identificados")
    weights = [w.x + w.width / 2 for w in weight_tokens[:5]]
    aliases = {"excess_rate": ("EXCED",), "gris": ("GRIS",), "ad_valorem": ("ADV",),
               "toll": ("PED",), "tas": ("TAS",)}
    centers = dict(zip(("20", "30", "50", "70", "100"), weights))
    for field, markers in aliases.items():
        found = next((w for w in header if any(_key(w.text).startswith(marker) for marker in markers)), None)
        if found:
            centers[field] = found.x + found.width / 2
    if set(aliases) - set(centers):
        raise AnaliseDocumentoError("Cabeçalhos de adicionais incompletos")
    return centers


def _modal_fill(rows, field):
    known = [row[field] for row in rows if row.get(field) is not None]
    if not known:
        return
    value, count = Counter(known).most_common(1)[0]
    if count / len(rows) < .5:
        return
    for row in rows:
        if row.get(field) != value:
            row[field] = value
            row.setdefault("inferred_fields", []).append(field)


def _parse_rules(text, provenance):
    normalized = _key(text)
    rules = []
    def add(rule_type, status="resolved", confidence=.98, **parameters):
        rules.append({"type": rule_type, "status": status, **parameters,
                      "source": {**provenance, "field": rule_type, "confidence": confidence}})
    match = re.search(r"FATOR CUBAGEM[^=]*=\s*(\d+)\s*KG", normalized)
    if match:
        add("cubage", factor_kg_m3=float(match.group(1)))
    add("toll", calculation="weight_fraction", fraction_kg=100)
    add("tas", calculation="fixed")
    # The matrix contains the percentages but does not declare their bases.
    add("gris", "unresolved", .75, critical=True, calculation="percentage", base=None)
    add("ad_valorem", "unresolved", .75, critical=True, calculation="percentage", base=None)
    add("icms", "unresolved", .7, critical=True, original_text="Conforme legislação em vigor")
    match = re.search(r"PALETIZACAO[^\d]*(?:R\$)?\s*(\d+[,.]\d+)", normalized)
    if match:
        add("palletization", calculation="per_unit", amount=float(match.group(1).replace(",", ".")), quantity_field="pallets")
    match = re.search(r"AGENDAMENTOS[^\d]*(\d+)%[^\n]*?MINIMO[^\d]*(\d+[,.]\d+)", normalized)
    if match:
        add("scheduling", calculation="percentage", percentage=float(match.group(1))/100,
            base="freight_weight", minimum=float(match.group(2).replace(",", ".")))
    match = re.search(r"DEVOLUCAO[^\d]*(\d+)%", normalized)
    if match:
        add("return", calculation="percentage", percentage=float(match.group(1))/100, base="original_freight")
    add("external_surcharges", "unresolved", .8, critical=True,
        original_text="TDE/TDA/TEP/TRT conforme relação de taxas externa")
    return rules


def extract_pdf_tariff(path: Path) -> dict:
    from app.services.document_intelligence.reader import read_pdf_words
    words = read_pdf_words(path)
    if not words:
        raise AnaliseDocumentoError("PDF sem texto ou imagem legível")
    text = "\n".join(
        " ".join(word.text for word in sorted(row_words, key=lambda item: item.x))
        for page_number in sorted({word.page for word in words})
        for _, row_words in _lines([word for word in words if word.page == page_number])
    )
    normalized = _key(text)
    if sum(marker in normalized for marker in ("ORIGEM", "FORMATO", "GRIS", "ADV", "PED")) < 4:
        raise AnaliseDocumentoError("Documento não contém sinais suficientes de matriz tarifária")
    first_page = [w for w in words if w.page == 1]
    lines = _lines(first_page)
    header_line = next((row for row in lines if "GRIS" in _key(" ".join(w.text for w in row[1])) and "ADV" in _key(" ".join(w.text for w in row[1]))), None)
    if header_line is None:
        raise AnaliseDocumentoError("Cabeçalho da matriz tarifária não identificado")
    header_y = header_line[0]
    centers = _column_centers(first_page, header_y)
    class_header = next((w for w in first_page if _key(w.text).startswith("CLASSIF")), None)
    if class_header is None:
        raise AnaliseDocumentoError("Coluna de classificação não identificada")
    class_x = class_header.x + class_header.width / 2
    general_y = min((w.y for w in first_page if _key(w.text).startswith("GENERAL")), default=max(w.y for w in first_page))
    classification_rows = []
    for y, row_words in lines:
        if not header_y < y < general_y:
            continue
        label_words = sorted((w for w in row_words if abs((w.x + w.width/2) - class_x) < 130), key=lambda item: item.x)
        label = _key(" ".join(w.text for w in label_words))
        classification = next((item for item in CLASSIFICATIONS if item == label or item in label), None)
        if classification:
            classification_rows.append((y, classification))
    if not classification_rows:
        raise AnaliseDocumentoError("Linhas de classificação não identificadas")
    state_lines = []
    for y, row_words in _lines([w for w in first_page if w.x < class_x - 100], tolerance=18):
        left = _key(" ".join(w.text for w in sorted(row_words, key=lambda item: item.x)))
        state = next((code for name, code in UF_NAMES.items() if name in left), None)
        if state:
            state_lines.append((y, state))
    column_order = sorted(centers.items(), key=lambda item: item[1])
    boundaries = {name: ((column_order[i-1][1] + center)/2 if i else center-70,
                         (center + column_order[i+1][1])/2 if i+1 < len(column_order) else center+70)
                  for i, (name, center) in enumerate(column_order)}
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    ordered_states = [state for _, state in sorted(state_lines)]
    group_starts = [y for y, classification in classification_rows if classification == "GRANDE CAPITAL"]
    if len(ordered_states) != len(group_starts):
        raise AnaliseDocumentoError("Blocos de UF e classificação não puderam ser reconciliados")
    rows = []
    for y, classification in classification_rows:
        group_index = max((i for i, start in enumerate(group_starts) if start <= y), default=-1)
        state = ordered_states[group_index] if group_index >= 0 else None
        if state is None:
            continue
        cells = {}
        for field, (left, right) in boundaries.items():
            cell_words = [w for w in first_page if left <= w.x + w.width/2 < right and abs(w.y-y) <= 13]
            decimals = 3 if field == "excess_rate" else 2
            cells[field] = _number(cell_words, decimals, percentage=field in ("gris", "ad_valorem"))
        rows.append({"id": f"{state}|{classification}", "state": state, "classification": classification, **cells,
                     "source": {"source_document": path.name, "sha256": sha, "page": 1,
                                "coordinates": {"y": y}, "field": "tariff_matrix", "confidence": .98}})
    for field in ("gris", "ad_valorem", "toll", "tas"):
        _modal_fill(rows, field)
    for row in rows:
        values = [row.pop(str(weight), None) for weight in (20, 30, 50, 70, 100)]
        if any(value is None for value in values + [row.get("excess_rate"), row.get("gris"), row.get("ad_valorem"), row.get("toll"), row.get("tas")]):
            raise AnaliseDocumentoError(f"Linha tarifária incompleta: {row['id']}")
        previous = 0
        row["brackets"] = []
        for limit, rate in zip((20, 30, 50, 70, 100), values):
            row["brackets"].append({"from_kg": previous, "to_kg": limit, "rate": rate,
                                    "source": {**row["source"], "field": f"weight_to_{limit}"}})
            previous = limit
    origin = re.search(r"ORIGEM\s*:?\s*([A-Z ]+)\s*/\s*([A-Z]{2})", normalized)
    if not origin:
        raise AnaliseDocumentoError("Origem não identificada")
    provenance = {"source_document": path.name, "sha256": sha, "page": 1}
    return {"formato": FORMATO, "origin": {"city": origin.group(1).title(), "state": origin.group(2)},
            "regions": rows, "rules": _parse_rules(text, provenance),
            "documents": [{**provenance, "role": "tariff"}],
            "raw_generalities": [line for line in text.splitlines() if any(marker in _key(line) for marker in ("ICMS", "CUBAGEM", "REENTREGA", "AGENDAMENTO", "DEVOLUCAO", "TDE/", "ESTADIA", "ARMAZENAGEM"))],
            "statistics": {"regions": len(rows), "brackets": len(rows)*5, "pages": len({word.page for word in words})}}
