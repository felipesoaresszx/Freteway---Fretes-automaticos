"""Exceções específicas para integração Alfa Transportes.

Seguindo o padrão de outras integrações (Risso, Correios).
"""


class AlfaIntegrationError(Exception):
    """Base segura para falhas esperadas da integração Alfa Transportes."""


class AlfaAuthenticationError(AlfaIntegrationError):
    """Erro de autenticação na API Alfa."""
    pass


class AlfaResponseError(AlfaIntegrationError):
    """Erro na resposta da API Alfa (formato inválido, dados inconsistentes)."""
    pass


class AlfaTimeoutError(AlfaIntegrationError):
    """Timeout na chamadas à API Alfa."""
    pass


class AlfaConnectionError(AlfaIntegrationError):
    """Falha de conexão com a API Alfa."""
    pass


class AlfaRateLimitError(AlfaIntegrationError):
    """Limite de requisições da API Alfa excedido."""
    pass


class AlfaBusinessError(AlfaIntegrationError):
    """Erro de negócio retornado pela Alfa (ex: destino não atendido)."""
    pass


class AlfaNoQuoteError(AlfaBusinessError):
    """Nenhuma cotação disponível para os dados informados."""
    pass


class AlfaInvalidRequestError(AlfaIntegrationError):
    """Requisição inválida enviada à API Alfa."""
    pass
