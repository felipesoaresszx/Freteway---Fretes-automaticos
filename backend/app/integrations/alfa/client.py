"""Cliente HTTP para API da Alfa Transportes.

Implementa chamadas à API de cotação com:
- Timeout configurável
- Retry com backoff para erros transitórios
- Mascaramento de credenciais em logs
- Tratamento de erros normalizados
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, ClassVar
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.core.url_security import validate_external_url
from app.integrations.alfa.exceptions import (
    AlfaAuthenticationError, AlfaConnectionError, AlfaInvalidRequestError, AlfaNoQuoteError, AlfaRateLimitError,
    AlfaResponseError, AlfaTimeoutError,
)
from app.integrations.alfa.schemas import AlfaQuoteRequest, AlfaQuoteResponse

logger = logging.getLogger(__name__)


class AlfaClient:
    """Cliente para API de cotação da Alfa Transportes.
    
    A implementação pública utiliza GET com parâmetros na URL:
    - idr: API Key
    - cliTip: Tipo de cliente (0 ou 1)
    - cepRem: CEP de origem
    - cliCep: CEP de destino
    - cliCnpj: CNPJ do destinatário
    - merVlr: Valor da mercadoria
    - merPeso: Peso
    - merM3: Cubagem
    - modoJson: 1
    """
    
    _last_request_time: ClassVar[dict[tuple[str, str], datetime]] = {}
    
    def __init__(self, credentials: dict[str, str]):
        """Inicializa o cliente com credenciais.
        
        Args:
            credentials: Dicionário com chaves: api_key, base_url, endpoint, login, password
        """
        self.credentials = credentials
        self.base_url = credentials.get("base_url", "https://api.alfatransportes.com.br").rstrip("/")
        self.endpoint = credentials.get("endpoint", "/cotacao/").strip()
        self.api_key = credentials.get("api_key", "")
        self.timeout = get_settings().TIMEOUT_API_INTEGRACAO
        self.retry_attempts = get_settings().INTEGRATION_RETRY_ATTEMPTS
        
    def _get_full_url(self) -> str:
        """Constrói a URL completa para o endpoint de cotação."""
        url = f"{self.base_url}{self.endpoint}"
        return url.rstrip("/") + "/"

    def _masked_url(self, params: dict[str, Any]) -> str:
        """Gera URL com credenciais mascaradas para logging."""
        masked_params = params.copy()
        if "idr" in masked_params:
            masked_params["idr"] = "***MASKED***"
        if "api_key" in masked_params:
            masked_params["api_key"] = "***MASKED***"
        query = urlencode(masked_params)
        base = self._get_full_url()
        return f"{base}?{query}"

    async def validate_credentials(self) -> bool:
        """Valida se as credenciais estão configuradas corretamente.
        
        Para a Alfa, valida se a API Key está presente.
        """
        if not self.api_key:
            return False
        
        # Teste simples: verificar se a API responde
        try:
            await self.quote(AlfaQuoteRequest(
                idr=self.api_key,
                cliTip="1",
                cepRem="07042180",
                cliCep="19500000",
                cliCnpj="24526470000151",
                merVlr=5668.00,
                merPeso=29.0,
                merM3=0.0832
            ))
            return True
        except (AlfaAuthenticationError, AlfaConnectionError, AlfaTimeoutError) as e:
            logger.debug(f"Alfa credential validation failed: {type(e).__name__}")
            return False
        except Exception as e:
            logger.debug(f"Alfa credential validation unexpected error: {type(e).__name__}")
            return False

    async def quote(self, payload: AlfaQuoteRequest) -> AlfaQuoteResponse:
        """Obtém cotação da API Alfa.
        
        Args:
            payload: Objeto AlfaQuoteRequest com todos os parâmetros
            
        Returns:
            AlfaQuoteResponse com a resposta da API
            
        Raises:
            AlfaTimeoutError: Timeout na requisição
            AlfaConnectionError: Falha de conexão
            AlfaAuthenticationError: Credencial inválida
            AlfaRateLimitError: Limite de requisições excedido
            AlfaResponseError: Resposta inválida
            AlfaNoQuoteError: Nenhuma cotação disponível
        """
        url = self._get_full_url()
        validate_external_url(url)
        
        params = payload.model_dump(exclude_none=True)
        
        last_error: Exception | None = None
        
        for attempt in range(self.retry_attempts):
            try:
                async with httpx.AsyncClient(
                    timeout=self.timeout, 
                    follow_redirects=False
                ) as client:
                    response = await client.get(url, params=params)
                    
                    # Tratamento de status codes
                    if response.status_code in (401, 403):
                        raise AlfaAuthenticationError("Credencial Alfa inválida ou acesso negado")
                    
                    if response.status_code == 429:
                        raise AlfaRateLimitError("Limite de requisições da Alfa excedido")
                    
                    if response.status_code == 400:
                        raise AlfaInvalidRequestError("Requisição inválida para API Alfa")
                    
                    if response.status_code == 404:
                        raise AlfaConnectionError("Endpoint da Alfa não encontrado")
                    
                    if response.status_code >= 500:
                        raise AlfaConnectionError(f"API Alfa retornou HTTP {response.status_code}")
                    
                    # Parse da resposta
                    try:
                        body = response.json()
                    except json.JSONDecodeError as exc:
                        raise AlfaResponseError("Resposta da Alfa não é JSON válido") from exc
                    
                    if not isinstance(body, dict):
                        raise AlfaResponseError("Resposta da Alfa tem formato inválido")
                    
                    # Validar estrutura mínima
                    response_obj = AlfaQuoteResponse.model_validate(body)
                    
                    # Verificar se há cotação
                    if not response_obj.cotacao:
                        raise AlfaNoQuoteError("Nenhuma cotação retornada pela Alfa")
                    
                    return response_obj
                    
            except httpx.TimeoutException as exc:
                last_error = AlfaTimeoutError("Timeout na API Alfa")
                logger.warning(
                    "carrier_request carrier=ALFA operation=quote status=timeout "
                    "attempt=%d error=%s",
                    attempt + 1, type(exc).__name__
                )
                if attempt < self.retry_attempts - 1:
                    delay = 2 ** attempt
                    await asyncio.sleep(delay)
                else:
                    raise last_error from exc
                    
            except httpx.RequestError as exc:
                last_error = AlfaConnectionError(f"Falha de conexão com API Alfa: {type(exc).__name__}")
                logger.warning(
                    "carrier_request carrier=ALFA operation=quote status=connection_error "
                    "attempt=%d error=%s",
                    attempt + 1, type(exc).__name__
                )
                if attempt < self.retry_attempts - 1:
                    delay = 2 ** attempt
                    await asyncio.sleep(delay)
                else:
                    raise last_error from exc
        
        # Se chegar aqui, é um erro inesperado
        if last_error:
            raise last_error
        raise AlfaConnectionError("Falha desconhecida ao chamar API Alfa")
