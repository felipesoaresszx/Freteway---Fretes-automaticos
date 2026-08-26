from xml.sax.saxutils import escape
from xml.etree import ElementTree

import httpx

from app.integrations.ssw.constants import SERVICE_URL, SOAP_NAMESPACE
from app.integrations.ssw.exceptions import SSWConnectionError, SSWInvalidResponseError, SSWTimeoutError


class SSWClient:
    def __init__(self, endpoint: str = SERVICE_URL, timeout_seconds: float = 20):
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds

    async def _call(self, operation: str, parameters: dict[str, object]) -> str:
        arguments = "".join(f"<{name}>{escape(str(value))}</{name}>" for name, value in parameters.items())
        envelope = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '
            f'xmlns:ssw="{SOAP_NAMESPACE}"><soapenv:Body><ssw:{operation}>{arguments}'
            f'</ssw:{operation}></soapenv:Body></soapenv:Envelope>'
        )
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds, follow_redirects=False) as client:
                response = await client.post(self.endpoint, content=envelope.encode("utf-8"), headers={
                    "Content-Type": "text/xml; charset=utf-8",
                    "SOAPAction": f'"{SOAP_NAMESPACE}#{"cotacao" if operation == "cotar" else operation}"',
                })
                response.raise_for_status()
        except httpx.TimeoutException as exc: raise SSWTimeoutError("Tempo limite excedido no SSW") from exc
        except httpx.HTTPError as exc: raise SSWConnectionError("Nao foi possivel conectar ao SSW") from exc
        try:
            root = ElementTree.fromstring(response.content)
            fault = next((node for node in root.iter() if node.tag.endswith("Fault")), None)
            if fault is not None: raise SSWConnectionError("O SSW recusou a chamada SOAP")
            returned = next((node for node in root.iter() if node.tag.endswith("return")), None)
            if returned is None or returned.text is None: raise SSWInvalidResponseError("SOAP SSW sem retorno")
            return returned.text
        except ElementTree.ParseError as exc: raise SSWInvalidResponseError("Envelope SOAP invalido") from exc

    async def get_mercadorias(self, *, dominio: str, login: str, senha: str, cnpj_pagador: str) -> str:
        return await self._call("getMercadoria", {"dominio": dominio, "login": login, "senha": senha, "cnpjPagador": cnpj_pagador})

    async def cotar(self, *, dominio: str, login: str, senha: str, cnpj_pagador: str, **data: object) -> str:
        names = {
            "cep_origem": "cepOrigem", "cep_destino": "cepDestino", "valor_nf": "valorNF",
            "quantidade": "quantidade", "peso": "peso", "volume": "volume", "mercadoria": "mercadoria",
            "cnpj_destinatario": "cnpjDestinatario", "coletar": "coletar", "entrega_dificil": "entDificil",
            "destinatario_contribuinte": "destContribuinte", "qtde_pares": "qtdePares", "altura": "altura",
            "largura": "largura", "comprimento": "comprimento", "fator_multiplicador": "fatorMultiplicador",
            "cnpj_remetente": "cnpjRemetente",
        }
        parameters: dict[str, object] = {"dominio": dominio, "login": login, "senha": senha, "cnpjPagador": cnpj_pagador}
        parameters.update({target: data.get(source, "") for source, target in names.items()})
        return await self._call("cotar", parameters)
