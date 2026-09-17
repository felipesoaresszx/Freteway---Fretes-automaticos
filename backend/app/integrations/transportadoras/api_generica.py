"""Adapter configurável para APIs REST de transportadoras."""

from urllib.parse import urljoin

import httpx

from app.integrations.transportadoras.base import ResultadoCotacao, TransportadoraAdapter
from app.models.models import TransportadoraConfiguracaoApi
from app.services.credenciais import descriptografar
from app.core.url_security import UnsafeUrlError, validate_external_url


def _campo(dados: object, caminho: str) -> object:
    atual = dados
    for parte in caminho.split("."):
        if isinstance(atual, list) and parte.isdigit():
            atual = atual[int(parte)]
        elif isinstance(atual, dict):
            atual = atual[parte]
        else:
            raise KeyError(caminho)
    return atual


class ApiGenericaAdapter(TransportadoraAdapter):
    nome = "API configurável"

    def __init__(self, configuracao: TransportadoraConfiguracaoApi):
        self.configuracao = configuracao

    async def cotar(self, cotacao_payload: dict) -> ResultadoCotacao:
        if not self.configuracao.ativa:
            return ResultadoCotacao(status="error", erro_codigo="API_INATIVA", erro_mensagem="Configuração de API inativa")
        url = urljoin(f"{self.configuracao.base_url.rstrip('/')}/", self.configuracao.endpoint_cotacao.lstrip("/"))
        try:
            validate_external_url(url)
        except UnsafeUrlError as exc:
            return ResultadoCotacao(status="error", erro_codigo="API_URL_INSEGURA", erro_mensagem=str(exc))

        headers = {"Accept": "application/json"}
        request_payload = dict(cotacao_payload)
        auth = None
        credencial = descriptografar(self.configuracao.credencial_criptografada)
        if self.configuracao.tipo_autenticacao == "bearer" and credencial:
            headers["Authorization"] = f"Bearer {credencial}"
        elif self.configuracao.tipo_autenticacao == "api_key" and credencial:
            headers[self.configuracao.nome_header or "X-API-Key"] = credencial
        elif self.configuracao.tipo_autenticacao == "query_param" and credencial:
            request_payload[self.configuracao.nome_header or "api_key"] = credencial
        elif self.configuracao.tipo_autenticacao == "basic" and credencial:
            usuario, separador, senha = credencial.partition(":")
            if not separador:
                return ResultadoCotacao(status="error", erro_codigo="CREDENCIAL_INVALIDA", erro_mensagem="Use usuário:senha para autenticação Basic")
            auth = httpx.BasicAuth(usuario, senha)

        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=False) as cliente:
                if self.configuracao.metodo_http == "GET":
                    resposta = await cliente.get(url, params=request_payload, headers=headers, auth=auth)
                else:
                    resposta = await cliente.post(url, json=request_payload, headers=headers, auth=auth)
                resposta.raise_for_status()
                dados = resposta.json()
            return ResultadoCotacao(
                status="success",
                valor_frete=float(_campo(dados, self.configuracao.campo_valor)),
                prazo_dias=int(_campo(dados, self.configuracao.campo_prazo)),
            )
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            return ResultadoCotacao(status="error", erro_codigo="ERRO_API_TRANSPORTADORA", erro_mensagem=str(exc))
