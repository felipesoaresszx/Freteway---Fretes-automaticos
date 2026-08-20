from app.schemas.transportadora import ConfiguracaoApiUpdate
from app.services.credenciais import criptografar, descriptografar


def test_credencial_e_criptografada():
    segredo = "token-super-secreto"
    cifrado = criptografar(segredo)
    assert segredo not in cifrado
    assert descriptografar(cifrado) == segredo


def test_configuracao_api_normaliza_metodo_e_auth():
    dados = ConfiguracaoApiUpdate(
        base_url="https://api.exemplo.com", metodo_http="post",
        tipo_autenticacao="BEARER", credencial="abc",
    )
    assert dados.metodo_http == "POST"
    assert dados.tipo_autenticacao == "bearer"
