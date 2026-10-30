"""Contrato REST Rodonaves: tokens por serviço, cidades DNE e cotação TMS."""

import asyncio
import math
import re
import unicodedata
from decimal import Decimal

import httpx

from app.integrations.transportadoras.base import ResultadoCotacao, TransportadoraAdapter
from app.services.credenciais import descriptografar


QUOTATION_URL = "https://quotation-apigateway.rte.com.br"
DNE_URL = "https://dne-api.rte.com.br"
DELIVERY_URL = "https://01wapi.rte.com.br"
RODONAVES_DEFAULTS = {
    "base_url": QUOTATION_URL, "endpoint_cotacao": "/api/v1/simula-cotacao",
    "metodo_http": "POST", "tipo_autenticacao": "rodonaves_login",
    "auth_url": f"{QUOTATION_URL}/token", "campo_valor": "FreightValue",
    "campo_prazo": "DeliveryTime", "nome_header": None,
}


def is_rodonaves(nome: str) -> bool:
    return "rodonaves" in nome.casefold()


class RodonavesError(Exception):
    def __init__(self, code: str, message: str):
        self.code, self.message = code, message
        super().__init__(message)


def _digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def _city(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", value) if not unicodedata.combining(c)).upper().strip()


def freight_value(value: object) -> float:
    # O contrato declara string; aceita decimal JSON e representação monetária BR.
    text = str(value).strip().replace("R$", "").replace(" ", "")
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    result = float(Decimal(text))
    if not math.isfinite(result) or result <= 0:
        raise ValueError("Frete inválido")
    return result


def delivery_days(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError("Prazo inválido")
    numeric = Decimal(str(value))
    if not numeric.is_finite() or numeric < 0 or numeric != numeric.to_integral_value():
        raise ValueError("Prazo inválido")
    return int(numeric)


class RodonavesAdapter(TransportadoraAdapter):
    nome = "RTE Rodonaves"

    def __init__(self, configuracao):
        self.configuracao = configuracao

    async def _token(self, client, base: str) -> dict:
        response = await client.post(f"{base}/token", data={
            "auth_type": "DEV", "grant_type": "password",
            "username": self.configuracao.usuario_integracao,
            "password": descriptografar(self.configuracao.credencial_criptografada),
        })
        if response.status_code in {400, 401, 403}:
            raise RodonavesError("RODONAVES_AUTENTICACAO_RECUSADA", "A Rodonaves recusou o acesso à API. Confira o usuário, a senha e a liberação da integração; o login do portal pode ser diferente.")
        response.raise_for_status()
        token = response.json().get("access_token")
        if not isinstance(token, str) or not token.strip():
            raise ValueError("Token ausente")
        return {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    async def _city_id(self, client, headers, cep: str) -> int:
        response = await client.get(f"{DNE_URL}/api/cities/byzipcode", params={"zipCode": cep}, headers=headers)
        response.raise_for_status()
        city_id = int(response.json()["Id"])
        if city_id <= 0:
            raise ValueError("Cidade ausente")
        return city_id

    async def _delivery(self, client, payload) -> int:
        headers = await self._token(client, DELIVERY_URL)
        response = await client.post(f"{DELIVERY_URL}/api/v1/prazo-entrega", headers=headers, json={
            "OriginCityDescription": _city(payload["origem_cidade"]),
            "OriginUFDescription": payload["origem_uf"].upper(),
            "DestinationCityDescription": _city(payload["destino_cidade"]),
            "DestinationUFDescription": payload["destino_uf"].upper(),
        })
        response.raise_for_status()
        return delivery_days(response.json()["DeliveryTime"])

    async def cotar(self, cotacao_payload: dict) -> ResultadoCotacao:
        cfg, p = self.configuracao, cotacao_payload
        if not cfg.ativa:
            return ResultadoCotacao(status="error", erro_codigo="RODONAVES_API_INATIVA", erro_mensagem="API Rodonaves inativa.")
        if not cfg.usuario_integracao or not cfg.credencial_criptografada:
            return ResultadoCotacao(status="error", erro_codigo="RODONAVES_CREDENCIAL_AUSENTE", erro_mensagem="Informe o usuário e a senha de acesso à API Rodonaves.")
        document = _digits(cfg.documento_devedor)
        if len(document) not in {11, 14}:
            return ResultadoCotacao(status="error", erro_codigo="RODONAVES_CONFIGURACAO_INCOMPLETA", erro_mensagem="Informe CPF/CNPJ do cliente na configuração da Rodonaves.")
        origin, destination = _digits(p.get("origem_cep")), _digits(p.get("destino_cep"))
        if len(origin) != 8 or len(destination) != 8:
            return ResultadoCotacao(status="error", erro_codigo="RODONAVES_CEP_INVALIDO", erro_mensagem="Informe os CEPs de origem e destino com oito dígitos.")
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
                quotation_headers = await self._token(client, QUOTATION_URL)
                dne_headers = await self._token(client, DNE_URL)
                origin_id, destination_id = await asyncio.gather(
                    self._city_id(client, dne_headers, origin), self._city_id(client, dne_headers, destination),
                )
                body = {
                    "OriginZipCode": origin, "OriginCityId": origin_id,
                    "DestinationZipCode": destination, "DestinationCityId": destination_id,
                    "TotalWeight": p["peso"], "EletronicInvoiceValue": p["valor_nf"],
                    "CustomerTaxIdRegistration": document,
                    "TotalPackages": p["quantidade_volumes"],
                    "Packs": [{"AmountPackages": v["quantidade"], "Weight": v["peso_kg"],
                               "Length": v["comprimento_cm"], "Height": v["altura_cm"],
                               "Width": v["largura_cm"]} for v in p["volumes"]],
                }
                # Manter uma tentativa por consulta, sem repetir o POST automaticamente.
                response = await client.post(f"{QUOTATION_URL}/api/v1/simula-cotacao", headers=quotation_headers, json=body)
                if response.status_code in {401, 403}:
                    raise RodonavesError("RODONAVES_AUTENTICACAO_RECUSADA", "A Rodonaves não autorizou a geração da cotação. Confira a liberação da API.")
                if response.status_code == 400:
                    try:
                        error = response.json()
                    except ValueError:
                        error = {}
                    message = error.get("Message") if isinstance(error, dict) else None
                    # Só traduz mensagens conhecidas; nunca devolver o corpo externo.
                    if message == "Cliente destinatário não encontrado.":
                        raise RodonavesError("RODONAVES_DESTINATARIO_NAO_ENCONTRADO", "A API Rodonaves não encontrou o cadastro do destinatário. Confira o CPF/CNPJ; se o portal cotar com os mesmos dados, solicite à Rodonaves a verificação do cadastro na API.")
                    if message == "Cliente remetente não encontrado.":
                        raise RodonavesError("RODONAVES_REMETENTE_NAO_ENCONTRADO", "A API Rodonaves não encontrou o cadastro do remetente. Confira o CPF/CNPJ configurado e sua liberação na transportadora.")
                    raise RodonavesError("RODONAVES_COTACAO_RECUSADA", "A Rodonaves recusou os dados da cotação. Confira o cadastro do destinatário e o vínculo do cliente na transportadora.")
                response.raise_for_status()
                result = response.json()
                if not isinstance(result, dict):
                    raise ValueError("Resposta de cotação inválida")
                # A produção usa Value/ProtocolNumber; manter o contrato antigo.
                raw_value = result.get("Value")
                value = freight_value(raw_value if raw_value is not None else result.get("FreightValue"))
                protocol = result.get("ProtocolNumber")
                details = {"protocolo": protocol if protocol is not None else result.get("ProtocolId"),
                           "avisos": ["Simulação Rodonaves: valor aproximado, sujeito a alteração na cotação definitiva."]}
                try:
                    if result.get("ActiveDeliveryTime") is False or result.get("DeliveryDaysOnError") is True:
                        raise ValueError("Prazo da cotação indisponível")
                    days = delivery_days(result.get("DeliveryTime"))
                except (ValueError, ArithmeticError):
                    try:
                        days = await asyncio.wait_for(self._delivery(client, p), timeout=5)
                    except (httpx.HTTPError, RodonavesError, KeyError, TypeError, ValueError, ArithmeticError, TimeoutError):
                        days = None
                        details["avisos"].append("Frete obtido; prazo indisponível na API de prazo da Rodonaves.")
                return ResultadoCotacao(status="success", valor_frete=value, prazo_dias=days, detalhamento=details)
        except RodonavesError as exc:
            return ResultadoCotacao(status="error", erro_codigo=exc.code, erro_mensagem=exc.message)
        except httpx.TimeoutException as exc:
            raise TimeoutError from exc
        except (httpx.HTTPError, KeyError, TypeError, ValueError, ArithmeticError):
            return ResultadoCotacao(status="error", erro_codigo="RODONAVES_API_ERRO", erro_mensagem="Falha ao consultar a API Rodonaves. Confira os dados e a disponibilidade do serviço.")
