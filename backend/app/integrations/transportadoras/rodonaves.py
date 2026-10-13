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
    "base_url": QUOTATION_URL, "endpoint_cotacao": "/api/v1/gera-cotacao",
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


class RodonavesAdapter(TransportadoraAdapter):
    nome = "RTE Rodonaves"

    def __init__(self, configuracao):
        self.configuracao = configuracao

    async def _token(self, client, base: str) -> dict:
        response = await client.post(f"{base}/token", data={
            "auth_type": "DEV", "grant_type": "password", "companyId": "1",
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
        days = int(response.json()["DeliveryTime"])
        if days < 0:
            raise ValueError("Prazo inválido")
        return days

    async def cotar(self, cotacao_payload: dict) -> ResultadoCotacao:
        cfg, p = self.configuracao, cotacao_payload
        if not cfg.ativa:
            return ResultadoCotacao(status="error", erro_codigo="RODONAVES_API_INATIVA", erro_mensagem="API Rodonaves inativa.")
        if not cfg.usuario_integracao or not cfg.credencial_criptografada:
            return ResultadoCotacao(status="error", erro_codigo="RODONAVES_CREDENCIAL_AUSENTE", erro_mensagem="Informe o usuário e a senha de acesso à API Rodonaves.")
        document = _digits(cfg.documento_devedor)
        receiver = _digits(p.get("documento_destinatario"))
        contact = (getattr(cfg, "contato_nome", None) or "").strip()
        phone = _digits(getattr(cfg, "contato_telefone", None))
        if len(document) not in {11, 14} or not contact or len(phone) < 10:
            return ResultadoCotacao(status="error", erro_codigo="RODONAVES_CONFIGURACAO_INCOMPLETA", erro_mensagem="Informe CPF/CNPJ do cliente, nome e telefone de contato na configuração da Rodonaves.")
        if len(receiver) not in {11, 14}:
            return ResultadoCotacao(status="error", erro_codigo="RODONAVES_DESTINATARIO_AUSENTE", erro_mensagem="Informe o CPF/CNPJ do destinatário na cotação.")
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
                    "CustomerTaxIdRegistration": document, "ReceiverCpfcnp": receiver,
                    "ContactName": contact, "ContactPhoneNumber": phone,
                    "TotalPackages": p["quantidade_volumes"],
                    "Packs": [{"AmountPackages": v["quantidade"], "Weight": v["peso_kg"],
                               "Length": v["comprimento_cm"], "Height": v["altura_cm"],
                               "Width": v["largura_cm"]} for v in p["volumes"]],
                }
                # Gera um registro TMS: não repetir POST automaticamente após falha.
                response = await client.post(f"{QUOTATION_URL}/api/v1/gera-cotacao", headers=quotation_headers, json=body)
                if response.status_code in {401, 403}:
                    raise RodonavesError("RODONAVES_AUTENTICACAO_RECUSADA", "A Rodonaves não autorizou a geração da cotação. Confira a liberação da API.")
                if response.status_code == 400:
                    raise RodonavesError("RODONAVES_COTACAO_RECUSADA", "A Rodonaves recusou os dados da cotação. Confira o cadastro do destinatário e o vínculo do cliente na transportadora.")
                response.raise_for_status()
                result = response.json()
                value = freight_value(result["FreightValue"])
                details = {"protocolo": result.get("ProtocolId"), "avisos": []}
                try:
                    days = await asyncio.wait_for(self._delivery(client, p), timeout=5)
                except (httpx.HTTPError, RodonavesError, KeyError, TypeError, ValueError, TimeoutError):
                    days = None
                    details["avisos"].append("Frete obtido; prazo indisponível na API de prazo da Rodonaves.")
                return ResultadoCotacao(status="success", valor_frete=value, prazo_dias=days, detalhamento=details)
        except RodonavesError as exc:
            return ResultadoCotacao(status="error", erro_codigo=exc.code, erro_mensagem=exc.message)
        except httpx.TimeoutException as exc:
            raise TimeoutError from exc
        except (httpx.HTTPError, KeyError, TypeError, ValueError, ArithmeticError):
            return ResultadoCotacao(status="error", erro_codigo="RODONAVES_API_ERRO", erro_mensagem="Falha ao consultar a API Rodonaves. Confira os dados e a disponibilidade do serviço.")
