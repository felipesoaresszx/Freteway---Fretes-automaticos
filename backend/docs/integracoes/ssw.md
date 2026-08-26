# Integração SSW Cotação

## Arquitetura

O SSW é implementado como provider compartilhado. Cada transportadora continua na tabela `transportadoras` e possui uma linha em `carrier_integrations` com `integration_type=API` e `adapter_code=ssw`. Configurações não secretas ficam em `configuration`; login e senha ficam juntos em `carrier_credentials`, criptografados pelo mecanismo de credenciais do Freteway.

Fluxo: API FastAPI → `SSWIntegrationService`/motor de cotação → `SSWProvider` → `SSWClient` → SOAP SSW → `SSWParser` → resposta Pydantic normalizada.

O cliente usa SOAP 1.1 RPC diretamente sobre o `httpx`, pois o projeto já utiliza esse cliente assíncrono e o contrato SSW possui somente duas operações simples. Isso evita carregar o WSDL de forma síncrona a cada processo e mantém timeout verdadeiramente assíncrono.

## Segurança

- Nunca envie domínio, login ou senha no payload de uma cotação.
- A senha é criptografada em repouso e nunca aparece nas respostas, logs ou auditoria.
- Configure `CREDENTIAL_ENCRYPTION_KEY` conforme as demais integrações do projeto.
- Logs registram apenas transportadora, provider, domínio, duração e código de retorno.

## Cadastro e validação

Cadastre primeiro a transportadora nas rotas existentes. Depois use `POST /api/v1/transportadoras/{id}/integracoes/ssw` com domínio de três letras, login, senha, CNPJ pagador válido e mercadoria padrão. Atualizações usam `PUT`; senha omitida preserva o segredo atual.

O teste `POST /api/v1/transportadoras/{id}/integracoes/ssw/testar` chama `getMercadoria`. O resultado e horário ficam em `carrier_integrations`. A consulta administrativa nunca devolve senha ou conteúdo criptografado.

## Mercadorias e cotação

`GET /api/v1/transportadoras/{id}/ssw/mercadorias` converte o XML de `getMercadoria` para JSON. `POST /api/v1/transportadoras/{id}/ssw/cotar` aceita CEP formatado ou numérico, normaliza CNPJs e usa `Decimal` para valores. Peso ou volume deve ser maior que zero.

O parser interpreta os códigos oficiais:

- `-2`: autenticação, domínio ou erro interno;
- `-1`: erro impeditivo de cálculo;
- `0`: sucesso;
- `1`: sucesso com alerta (não é falha).

Tags financeiras ausentes assumem zero. XML inválido gera erro controlado, sem retornar o XML bruto.

## Rotas

- `GET /api/v1/transportadoras/ssw`
- `POST|PUT|GET /api/v1/transportadoras/{id}/integracoes/ssw`
- `POST /api/v1/transportadoras/{id}/integracoes/ssw/testar`
- `GET /api/v1/transportadoras/{id}/ssw/mercadorias`
- `POST /api/v1/transportadoras/{id}/ssw/cotar`
- `POST /api/v1/transportadoras/importacao/ssw`

Todas aparecem no Swagger sob **Integrações SSW**.

## Migração e execução

```powershell
cd backend
alembic upgrade head
python -m pytest -q tests/test_ssw_parser.py tests/test_ssw_provider.py
```

Testes reais são ignorados por padrão. Para habilitá-los, defina `SSW_TEST_DOMAIN`, `SSW_TEST_LOGIN`, `SSW_TEST_PASSWORD` e `SSW_TEST_PAYER_CNPJ`, depois execute `python -m pytest -q tests/integration/ssw`.

## Troubleshooting

- `401`: credenciais ou domínio recusados pelo SSW.
- `422`: configuração/carga inválida ou cálculo recusado.
- `502`: falha HTTP, SOAP, DNS, SSL ou XML inválido.
- `504`: timeout do SSW.
- Código `1`: confira `alerta=true` e `mensagem`; o valor continua válido.

Contrato oficial: <https://ssw.inf.br/ws/sswCotacao/help.html>. WSDL: <https://ssw.inf.br/ws/sswCotacao/index.php?wsdl>.
