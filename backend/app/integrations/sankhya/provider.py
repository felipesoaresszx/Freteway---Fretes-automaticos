import json
import math
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from app.schemas.cotacao import ResultadoTransportadora


_FORBIDDEN_TEXT = str.maketrans({character: "" for character in '\"[]{}'})


class SankhyaQuoteProvider:
    """Adapta o motor ao contrato textual compativel com a Frenet."""

    @staticmethod
    def sanitize(value: Any) -> str:
        text = "" if value is None else str(value)
        text = text.translate(_FORBIDDEN_TEXT)
        return re.sub(r"[\x00-\x1f\x7f]+", " ", text).strip()

    @staticmethod
    def price(value: Any) -> str:
        try:
            number = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ValueError("Preco de frete invalido") from exc
        if not number.is_finite() or number < 0:
            raise ValueError("Preco de frete invalido")
        return format(number.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "f")

    @staticmethod
    def delivery_days(value: Any) -> str:
        if isinstance(value, bool):
            raise ValueError("Prazo de entrega invalido")
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("Prazo de entrega invalido") from exc
        if not math.isfinite(number) or number < 0 or not number.is_integer():
            raise ValueError("Prazo de entrega invalido")
        return str(int(number))

    def line(self, result: ResultadoTransportadora, *, carrier_code: str = "",
             codparc: int = 0, service_code: str = "", service_description: str = "") -> dict[str, Any]:
        error = result.status != "success" or result.valor_frete is None or result.prazo_dias is None
        message = ""
        shipping_price = "0"
        delivery_time = "0"
        if error:
            if result.erro:
                message = f"{result.erro.codigo}: {result.erro.mensagem}"
            else:
                message = "Cotacao indisponivel"
        else:
            try:
                shipping_price = self.price(result.valor_frete)
                delivery_time = self.delivery_days(result.prazo_dias)
            except ValueError as exc:
                error = True
                message = str(exc)
        return {
            "ServiceCode": self.sanitize(service_code),
            "ServiceDescription": self.sanitize(service_description or result.transportadora),
            "Carrier": self.sanitize(result.transportadora),
            "CarrierCode": self.sanitize(carrier_code),
            "CodParcTransp": int(codparc) if codparc and int(codparc) > 0 else 0,
            "ShippingPrice": shipping_price,
            "DeliveryTime": delivery_time,
            "Error": bool(error),
            "Msg": self.sanitize(message),
        }

    @staticmethod
    def serialize(lines: list[dict[str, Any]]) -> str:
        return json.dumps({"ShippingSevicesArray": lines}, ensure_ascii=False, separators=(",", ":"))
