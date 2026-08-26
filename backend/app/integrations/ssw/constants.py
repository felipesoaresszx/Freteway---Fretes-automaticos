from enum import IntEnum

WSDL_URL = "https://ssw.inf.br/ws/sswCotacao/index.php?wsdl"
SERVICE_URL = "https://ssw.inf.br/ws/sswCotacao/index.php"
SOAP_NAMESPACE = "urn:sswinfbr.sswCotacao"


class SSWResultCode(IntEnum):
    AUTH_OR_INTERNAL_ERROR = -2
    CALCULATION_ERROR = -1
    SUCCESS = 0
    SUCCESS_WITH_WARNING = 1
