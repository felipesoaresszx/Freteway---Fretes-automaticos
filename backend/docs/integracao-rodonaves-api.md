# Rodonaves: cotação REST

O cadastro RTE Rodonaves usa o adapter `RodonavesAdapter` quando o método de
cálculo é `api`. Não há dependência de automação do Portal do Cliente.

## Atualização em 30/10/2026: simulação

O adapter utiliza POST `/api/v1/simula-cotacao`. Não exige nem envia
CPF/CNPJ do destinatário ou dados de contato. Mantém o CPF/CNPJ do
cliente solicitante, CEPs, cidades, peso, valor da nota e volumes.
O resultado inclui aviso de valor aproximado, sujeito a alteração na
cotação definitiva. O campo de valor configurado é `FreightValue`;
o parser também aceita `Value`. O fallback de prazo foi preservado.
Validação: 35 testes do adapter com HTTP simulado; sem consulta real.
[Contrato oficial](https://dev.rodonaves.com.br/v2.0/reference/apiv1simula-cotacaopost-1).

As seções abaixo registram a integração anterior com `gera-cotacao`
e suas validações históricas.

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
  A resposta real de produção usa `Value`, `ProtocolNumber` e `DeliveryTime`.
  O adapter também aceita `FreightValue` e `ProtocolId` do contrato antigo.
  Priorizar o prazo da própria cotação quando válido e disponível.
- Prazo: POST `https://01wapi.rte.com.br/api/v1/prazo-entrega`, nomes de cidades
  sem acentos em maiúsculas e UFs. Ler `DeliveryTime`. Se este serviço falhar,
  Consultar somente quando a cotação não informar prazo válido/disponível.
  Se falhar, preservar o frete com prazo ausente e aviso. Limitar essa etapa
  a cinco segundos.

`gera-cotacao` registra cotação no TMS; não há retry automático desse POST.
Erros não expõem senha, tokens, corpo HTTP ou dados pessoais da resposta.
Destinatários ainda não cadastrados na Rodonaves podem ser recusados; este
adapter não cadastra clientes automaticamente.

Recusas conhecidas de destinatário e remetente são traduzidas para códigos
e mensagens específicos, sem repassar o corpo HTTP externo. A recusa de
destinatário não prova ausência de cadastro no portal: se os mesmos dados
funcionarem no portal, solicitar à Rodonaves a verificação do cadastro na API.

## Resposta real e correção do parser em 27/10/2026

O teste com origem 07042180, destino 85865310, remetente MODIAL São Paulo,
destinatário 07.671.011/0001-42, mercadoria R$ 9.900,00 e dois volumes (12 kg,
41 x 44 x 34 cm; 16 kg, 43 x 56 x 40 cm) retornou HTTP 200. Resposta real:
`Value=236.71`, `ProtocolNumber=225047304`, `DeliveryTime=4`, validade
11/11/2026. O parser anterior esperava apenas os campos do contrato antigo e
trataria esse sucesso como erro. A correção cobre ambos os formatos e evita
uma consulta adicional de prazo quando a cotação já trouxer um prazo válido.

Testes cobrem a resposta real, compatibilidade antiga, prazo zero, fallback de
prazo, preservação de preço quando o prazo falha, recusas específicas e
respostas inválidas sem repetição do POST de cotação. A divergência cadastral
dos outros destinatários permanece uma recusa da transportadora; este ajuste
não cadastra clientes nem substitui a resposta da API por preço do portal.

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
