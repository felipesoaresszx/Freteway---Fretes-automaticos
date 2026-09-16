"""Provider de cotação para Alfa Transportes.

Implementa a interface CarrierAdapter para integração com a API Alfa.
"""

import json
import logging
from time import perf_counter
from typing import Any

import httpx

from app.integrations.alfa.client import AlfaClient
from app.integrations.alfa.exceptions import (
    AlfaAuthenticationError, AlfaConnectionError, AlfaIntegrationError,
    AlfaNoQuoteError, AlfaResponseError, AlfaTimeoutError,
)
from app.integrations.alfa.mapper import to_alfa_request, to_freteway_result
from app.integrations.alfa.schemas import AlfaCredentials, AlfaQuoteResponse
from app.integrations.transportadoras.carrier_base import CarrierAdapter
from app.schemas.carrier import FreightQuoteRequest, FreightQuoteResult

logger = logging.getLogger(__name__)


class AlfaProvider(CarrierAdapter):
    """Provider de cotação para Alfa Transportes.
    
    Segue o padrão CarrierAdapter:
    - validate_credentials: valida API Key
    - get_services: retorna lista de serviços
    - quote: obtém cotação e converte para FreightQuoteResult
    """

    async def validate_credentials(self, credentials: dict[str, str]) -> bool:
        """Valida se as credenciais da Alfa estão configuradas corretamente.
        
        Args:
            credentials: Dicionário com api_key, base_url, endpoint, etc.
            
        Returns:
            True se credenciais são válidas, False caso contrário
        """
        try:
            validated = AlfaCredentials.model_validate(credentials)
            return await AlfaClient(validated.model_dump(mode="json")).validate_credentials()
        except (AlfaIntegrationError, httpx.HTTPError, ValueError, json.JSONDecodeError):
            return False

    async def get_services(self, credentials: dict[str, str]) -> list[dict[str, str]]:
        """Obtém lista de serviços disponíveis da Alfa.
        
        Para a Alfa, retornamos um único serviço padrão.
        
        Args:
            credentials: Credenciais da transportadora
            
        Returns:
            Lista de serviços (no momento, apenas um serviço genérico)
        """
        return [{"code": "alfa-standard", "name": "Alfa Transportes"}]

    async def quote(self, request: FreightQuoteRequest, credentials: dict[str, str]) -> list[FreightQuoteResult]:
        """Obtém cotação da API Alfa e converte para formato canônico.
        
        Args:
            request: FreightQuoteRequest com dados do frete
            credentials: Credenciais da transportadora
            
        Returns:
            Lista com um FreightQuoteResult (Alfa oferece uma cotação por request)
            
        Raises:
            AlfaAuthenticationError: Credencial inválida
            AlfaConnectionError: Falha de conexão
            AlfaTimeoutError: Timeout
            AlfaResponseError: Resposta inválida
            AlfaNoQuoteError: Nenhuma cotação disponível
        """
        started = perf_counter()
        
        try:
            # Validar credenciais
            validated = AlfaCredentials.model_validate(credentials)
            creds_dict = validated.model_dump(mode="json")
            
            # Converter request para formato Alfa
            alfa_request = to_alfa_request(request, creds_dict)
            
            # Chamar API Alfa
            client = AlfaClient(creds_dict)
            response = await client.quote(alfa_request)
            
            # Converter resposta para formato canônico
            result = to_freteway_result(response, raw_response=None)
            
            logger.info(
                "carrier_quote carrier=ALFA operation=quote status=success "
                "duration_ms=%d freight_value=%s delivery_days=%s",
                int((perf_counter() - started) * 1000),
                str(result.price),
                result.delivery_days
            )
            
            return [result]
            
        except AlfaAuthenticationError as exc:
            logger.warning(
                "carrier_quote carrier=ALFA operation=quote status=auth_error "
                "error=%s duration_ms=%d",
                str(exc),
                int((perf_counter() - started) * 1000)
            )
            raise
            
        except AlfaConnectionError as exc:
            logger.warning(
                "carrier_quote carrier=ALFA operation=quote status=connection_error "
                "error=%s duration_ms=%d",
                str(exc),
                int((perf_counter() - started) * 1000)
            )
            raise
            
        except AlfaTimeoutError as exc:
            logger.warning(
                "carrier_quote carrier=ALFA operation=quote status=timeout "
                "error=%s duration_ms=%d",
                str(exc),
                int((perf_counter() - started) * 1000)
            )
            raise
            
        except AlfaNoQuoteError as exc:
            logger.warning(
                "carrier_quote carrier=ALFA operation=quote status=no_quote "
                "error=%s duration_ms=%d",
                str(exc),
                int((perf_counter() - started) * 1000)
            )
            raise
            
        except (AlfaResponseError, ValueError) as exc:
            logger.warning(
                "carrier_quote carrier=ALFA operation=quote status=invalid_response "
                "error=%s duration_ms=%d",
                str(exc),
                int((perf_counter() - started) * 1000)
            )
            raise
            
        except Exception as exc:
            logger.error(
                "carrier_quote carrier=ALFA operation=quote status=unknown_error "
                "error_type=%s error=%s duration_ms=%d",
                type(exc).__name__,
                str(exc),
                int((perf_counter() - started) * 1000)
            )
            raise
