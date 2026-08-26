"""Adapter oficial da API REST de cotacao da Braspress."""

import httpx

from app.core.url_security import UnsafeUrlError, validate_external_url
from app.integrations.transportadoras.base import ResultadoCotacao, TransportadoraAdapter
from app.models.models import TransportadoraConfiguracaoApi
from app.services.credenciais import descriptografar


class BraspressAdapter(TransportadoraAdapter):
    nome = "Braspress"

    def __init__(self, configuracao: TransportadoraConfiguracaoApi):
        self.configuracao = configuracao

    async def cotar(self, cotacao_payload: dict) -> ResultadoCotacao:
        usuario = self.configuracao.usuario_integracao
        senha = descriptografar(self.configuracao.credencial_criptografada)
        if not self.configuracao.ativa:
            return ResultadoCotacao(status="error", erro_codigo="BRASPRESS_API_INATIVA", erro_mensagem="API Braspress inativa")
        if not usuario or not senha:
            return ResultadoCotacao(status="error", erro_codigo="BRASPRESS_CREDENCIAL_AUSENTE", erro_mensagem="Informe o usuario e a senha da Braspress.")
        if not self.configuracao.documento_devedor:
            return ResultadoCotacao(status="error", erro_codigo="BRASPRESS_REMETENTE_AUSENTE", erro_mensagem="Informe o CNPJ remetente cadastrado na Braspress.")
        if not cotacao_payload.get("documento_destinatario"):
            return ResultadoCotacao(status="error", erro_codigo="BRASPRESS_DESTINATARIO_AUSENTE", erro_mensagem="Informe o CPF/CNPJ do destinatario na cotacao.")

        url = f"{self.configuracao.base_url.rstrip('/')}/{self.configuracao.endpoint_cotacao.lstrip('/')}"
        try:
            validate_external_url(url)
        except UnsafeUrlError as exc:
            return ResultadoCotacao(status="error", erro_codigo="BRASPRESS_URL_INSEGURA", erro_mensagem=str(exc))
        payload = {
            "cnpjRemetente": self.configuracao.documento_devedor,
            "cnpjDestinatario": cotacao_payload["documento_destinatario"],
            "modal": self.configuracao.tipo_transporte or "R",
            "tipoFrete": "1",
            "cepOrigem": cotacao_payload["origem_cep"],
            "cepDestino": cotacao_payload["destino_cep"],
            "vlrMercadoria": cotacao_payload["valor_nf"],
            "peso": cotacao_payload["peso"],
            "volumes": cotacao_payload["quantidade_volumes"],
            "cubagem": [{
                "comprimento": volume["comprimento_cm"] / 100,
                "largura": volume["largura_cm"] / 100,
                "altura": volume["altura_cm"] / 100,
                "volumes": volume["quantidade"],
            } for volume in cotacao_payload["volumes"]],
        }
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
                response = await client.post(url, json=payload, auth=httpx.BasicAuth(usuario, senha), headers={"Accept": "application/json"})
                if response.status_code in {401, 403}:
                    return ResultadoCotacao(status="error", erro_codigo="BRASPRESS_AUTENTICACAO_RECUSADA", erro_mensagem="Login recusado pela Braspress. Confira usuario, senha e liberacao da API.")
                response.raise_for_status()
                body = response.json()
            return ResultadoCotacao(status="success", valor_frete=float(body["totalFrete"]), prazo_dias=int(body["prazo"]), moeda="BRL")
        except httpx.TimeoutException as exc:
            raise TimeoutError from exc
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            return ResultadoCotacao(status="error", erro_codigo="BRASPRESS_API_ERRO", erro_mensagem=f"Falha na API Braspress: {type(exc).__name__}")
