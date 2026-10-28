"""Rispa via FreteCalc: gateway GET/XML compatível com a Tray."""

import math
import re
from decimal import Decimal
from xml.etree import ElementTree as ET

import httpx

from app.integrations.transportadoras.base import ResultadoCotacao, TransportadoraAdapter
from app.services.credenciais import descriptografar

RISPA_DEFAULTS = {
    "base_url": "https://api.fretecalc.com",
    "endpoint_cotacao": "/v1/frete",
    "metodo_http": "GET",
    "tipo_autenticacao": "query_param",
    "nome_header": "token",
    "campo_valor": "valor",
    "campo_prazo": "prazo_max",
}


def is_rispa(nome: str) -> bool:
    return bool(re.match(r"^rispar?(?:\s|$)", nome.strip(), re.IGNORECASE))


def tray_params(payload: dict) -> dict:
    volumes = payload["volumes"]
    quantidade = sum(int(v["quantidade"]) for v in volumes)
    if quantidade <= 0:
        raise ValueError("Informe os volumes da carga")
    valor_unitario = Decimal(str(payload["valor_nf"])) / quantidade
    produtos = []
    for codigo, volume in enumerate(volumes, 1):
        c, l, a = (Decimal(str(volume[k])) / 100 for k in
                   ("comprimento_cm", "largura_cm", "altura_cm"))
        produtos.append(";".join(str(v) for v in (
            c, l, a, c * l * a, volume["quantidade"], volume["peso_kg"],
            codigo, valor_unitario,
        )))
    return {
        "cep": re.sub(r"\D", "", payload["origem_cep"]),
        "cep_destino": re.sub(r"\D", "", payload["destino_cep"]),
        "envio": "1", "num_ped": "1", "prods": "/".join(produtos),
    }


class RispaAdapter(TransportadoraAdapter):
    nome = "RISPA TRANSPORTES"

    def __init__(self, configuracao):
        self.configuracao = configuracao

    async def cotar(self, cotacao_payload: dict) -> ResultadoCotacao:
        if not self.configuracao.ativa:
            return ResultadoCotacao(status="error", erro_codigo="API_INATIVA",
                                    erro_mensagem="Configuração da Rispa inativa")
        try:
            token = descriptografar(self.configuracao.credencial_criptografada)
            if not token:
                raise ValueError("Informe o token da Rispa")
            params = tray_params(cotacao_payload)
            params["token"] = token
            async with httpx.AsyncClient(timeout=15, follow_redirects=False) as cliente:
                resposta = await cliente.get("https://api.fretecalc.com/v1/frete",
                                             params=params, headers={"Accept": "application/xml"})
            resposta.raise_for_status()
            if "<!DOCTYPE" in resposta.text.upper() or "<!ENTITY" in resposta.text.upper():
                raise ValueError("XML inválido")
            root = ET.fromstring(resposta.content)
            resultado = next((r for r in root.findall("resultado")
                              if is_rispa(r.findtext("servico", ""))), None)
            if resultado is None:
                return ResultadoCotacao(status="error", erro_codigo="RISPA_SEM_COTACAO",
                                        erro_mensagem="A Rispa não retornou cotação para esta carga e destino")
            valor = float(resultado.findtext("valor", ""))
            prazo = int(resultado.findtext("prazo_max", ""))
            if not math.isfinite(valor) or valor < 0 or prazo < 0:
                raise ValueError("Valor ou prazo inválido")
            return ResultadoCotacao(status="success", valor_frete=valor, prazo_dias=prazo,
                                    detalhamento={"servico": resultado.findtext("servico"),
                                                  "peso_calculado_kg": resultado.findtext("peso"),
                                                  "transporte": resultado.findtext("transporte")})
        except httpx.HTTPError:
            # URLs de exceções HTTP podem conter o token na query string.
            return ResultadoCotacao(status="error", erro_codigo="ERRO_API_TRANSPORTADORA",
                                    erro_mensagem="Falha na consulta à API da Rispa")
        except (ValueError, KeyError, TypeError, ET.ParseError):
            return ResultadoCotacao(status="error", erro_codigo="RISPA_DADOS_INVALIDOS",
                                    erro_mensagem="Confira a credencial e os dados da carga; resposta Rispa inválida")
