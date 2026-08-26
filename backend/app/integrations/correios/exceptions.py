class CorreiosIntegrationError(Exception):
    """Falha esperada e segura da integração com os Correios."""


class CorreiosAuthenticationError(CorreiosIntegrationError):
    pass


class CorreiosResponseError(CorreiosIntegrationError):
    pass
