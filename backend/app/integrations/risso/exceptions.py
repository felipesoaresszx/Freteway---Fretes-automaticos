class RissoIntegrationError(Exception):
    """Base segura para falhas esperadas da integração Risso/Senior."""


class RissoAuthenticationError(RissoIntegrationError):
    pass


class RissoResponseError(RissoIntegrationError):
    pass


class RissoTimeoutError(RissoIntegrationError):
    pass


class RissoConnectionError(RissoIntegrationError):
    pass


class RissoRateLimitError(RissoIntegrationError):
    pass


class RissoBusinessError(RissoIntegrationError):
    pass


class RissoProcessingError(RissoBusinessError):
    """A Senior aceitou a solicitação, mas ainda não produziu o resultado."""
