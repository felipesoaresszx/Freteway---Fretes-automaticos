from __future__ import annotations

from app.services.tabela_frete.table_engine.models import Surcharge


def map_surcharges(rows: list[dict[str, object]]) -> list[Surcharge]:
    taxes: list[Surcharge] = []
    seen: set[tuple[str, str, float, str | None]] = set()
    for row in rows:
        for key, value in row.items():
            if key in {"gris", "ad_valorem", "pedagio"} and value is not None:
                kind = "PERCENTAGE" if key in {"gris", "ad_valorem"} else "FIXED"
                basis = "INVOICE_VALUE" if key in {"gris", "ad_valorem"} else "FREIGHT"
                identity = (str(key).upper(), kind, float(value), basis)
                if identity not in seen:
                    taxes.append(Surcharge(
                        code=identity[0], name=identity[0], type=kind,
                        value=float(value), basis=basis,
                    ))
                    seen.add(identity)
    return taxes
