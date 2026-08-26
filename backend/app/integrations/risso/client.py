import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import ClassVar

import httpx

from app.core.config import get_settings
from app.core.url_security import validate_external_url
from app.integrations.risso.exceptions import (
    RissoAuthenticationError, RissoConnectionError, RissoRateLimitError,
    RissoResponseError, RissoTimeoutError,
)
from app.integrations.risso.schemas import (
    RissoApprovalPayload, RissoApprovalResponse, RissoQuotePayload, RissoQuoteResponse,
)


class RissoClient:
    _tokens: ClassVar[dict[tuple[str, str], tuple[str, datetime]]] = {}

    def __init__(self, credentials: dict[str, str]):
        self.credentials = credentials
        self.base_url = credentials.get(
            "base_url", "https://platform.senior.com.br/t/senior.com.br/bridge/1.0/rest/tms"
        ).rstrip("/")
        self.auth_base_url = credentials.get(
            "auth_base_url", "https://platform.senior.com.br/t/senior.com.br/bridge/1.0/rest"
        ).rstrip("/")
        self.timeout = get_settings().TIMEOUT_API_INTEGRACAO

    def _headers(self, token: str | None = None) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    async def _authenticate(self, client: httpx.AsyncClient) -> str:
        username, password = self.credentials.get("username", ""), self.credentials.get("password", "")
        if not username or not password:
            raise RissoAuthenticationError("Credenciais Senior não configuradas")
        cache_key = (self.auth_base_url, username)
        cached = self._tokens.get(cache_key)
        now = datetime.now(UTC)
        if cached and cached[1] > now + timedelta(minutes=2):
            return cached[0]

        url = f"{self.auth_base_url}/platform/authentication/actions/login"
        validate_external_url(url)
        try:
            response = await client.post(
                url, json={"username": username, "password": password}, headers=self._headers()
            )
        except httpx.TimeoutException as exc:
            raise RissoTimeoutError("Tempo limite ao autenticar na Senior") from exc
        except httpx.RequestError as exc:
            raise RissoConnectionError("Falha de conexão ao autenticar na Senior") from exc
        if response.status_code in {401, 403}:
            raise RissoAuthenticationError("Autenticação Senior recusada")
        if response.status_code >= 400:
            raise RissoAuthenticationError(f"Autenticação Senior falhou (HTTP {response.status_code})")
        try:
            body = response.json()
        except ValueError as exc:
            raise RissoResponseError("Resposta de autenticação Senior inválida") from exc
        token_data = body.get("jsonToken") or body
        if isinstance(token_data, str):
            try:
                token_data = json.loads(token_data)
            except json.JSONDecodeError as exc:
                raise RissoResponseError("Token retornado pela Senior é inválido") from exc
        if not isinstance(token_data, dict) or not token_data.get("access_token"):
            raise RissoResponseError("Resposta de autenticação Senior inválida")
        expires_in = int(token_data.get("expires_in", 3600))
        self._tokens[cache_key] = (token_data["access_token"], now + timedelta(seconds=expires_in))
        return token_data["access_token"]

    async def validate_credentials(self) -> bool:
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
            await self._authenticate(client)
        return True

    async def quote(self, payload: RissoQuotePayload) -> RissoQuoteResponse:
        body = await self._authorized_post("documentos/actions/simulaCotacaoFrete", payload.model_dump(exclude_none=True, mode="json"))
        try:
            return RissoQuoteResponse.model_validate(body)
        except (TypeError, ValueError) as exc:
            raise RissoResponseError("Resposta de cotação Senior inválida") from exc

    async def approve_quote(self, quote_id: str, email: str | None = None) -> RissoApprovalResponse:
        payload = RissoApprovalPayload(idCotacaoFrete=quote_id, email=email)
        body = await self._authorized_post(
            "documentos/actions/aprovaCotacaoFrete", payload.model_dump(exclude_none=True)
        )
        try:
            return RissoApprovalResponse.model_validate(body)
        except (TypeError, ValueError) as exc:
            raise RissoResponseError("Resposta de aprovação Senior inválida") from exc

    async def _authorized_post(self, path: str, payload: dict) -> dict:
        url = f"{self.base_url}/{path.lstrip('/')}"
        validate_external_url(url)
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
            token = await self._authenticate(client)
            refreshed = False
            response: httpx.Response | None = None
            for attempt in range(3):
                try:
                    response = await client.post(url, json=payload, headers=self._headers(token))
                except httpx.TimeoutException as exc:
                    raise RissoTimeoutError("Tempo limite na API da Risso") from exc
                except httpx.RequestError as exc:
                    raise RissoConnectionError("Falha de conexão com a API da Risso") from exc
                if response.status_code == 401 and not refreshed:
                    self._tokens.pop((self.auth_base_url, self.credentials.get("username", "")), None)
                    token = await self._authenticate(client)
                    refreshed = True
                    continue
                if response.status_code != 429:
                    break
                if attempt < 2:
                    retry_after = response.headers.get("Retry-After", "")
                    delay = min(float(retry_after), 4.0) if retry_after.replace(".", "", 1).isdigit() else float(2 ** attempt)
                    await asyncio.sleep(delay)
            assert response is not None
            if response.status_code == 429:
                raise RissoRateLimitError("Limite de requisições da Risso excedido")
            if response.status_code in {401, 403}:
                raise RissoAuthenticationError("Autorização da API Senior recusada")
            if response.status_code >= 400:
                detail = ""
                try:
                    error_body = response.json()
                    if isinstance(error_body, dict):
                        message = error_body.get("message") or error_body.get("reason")
                        if message:
                            detail = f": {str(message)[:300]}"
                except ValueError:
                    pass
                raise RissoResponseError(f"API Senior retornou HTTP {response.status_code}{detail}")
            try:
                body = response.json()
            except ValueError as exc:
                raise RissoResponseError("API Senior retornou JSON inválido") from exc
            if not isinstance(body, dict):
                raise RissoResponseError("API Senior retornou formato inválido")
            return body
