import asyncio
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import ClassVar

import httpx

from app.core.config import get_settings
from app.core.url_security import validate_external_url
from app.integrations.correios.exceptions import CorreiosAuthenticationError, CorreiosResponseError


class CorreiosClient:
    _tokens: ClassVar[dict[tuple[str, str, str, str], tuple[str, datetime]]] = {}

    def __init__(self, credentials: dict[str, str]):
        self.credentials = credentials
        self.base_url = credentials.get("base_url", "https://api.correios.com.br").rstrip("/")
        self.timeout = get_settings().TIMEOUT_API_INTEGRACAO
        self._authentication_lock = asyncio.Lock()

    def _cache_key(self) -> tuple[str, str, str, str]:
        """Isola tokens por credencial sem manter a senha em texto no identificador."""
        username = self.credentials.get("username", "").strip()
        component_password = self.credentials.get("api_key", "").strip()
        postage_card = self.credentials.get("postage_card", "").strip()
        fingerprint = sha256(component_password.encode("utf-8")).hexdigest()
        return self.base_url, username, postage_card, fingerprint

    async def _authenticate(self, client: httpx.AsyncClient) -> str:
        username = self.credentials.get("username", "").strip()
        api_key = self.credentials.get("api_key", "").strip()
        postage_card = self.credentials.get("postage_card", "").strip()
        if not username or not api_key:
            raise CorreiosAuthenticationError("Usuário e chave de API dos Correios não configurados")
        if not postage_card:
            raise CorreiosAuthenticationError("Cartão de postagem dos Correios não configurado")
        cache_key = self._cache_key()
        async with self._authentication_lock:
            now = datetime.now(UTC)
            cached = self._tokens.get(cache_key)
            if cached and cached[1] > now + timedelta(minutes=2):
                return cached[0]

            url = f"{self.base_url}/token/v1/autentica/cartaopostagem"
            validate_external_url(url)
            response = await client.post(
                url, auth=httpx.BasicAuth(username, api_key), json={"numero": postage_card},
            )
            if response.status_code in {401, 403}:
                raise CorreiosAuthenticationError("Usuário, senha do componente ou cartão de postagem recusado pelos Correios")
            response.raise_for_status()
            body = response.json()
            token = body.get("token")
            if not token:
                raise CorreiosResponseError("Resposta de autenticação dos Correios inválida")
            expiration = now + timedelta(hours=23)
            if body.get("expiraEm"):
                try:
                    expiration = datetime.fromisoformat(str(body["expiraEm"]).replace("Z", "+00:00"))
                except ValueError:
                    pass
            self._tokens[cache_key] = (token, expiration)
            return token

    async def validate_credentials(self) -> bool:
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
            await self._authenticate(client)
        return True

    async def quote_service(self, service_code: str, request_data: dict[str, str]) -> tuple[dict, dict]:
        price_url = f"{self.base_url}/preco/v1/nacional/{service_code}"
        deadline_url = f"{self.base_url}/prazo/v1/nacional/{service_code}"
        validate_external_url(price_url)
        validate_external_url(deadline_url)
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
            token = await self._authenticate(client)
            headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
            price = await client.get(price_url, params=request_data, headers=headers)
            deadline = await client.get(deadline_url, params={
                "cepOrigem": request_data["cepOrigem"], "cepDestino": request_data["cepDestino"],
            }, headers=headers)
            if price.status_code == 401 or deadline.status_code == 401:
                self._tokens.pop(self._cache_key(), None)
                raise CorreiosAuthenticationError("Token dos Correios recusado")
            price.raise_for_status()
            deadline.raise_for_status()
            price_body, deadline_body = price.json(), deadline.json()
            if not isinstance(price_body, dict) or not isinstance(deadline_body, dict):
                raise CorreiosResponseError("Resposta de preço ou prazo dos Correios inválida")
            return price_body, deadline_body
