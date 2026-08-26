# Integração Risso Transportes / Senior TMS

## Arquitetura

A Risso usa a arquitetura compartilhada de transportadoras. O cadastro permanece em `transportadoras`, a configuração em `carrier_integrations` (`integration_type=API`, `adapter_code=risso`) e as credenciais em `carrier_credentials`, criptografadas pelo serviço de credenciais existente. Nenhum endpoint público exclusivo de cotação foi criado.

Fluxo: endpoint universal de cotações → motor concorrente de cotação → registry de adapters → `RissoProvider` → `RissoClient` → Senior TMS → mapper para o resultado universal.

## Configuração e segurança

Configure na tela de Integrações:

- URL base TMS (padrão: `https://platform.senior.com.br/t/senior.com.br/bridge/1.0/rest/tms`);
- URL de autenticação Bridge (padrão: `https://platform.senior.com.br/t/senior.com.br/bridge/1.0/rest`);
- usuário e senha Senior;
- CNPJ remetente, tipo de frete e, somente quando confirmados, códigos de natureza da operação/carga.

A Risso confirmou por e-mail em 25/08/2026 que esta conta não utiliza `client_id`. Senha, token e payload criptografado nunca são retornados ao navegador. O botão **Testar credenciais** executa apenas o login e retorna uma mensagem sanitizada.

## Autenticação e token

O client chama `POST /platform/authentication/actions/login` pela URL Bridge fornecida pela Risso, interpreta `jsonToken` (string JSON) ou um token JSON direto e envia `Authorization: Bearer ...` ao TMS. O token fica somente em memória, é reutilizado até próximo da expiração e é invalidado após um `401`; a chamada é repetida uma única vez com novo login.

## Mapper Freteway → Senior

- CNPJs e CEPs são enviados somente com dígitos;
- `quantidadePeso` recebe o peso total em kg;
- `quantidadeVolumes` recebe a soma das quantidades;
- `quantidadeMetrosCubicos` usa a cubagem universal já calculada em m³;
- `valorMercadoria` recebe o valor da nota como `Decimal` no provider;
- `tipoFrete` vem da configuração da integração;
- o CNPJ destinatário vem da requisição universal de cotação.

Por orientação expressa da Risso, `codigoFilialEmitente`, `icmsIncluso`, `codigoTipoTransporte` e `codigoTipoVeiculo` não são enviados. Natureza da operação e da carga só são enviadas se a Risso confirmar os códigos adequados para a mercadoria.

O fator de peso cubado não é presumido pela Risso. `quantidadePesoCubado` somente é enviado quando um valor explícito estiver disponível/configurado.

## Resposta e estados

Em `SIMULADO`, `valorLiquido` é preferido como preço final; se ausente, usa-se `valorFrete`. Campos financeiros, validade, identificadores, tarifa e percursos ficam em `metadata.cotacaoFrete`.

`ERRO_SIMULACAO` vira erro isolado da transportadora. `PROCESSANDO_SIMULACAO` também retorna um erro controlado de processamento: a documentação consultada não fornece, nesse contrato, uma operação segura de consulta do resultado que justifique polling. Assim não há loop ou espera indefinida e as demais transportadoras continuam sendo retornadas.

O client contém `approve_quote()` para `POST /documentos/actions/aprovaCotacaoFrete`, mas não foi exposta rota pública porque o Freteway ainda não possui fluxo universal de contratação/aprovação.

## Resiliência

Timeout e falhas de conexão são tipados. Um `401` renova o token uma vez. Um `429` faz no máximo duas novas tentativas, respeitando `Retry-After` até quatro segundos ou usando backoff de 1 e 2 segundos. Respostas HTTP/JSON inválidas não expõem corpos ou credenciais.

## Testes

Os testes unitários usam clients HTTP falsos e nunca chamam a Risso. O teste real é ignorado por padrão e exige `RUN_RISSO_INTEGRATION_TESTS=true` e credenciais explícitas no ambiente.

## Referências oficiais

- [Senior Gestão de Transportes TMS](https://documentacao.senior.com.br/gestaodetransportestms/7.0.0/#portal-do-cliente/integra-portal-cliente.htm)
- [Senior X — consumo de APIs](https://api.xplatform.com.br/api-portal/pt-br/tutoriais/consumindo-uma-api)
- [TMS Documentos](https://dev.senior.com.br/api_privada/tms_documentos/)
