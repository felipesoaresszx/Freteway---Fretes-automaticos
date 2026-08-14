from pydantic import BaseModel, Field, model_validator

from app.schemas.cotacao import Endereco, VolumeIn


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
        if isinstance(data, dict) and "peso" in data and "peso_kg" not in data:
            data = {**data, "peso_kg": data["peso"]}
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
            return VolumeIn(
                quantidade=self.quantidade, peso_kg=self.peso_kg,
                comprimento_cm=lado_cm, largura_cm=lado_cm, altura_cm=lado_cm,
            )
        return VolumeIn(
            quantidade=self.quantidade, peso_kg=self.peso_kg,
            comprimento_cm=self.comprimento_cm, largura_cm=self.largura_cm,
            altura_cm=self.altura_cm,
        )


class CotacaoSankhyaIn(BaseModel):
    empresa_sankhya_id: str | None = Field(default=None, min_length=1, max_length=80)
    origem: Endereco
    destino: Endereco
    itens: list[ItemPedidoSankhya] = Field(min_length=1)
    valor_mercadoria: float = Field(gt=0)
    numero_pedido: str | None = Field(default=None, max_length=100)
    tipo_entrega: str | None = Field(default=None, max_length=120)
    tipo_transporte: str | None = Field(default=None, max_length=120)
    transportadoras_ids: list[str] | None = None
    modo: str | None = Field(default=None, pattern="^(anexar|substituir)$")

    @model_validator(mode="before")
    @classmethod
    def aceitar_nomes_do_contrato(cls, data):
        if not isinstance(data, dict):
            return data
        data = dict(data)
        if "numero_pedido_sankhya" in data and "numero_pedido" not in data:
            data["numero_pedido"] = data["numero_pedido_sankhya"]
        if "valor_total_mercadoria" in data and "valor_mercadoria" not in data:
            data["valor_mercadoria"] = data["valor_total_mercadoria"]
        return data


class LinhaCotacaoSankhya(BaseModel):
    id_container: int
    codigo_parceiro_transportadora: int | None = None
    nome_parceiro: str | None = None
    prazo_entrega: int | None = None
    valor_cotacao: float | None = None
    aprovado: bool | None = None
    codigo_servico: str | None = None
    servico: str | None = None
    transportadora: str
    erro: str | None = None
    transportadora_freteway_id: str
    status: str
    request_id: str


class CotacaoSankhyaOut(BaseModel):
    numero_pedido: str | None = None
    status: str
    linhas: list[LinhaCotacaoSankhya]
    cotacoes_geradas: int = 0
    cotacoes_com_erro: int = 0
    tempo_resposta_ms: int = 0


class MapeamentoSankhyaIn(BaseModel):
    transportadora_id: str
    codigo_parceiro: int = Field(gt=0)
    nome_parceiro: str = Field(min_length=1, max_length=255)
    codigo_servico: str | None = Field(default=None, max_length=100)
    servico: str | None = Field(default=None, max_length=120)
    ativo: bool = True


class MapeamentoSankhyaOut(MapeamentoSankhyaIn):
    id: str
