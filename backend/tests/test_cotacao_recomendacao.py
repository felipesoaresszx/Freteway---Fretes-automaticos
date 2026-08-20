from app.schemas.cotacao import ResultadoTransportadora
from app.services.cotacao_service import explicar_recomendacao


def proposta(identificador: str, valor: float, prazo: int):
    return ResultadoTransportadora(
        transportadora_id=identificador, transportadora=identificador, status="success",
        valor_frete=valor, prazo_dias=prazo, request_id=f"req-{identificador}",
    )


def test_explicacao_informa_amostra_e_prazo():
    mensagem = explicar_recomendacao([proposta("t1", 100, 3), proposta("t2", 120, 2)], "t1")
    assert mensagem == "Menor valor entre 2 proposta(s) válida(s), com prazo de 3 dia(s)."


def test_explicacao_ausente_sem_resultado_valido():
    assert explicar_recomendacao([], None) is None
