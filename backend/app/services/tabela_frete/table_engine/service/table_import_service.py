from __future__ import annotations

import re
import unicodedata
import csv
import io
from pathlib import Path

from app.services.tabela_frete.table_engine.adapters.normalized_table_adapter import to_canonical_contract
from app.services.tabela_frete.table_engine.detection.format_detector import detect_format
from app.services.tabela_frete.table_engine.detection.structure_detector import detect_structure
from app.services.tabela_frete.table_engine.extraction.document import extract_document
from app.services.tabela_frete.table_engine.mapping.destination_mapper import map_destinations
from app.services.tabela_frete.table_engine.mapping.semantic_mapper import SemanticMapper
from app.services.tabela_frete.table_engine.mapping.surcharge_mapper import map_surcharges
from app.services.tabela_frete.table_engine.mapping.weight_band_mapper import map_weight_bands
from app.services.tabela_frete.table_engine.models import FreightTable
from app.services.tabela_frete.table_engine.rules.rule_detector import detect_rules
from app.services.tabela_frete.table_engine.validation.table_validator import validate_table


class TableImportService:
    """Pipeline universal: extração → detecção → normalização → classificação → mapeamento → validação."""

    def import_document(self, path: str | Path, *, carrier: str | None = None, origin: dict[str, str] | None = None) -> dict[str, object]:
        file_path = Path(path)
        raw_text = extract_document(file_path)
        format_name = detect_format(file_path, file_type=file_path.suffix.lstrip("."))
        structure = detect_structure(raw_text)
        rows = self._extract_rows(raw_text)
        mapped = SemanticMapper().map(rows)
        detected_rules = detect_rules(raw_text)
        table = FreightTable(
            carrier=carrier,
            origin=origin or {"city": "Guarulhos", "state": "SP"},
            validity={"source": file_path.name},
            weight_bands=map_weight_bands(mapped),
            destinations=map_destinations(mapped),
            surcharges=map_surcharges(mapped),
            delivery_rules=[{"source": file_path.name, "kind": "delivery"}],
            collection_rules=[{"source": file_path.name, "kind": "collection"}],
            general_rules=[{"source": file_path.name, "kind": "generic", "rules": detected_rules}],
            metadata={"source_document": file_path.name, "detected_format": format_name},
        )
        validation = validate_table(table)
        contract = to_canonical_contract(table)
        contract["format_detected"] = format_name
        contract["structure"] = structure
        contract["validation"] = validation
        cubage = detected_rules.get("cubage", {})
        if cubage.get("status") == "resolved":
            contract["fator_cubagem"] = cubage["factor_kg_m3"]
        contract["pipeline"] = [
            {"stage": "format_detection", "status": "completed", "format": format_name},
            {"stage": "extraction", "status": "completed"},
            {"stage": "normalization", "status": "completed", "rows": len(rows)},
            {"stage": "rule_mapping", "status": "completed"},
            {"stage": "canonical_model", "status": "completed", "schema": "canonical_tariff_v2"},
            {"stage": "validation", "status": validation["status"]},
        ]
        return contract

    def _extract_rows(self, raw_text: str) -> list[dict[str, object]]:
        lines = [line for line in raw_text.splitlines() if line.strip()]
        if not lines:
            return []

        # Spreadsheet exports commonly repeat the tariff header between
        # regions and use blank UF cells for continuation rows.
        for index, line in enumerate(lines):
            parts = [part.strip() for part in line.split("|")]
            normalized = _header_key(line)
            if "UF" in normalized and "DESTINO" in normalized and _weight_header_count(parts) >= 1:
                rows = _pipe_rows(lines[index:], parts)
                if rows:
                    return rows

        # PDF text extraction does not preserve table delimiters. Its stable
        # semantic anchors are the destination UF and the five tariff values.
        pdf_rows = _pdf_tariff_rows(lines)
        if pdf_rows:
            return pdf_rows

        delimiter = "|" if any("|" in line for line in lines) else ","
        reader = csv.reader(io.StringIO(raw_text), delimiter=delimiter)
        table = [row for row in reader if row and any(cell.strip() for cell in row)]
        if len(table) >= 2:
            header = [cell.strip() for cell in table[0]]
            return [
                {
                    header_name: values[position].strip()
                    for position, header_name in enumerate(header)
                    if position < len(values) and header_name
                }
                for values in table[1:]
            ]
        return []


def _header_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char)).upper()


def _weight_header_count(parts: list[str]) -> int:
    return sum(bool(re.search(r"(?:ATE|AT[EÉ]|KG|PESO)", part, re.IGNORECASE)) for part in parts)


def _pipe_rows(lines: list[str], header: list[str]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    state: str | None = None
    for line in lines[1:]:
        # Each worksheet is emitted with a marker by the parser. A table must
        # never consume rows from the next worksheet using the previous header.
        if line.startswith("### "):
            break
        parts = [part.strip() for part in line.split("|")]
        if _header_key(line).count("DESTINO") and _header_key(line).count("UF"):
            continue
        if len(parts) < 2:
            continue
        if re.fullmatch(r"[A-Za-z]{2}", parts[0]):
            state = parts[0].upper()
            destination = parts[1]
            values = parts
        else:
            destination = parts[0]
            values = [state or "", *parts]
        if not state or not destination or _header_key(destination) in {"DESTINO", "UF"}:
            continue
        row = {
            header[position]: values[position].strip()
            for position in range(min(len(header), len(values)))
            if header[position]
        }
        row["UF"] = state
        row["DESTINO"] = destination
        rows.append(row)
    return rows


def _pdf_tariff_rows(lines: list[str]) -> list[dict[str, object]]:
    states = "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split()
    state_pattern = re.compile("|".join(states))
    number_pattern = re.compile(r"\d{2,3}[,.]\d{2}")
    rows: list[dict[str, object]] = []
    current_state: str | None = None
    for line in lines:
        compact = " ".join(line.split())
        match = number_pattern.search(compact)
        if not match:
            continue
        prefix = compact[: match.start()].strip()
        codes = [item.group(0) for item in state_pattern.finditer(prefix)]
        if codes:
            current_state = codes[-1]
        if not current_state:
            continue
        city = prefix
        if codes:
            marker = prefix.rfind(codes[-1])
            city = prefix[marker + 2 :].strip()
        city = re.sub(r"^(?:ORIGEM|DESTINO)\s+", "", city, flags=re.IGNORECASE).strip()
        values = number_pattern.findall(compact[match.start():])
        if not city or len(values) < 3:
            continue
        values.extend([values[-1]] * (5 - len(values)))
        rows.append(
            {
                "UF": current_state,
                "DESTINO": city,
                "ATÉ 20 KG": values[0],
                "ATÉ 30 KG": values[1],
                "ATÉ 50 KG": values[2],
                "ATÉ 70 KG": values[3],
                "ATÉ 100 KG": values[4],
            }
        )
    return rows


def import_table_document(path: str | Path, *, carrier: str | None = None, origin: dict[str, str] | None = None) -> dict[str, object]:
    return TableImportService().import_document(path, carrier=carrier, origin=origin)
