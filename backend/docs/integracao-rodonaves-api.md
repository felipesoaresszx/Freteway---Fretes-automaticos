# Rodonaves: cotação REST

O cadastro RTE Rodonaves usa o adapter `RodonavesAdapter` quando o método de
cálculo é `api`. Não há dependência de automação do Portal do Cliente.

## Configuração

Aplicar `alembic upgrade head` para incluir os campos de contato. Em Integrações,
selecionar API e abrir Configurar API. Informar usuário e senha **liberados para
API**, CPF/CNPJ do cliente vinculado ao usuário, nome e telefone do contato.
A senha usa a criptografia existente e nunca retorna no response.

O utilitário `python -m scripts.configure_rodonaves` recebe os valores por
variáveis de ambiente `RODONAVES_USERNAME`, `RODONAVES_PASSWORD`,
`RODONAVES_DOCUMENT`, `RODONAVES_CONTACT_NAME`, `RODONAVES_CONTACT_PHONE`.
Localiza exatamente um cadastro existente e só ativa após obter token e
verificar o contato. Não criar arquivos com senhas nem versionar segredos.

## Contrato

- Autenticação: POST `/token`, form-urlencoded, `auth_type=DEV`,
  `grant_type=password`, `username`, `password`. Não enviar `companyId=1`:
  esse parâmetro impõe um vínculo de empresa que pode recusar um acesso válido.
- Cada serviço recebe seu próprio token. Tokens são obtidos por cotação,
  evitando uso de token expirado.
- Cidades: GET `https://dne-api.rte.com.br/api/cities/byzipcode?zipCode=CEP`.
  Usar `Id` como identificador interno; não usar o código IBGE.
- Cotação: POST `https://quotation-apigateway.rte.com.br/api/v1/gera-cotacao`.
  Peso real total, peso unitário e dimensões em centímetros de cada linha,
  quantidade de volumes e valor da nota. CPF/CNPJ do destinatário é obrigatório.
  Ler `FreightValue` e guardar `ProtocolId`.
- Prazo: POST `https://01wapi.rte.com.br/api/v1/prazo-entrega`, nomes de cidades
  sem acentos em maiúsculas e UFs. Ler `DeliveryTime`. Se este serviço falhar,
  preservar o frete com prazo ausente e aviso. Limitar essa etapa a cinco segundos.

`gera-cotacao` registra cotação no TMS; não há retry automático desse POST.
Erros não expõem senha, tokens, corpo HTTP ou dados pessoais da resposta.
Destinatários ainda não cadastrados na Rodonaves podem ser recusados; este
adapter não cadastra clientes automaticamente.

## Validação em 27/10/2026

O novo acesso fornecido foi aceito pelo endpoint de cotação (HTTP 200 com
`access_token`) sem `companyId`. Com `companyId=1`, os três serviços recusaram
a autenticação com `invalid_grant`, informando ausência de vínculo à empresa
RODONAVES. O adapter foi corrigido para não enviar esse parâmetro, conforme
o formulário documentado. Os 11 testes do adapter passaram, incluindo a
regressão do formulário de autenticação. Nenhuma cotação foi gerada no teste.

### Ativação em produção

Em 27/10/2026, após autorização do usuário, o banco foi protegido pelo backup
`backups/freteway_2026-10-27_143637.dump`. A correção foi aplicada ao checkout
do servidor e aos containers backend e worker, seguidos de reinício. A
reconstrução completa das imagens foi interrompida por consumo de recursos;
as imagens Docker não foram republicadas nessa intervenção. A correção e o
teste de regressão foram preparados para incorporação ao Git, preservando
o ajuste nos próximos builds e deploys.

O cadastro RTE RODONAVES foi configurado com usuário `LAIDOM`, senha
criptografada no banco, CNPJ MODIAL São Paulo `04.917.818/0001-24` e contato
Felipe fornecido pelo usuário. Transportadora e API ativas, método `api`,
status da integração `ativo` e ambiente `producao`. A tabela existente
`Tabela Rodonaves` também foi confirmada como `active` e foi preservada.

Validação final pelo adapter instalado no backend: autenticação aceita em
cotação, cidades e prazo; consulta de cidade por CEP aceita; `/health` e
`/api/v1/health/ready` com HTTP 200. Não foi criada cotação no TMS. A validação
não comprova o vínculo comercial dos demais CNPJs nem um valor real de frete.

## Validação anterior em 13/10/2026

O acesso fornecido para o Portal do Cliente foi recusado pelas APIs de cotação,
cidades e prazo com HTTP 400 / `invalid_grant`. Também foi verificado o CNPJ com
e sem pontuação e `companyId=1`. Não foi obtido token nem gerada cotação real.
É necessário confirmar/liberar as credenciais de API com a Rodonaves.

O banco local estava inacessível e o Docker Desktop desligado; a migração e a
configuração do cadastro não foram executadas. Nenhuma senha foi salva em
arquivo do projeto. O utilitário permite concluir a configuração no ambiente
que contém o banco, após receber acesso válido e os dados do contato.

Fontes: [cotação](https://dev.rodonaves.com.br/reference/apiv1gera-cotacaopost-1),
[token](https://dev.rodonaves.com.br/reference/post_token),
[cidades](https://dev.rodonaves.com.br/reference/apicitiesbyzipcodeget),
[prazo](https://dev.rodonaves.com.br/reference/apideliverytimeget-1).
