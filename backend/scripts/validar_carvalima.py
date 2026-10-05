"""Extrai a Carvalima para revisão sem alterar banco ou publicar tabela."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.tabela_frete.carvalima_pdf import extract_carvalima_pdf  # noqa: E402
from app.services.tabela_frete.calculo_universal import calcular_universal  # noqa: E402


def main():
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, default=root / "tabelas_trans" / "TABELA CARVALIMA.pdf")
    parser.add_argument("--output", type=Path, default=root / "tmp" / "carvalima-validacao")
    parser.add_argument("--confirm-current-prices", action="store_true", help="Use somente após confirmação explícita dos preços vigentes.")
    parser.add_argument("--valid-from", type=date.fromisoformat, help="Início da vigência confirmado pelo operador (AAAA-MM-DD).")
    parser.add_argument("--valid-until", type=date.fromisoformat, help="Fim da vigência confirmado pelo operador (AAAA-MM-DD).")
    args = parser.parse_args()
    if bool(args.valid_from) != bool(args.valid_until):
        parser.error("Informe início e fim da vigência juntos")
    if args.valid_until and (args.valid_until < args.valid_from or not args.confirm_current_prices):
        parser.error("Vigência inválida ou preços não confirmados")
    data = extract_carvalima_pdf(args.pdf)
    if not data:
        parser.error("Documento não reconhecido como tabela Carvalima")
    if args.confirm_current_prices:
        data["metadata"]["prices_confirmed_current"] = True
        data["metadata"]["prices_confirmation_note"] = "Preços atuais confirmados pelo operador; data divergente do PDF preservada."
    if args.valid_from:
        data["metadata"]["document_original_validity"] = dict(data["validity"])
        data["metadata"]["validity_override_source"] = "Vigência definida explicitamente pelo operador."
        data["validity"] = {"start": args.valid_from.isoformat(), "end": args.valid_until.isoformat()}
        data["metadata"]["commercial_pending_items"] = []
    examples = []
    for city, uf in (("Campo Grande", "MS"), ("Cuiaba", "MT"), ("Rio Branco", "AC"), ("Belem", "PA"), ("Alenquer", "PA"), ("Porto Velho", "RO")):
        request = {"origem_cidade": "Sao Paulo", "origem_uf": "SP", "destino_cidade": city, "destino_uf": uf, "peso": 100, "valor_nf": 1000}
        examples.append({"entrada": request, "resultado": calcular_universal(data, request)})
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "tabela-normalizada.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.output / "cotacoes-conferencia.json").write_text(json.dumps(examples, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"estatisticas": data["estatisticas"], "output": str(args.output), "validity": data["validity"], "prices_confirmed_current": bool(args.confirm_current_prices)}, ensure_ascii=True))


if __name__ == "__main__":
    main()
