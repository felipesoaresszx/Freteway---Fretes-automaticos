"""Adapter oficial da API REST de cotação JAMEF."""

from datetime import date, datetime, timedelta
from typing import ClassVar

import httpx

from app.core.url_security import validate_external_url
from app.integrations.transportadoras.base import ResultadoCotacao, TransportadoraAdapter
from app.models.models import TransportadoraConfiguracaoApi
from app.services.credenciais import descriptografar


class JamefAuthenticationError(Exception):
    """Falha segura de autenticação, sem incluir credenciais ou resposta remota."""


class JamefAdapter(TransportadoraAdapter):
    nome = "JAMEF"
    _tokens: ClassVar[dict[str, tuple[str, datetime]]] = {}

    def __init__(self, configuracao: TransportadoraConfiguracaoApi):
        self.configuracao = configuracao

    async def _token(self, client: httpx.AsyncClient) -> str:
        cache_key = self.configuracao.id
        cached = self._tokens.get(cache_key)
        if cached and cached[1] > datetime.utcnow() + timedelta(minutes=2):
            return cached[0]
        auth_url = self.configuracao.auth_url or "https://api.jamef.com.br/auth/v1"
        url = f"{auth_url.rstrip('/')}/login"
        validate_external_url(url)
        response = await client.post(url, json={
            "username": self.configuracao.usuario_integracao,
            "password": descriptografar(self.configuracao.credencial_criptografada),
        })
        if response.status_code in {401, 403}:
            raise JamefAuthenticationError
        response.raise_for_status()
        body = response.json()
        try:
            token_data = body["dado"][0]
            token = token_data["accessToken"]
            expires_in = int(token_data.get("expiresIn", 3600))
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ValueError("Resposta de autenticação JAMEF inválida") from exc
        self._tokens[cache_key] = (token, datetime.utcnow() + timedelta(seconds=expires_in))
        return token

    async def cotar(self, cotacao_payload: dict) -> ResultadoCotacao:
        if not self.configuracao.ativa:
            return ResultadoCotacao(status="error", erro_codigo="JAMEF_API_INATIVA", erro_mensagem="API JAMEF inativa")
        if not self.configuracao.usuario_integracao or not self.configuracao.credencial_criptografada:
            return ResultadoCotacao(status="error", erro_codigo="JAMEF_CREDENCIAL_AUSENTE", erro_mensagem="Credencial JAMEF não configurada")
        if not self.configuracao.documento_devedor:
            return ResultadoCotacao(status="error", erro_codigo="JAMEF_PAGADOR_AUSENTE", erro_mensagem="Documento do pagador não configurado")

        quote_url = f"{self.configuracao.base_url.rstrip('/')}/{self.configuracao.endpoint_cotacao.lstrip('/')}"
        validate_external_url(quote_url)
        payload = {
            "tipoTransporte": self.configuracao.tipo_transporte or "1",
            "documentoDevedor": self.configuracao.documento_devedor,
            "cepOrigem": cotacao_payload["origem_cep"],
            "cepDestino": cotacao_payload["destino_cep"],
            "quantidadeVolume": cotacao_payload["quantidade_volumes"],
            "pesoMercadoria": cotacao_payload["peso"],
            "valorNotaFiscal": cotacao_payload["valor_nf"],
            "metragemCubica": cotacao_payload["volume_total_m3"],
            "dataColeta": date.today().strftime("%d/%m/%Y"),
        }
        if self.configuracao.filial_origem:
            payload["filialOrigem"] = self.configuracao.filial_origem
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
                token = await self._token(client)
                response = await client.post(quote_url, json=payload, headers={"Authorization": f"Bearer {token}"})
                if response.status_code == 401:
                    self._tokens.pop(self.configuracao.id, None)
                    token = await self._token(client)
                    response = await client.post(quote_url, json=payload, headers={"Authorization": f"Bearer {token}"})
                response.raise_for_status()
                body = response.json()
            dado = body["dado"][0]
            previsao = datetime.strptime(dado["previsaoEntrega"], "%d/%m/%Y").date()
            return ResultadoCotacao(
                status="success", valor_frete=float(dado["total"]),
                prazo_dias=max(0, (previsao - date.today()).days), moeda="BRL",
            )
        except JamefAuthenticationError:
            return ResultadoCotacao(
                status="error",
                erro_codigo="JAMEF_AUTENTICACAO_RECUSADA",
                erro_mensagem="Login recusado pela JAMEF. Confira usuário, senha e a liberação do acesso à API.",
            )
        except httpx.TimeoutException as exc:
            raise TimeoutError from exc
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            return ResultadoCotacao(
                status="error", erro_codigo="JAMEF_API_ERRO",
                erro_mensagem=f"Falha na API JAMEF: {type(exc).__name__}",
            )
