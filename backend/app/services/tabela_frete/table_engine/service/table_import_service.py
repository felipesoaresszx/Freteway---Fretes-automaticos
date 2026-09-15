from __future__ import annotations

from pathlib import Path

from app.services.tabela_frete.table_engine.adapters.normalized_table_adapter import to_canonical_contract
from app.services.tabela_frete.table_engine.classification.column_classifier import classify_columns
from app.services.tabela_frete.table_engine.detection.format_detector import detect_format
from app.services.tabela_frete.table_engine.detection.structure_detector import detect_structure
from app.services.tabela_frete.table_engine.extraction.document import extract_document
from app.services.tabela_frete.table_engine.mapping.destination_mapper import map_destinations
from app.services.tabela_frete.table_engine.mapping.semantic_mapper import SemanticMapper
from app.services.tabela_frete.table_engine.mapping.surcharge_mapper import map_surcharges
from app.services.tabela_frete.table_engine.mapping.weight_band_mapper import map_weight_bands
from app.services.tabela_frete.table_engine.models import FreightTable, Surcharge, WeightBand
from app.services.tabela_frete.table_engine.normalization.city_normalizer import normalize_city_name
from app.services.tabela_frete.table_engine.normalization.cep_normalizer import normalize_cep
from app.services.tabela_frete.table_engine.normalization.number_normalizer import normalize_number
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
        table = FreightTable(
            carrier=carrier,
            origin=origin or {"city": "Guarulhos", "state": "SP"},
            validity={"source": file_path.name},
            weight_bands=map_weight_bands(mapped),
            destinations=map_destinations(mapped),
            surcharges=map_surcharges(mapped),
            delivery_rules=[{"source": file_path.name, "kind": "delivery"}],
            collection_rules=[{"source": file_path.name, "kind": "collection"}],
            general_rules=[{"source": file_path.name, "kind": "generic", "rules": detect_rules(raw_text)}],
        )
        validation = validate_table(table)
        contract = to_canonical_contract(table)
        contract["format_detected"] = format_name
        contract["structure"] = structure
        contract["validation"] = validation
        return contract

    def _extract_rows(self, raw_text: str) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        lines = [line for line in raw_text.splitlines() if line.strip()]
        if not lines:
            return rows
        delimiter = "|" if any("|" in line for line in lines) else ","
        try:
            import csv
            import io

            reader = csv.reader(io.StringIO(raw_text), delimiter=delimiter)
            table = [row for row in reader if row and any(cell.strip() for cell in row)]
            if len(table) >= 2:
                header = [cell.strip() for cell in table[0]]
                for values in table[1:]:
                    row = {}
                    for idx, header_name in enumerate(header):
                        if idx < len(values):
                            row[header_name] = values[idx].strip()
                    if row:
                        rows.append(row)
                return rows
        except Exception:
            pass

        for line in lines:
            if "|" in line:
                parts = [part.strip() for part in line.split("|")]
                headers = [part for part in parts if part]
                if len(headers) >= 2:
                    rows.append({str(index): value for index, value in enumerate(headers)})
            elif ":" in line and len(line.split(":")) >= 2:
                key, value = line.split(":", 1)
                rows.append({key.strip(): value.strip()})
        return rows


def import_table_document(path: str | Path, *, carrier: str | None = None, origin: dict[str, str] | None = None) -> dict[str, object]:
    return TableImportService().import_document(path, carrier=carrier, origin=origin)
