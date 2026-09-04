from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.cotacao import Endereco, VolumeIn
from app.schemas.transportadora import somente_digitos


class EnderecoSankhya(Endereco):
    cidade: str = ""
    uf: str = Field(default="--", min_length=2, max_length=2)

    @field_validator("cep")
    @classmethod
    def validar_cep(cls, valor: str) -> str:
        normalizado = somente_digitos(valor)
        if len(normalizado) != 8:
            raise ValueError("CEP deve conter 8 digitos")
        return normalizado


class ItemPedidoSankhya(BaseModel):
    quantidade: int = Field(default=1, gt=0)
    peso_kg: float = Field(gt=0)
    comprimento_cm: float | None = Field(default=None, gt=0)
    largura_cm: float | None = Field(default=None, gt=0)
    altura_cm: float | None = Field(default=None, gt=0)
    volume_m3: float | None = Field(default=None, gt=0)
    valor: float | None = Field(default=None, ge=0)

    @model_validator(mode="before")
    @classmethod
    def aceitar_contrato_sankhya(cls, data):
        if isinstance(data, dict):
            data = dict(data)
            for origem, destino in (("peso", "peso_kg"), ("Peso", "peso_kg"),
                                    ("altura", "altura_cm"), ("Altura", "altura_cm"),
                                    ("largura", "largura_cm"), ("Largura", "largura_cm"),
                                    ("comprimento", "comprimento_cm"), ("Comprimento", "comprimento_cm"),
                                    ("Quantidade", "quantidade"), ("VolumeM3", "volume_m3")):
                if origem in data and destino not in data:
                    data[destino] = data[origem]
        return data

    @model_validator(mode="after")
    def validar_volume(self):
        dimensoes = (self.comprimento_cm, self.largura_cm, self.altura_cm)
        if self.volume_m3 is None and any(valor is None for valor in dimensoes):
            raise ValueError("Informe volume_m3 ou comprimento_cm, largura_cm e altura_cm")
        return self

    def para_volume(self) -> VolumeIn:
        if self.volume_m3 is not None:
            lado_cm = (self.volume_m3 * 1_000_000) ** (1 / 3)
            return VolumeIn(quantidade=self.quantidade, peso_kg=self.peso_kg,
                            comprimento_cm=lado_cm, largura_cm=lado_cm, altura_cm=lado_cm)
        return VolumeIn(quantidade=self.quantidade, peso_kg=self.peso_kg,
                        comprimento_cm=self.comprimento_cm, largura_cm=self.largura_cm,
                        altura_cm=self.altura_cm)


class CotacaoSankhyaIn(BaseModel):
    empresa_sankhya_id: str = Field(min_length=1, max_length=80)
    origem: EnderecoSankhya
    destino: EnderecoSankhya
    itens: list[ItemPedidoSankhya] = Field(min_length=1)
    valor_mercadoria: float = Field(gt=0)
    numero_pedido: str = Field(min_length=1, max_length=100)
    transportadoras_ids: list[str] | None = None

    @model_validator(mode="before")
    @classmethod
    def aceitar_nomes_do_contrato(cls, data):
        if not isinstance(data, dict):
            return data
        data = dict(data)
        aliases = {
            "CODEMP": "empresa_sankhya_id", "codemp": "empresa_sankhya_id",
            "NUNOTA": "numero_pedido", "nunota": "numero_pedido",
            "VLRNOTA": "valor_mercadoria", "vlrnota": "valor_mercadoria",
            "VlrNota": "valor_mercadoria",
            "valor_total_mercadoria": "valor_mercadoria", "numero_pedido_sankhya": "numero_pedido",
            "volumes": "itens", "Volumes": "itens",
        }
        for origem, destino in aliases.items():
            if origem in data and destino not in data:
                data[destino] = data[origem]
        for campo in ("empresa_sankhya_id", "numero_pedido"):
            if campo in data and data[campo] is not None:
                data[campo] = str(data[campo])
        cep_origem = data.get("cep_origem") or data.get("CEP_ORIGEM") or data.get("CepOrigem")
        cep_destino = data.get("cep_destino") or data.get("CEP_DESTINO") or data.get("CepDestino")
        if "origem" not in data and cep_origem:
            data["origem"] = {"cep": cep_origem}
        if "destino" not in data and cep_destino:
            data["destino"] = {"cep": cep_destino}
        return data


class MapeamentoSankhyaIn(BaseModel):
    transportadora_id: str
    empresa_sankhya_id: str | None = Field(default=None, min_length=1, max_length=80)
    codigo_parceiro: int = Field(gt=0)
    nome_parceiro: str = Field(min_length=1, max_length=255)
    codigo_servico: str | None = Field(default=None, max_length=100)
    servico: str | None = Field(default=None, max_length=120)
    ativo: bool = True


class MapeamentoSankhyaOut(MapeamentoSankhyaIn):
    id: str
