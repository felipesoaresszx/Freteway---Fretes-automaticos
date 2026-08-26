class SSWException(Exception):
    """Base segura para falhas do provider SSW."""


class SSWAuthenticationError(SSWException): pass
class SSWCalculationError(SSWException): pass
class SSWConnectionError(SSWException): pass
class SSWTimeoutError(SSWException): pass
class SSWInvalidResponseError(SSWException): pass
