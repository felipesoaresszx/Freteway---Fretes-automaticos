from __future__ import annotations

from app.services.tabela_frete.table_engine.models import Surcharge


def map_surcharges(rows: list[dict[str, object]]) -> list[Surcharge]:
    taxes: list[Surcharge] = []
    for row in rows:
        for key, value in row.items():
            if key in {"gris", "ad_valorem", "pedagio"} and value is not None:
                taxes.append(Surcharge(code=str(key).upper(), name=str(key).upper(), type="PERCENTAGE" if key in {"gris", "ad_valorem"} else "FIXED", value=float(value), basis="INVOICE_VALUE" if key in {"gris", "ad_valorem"} else "FREIGHT"))
    return taxes
