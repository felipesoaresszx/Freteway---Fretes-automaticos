# Guia de apresentacao do codigo - FreteWay

Este documento explica as partes essenciais do projeto em uma ordem adequada para apresentacao. A ideia nao e comentar cada linha, mas mostrar como as camadas se conectam e onde estao as principais regras de negocio.

## 1. Resumo do projeto

O FreteWay e um sistema web para criar cotacoes de frete, consultar varias transportadoras, comparar valores e prazos e administrar tabelas tarifarias.

O problema resolvido e a centralizacao de um processo que normalmente exigiria consultas separadas. O usuario informa os dados da carga uma vez, o sistema consulta as opcoes disponiveis e apresenta os resultados em um unico lugar.

Frase sugerida para abrir a apresentacao:

> O FreteWay centraliza a cotacao de fretes. A aplicacao recebe os dados da carga, calcula sua cubagem, consulta diferentes transportadoras e indica a opcao de menor preco, mantendo tambem o prazo e os erros individuais de cada consulta.

## 2. Arquitetura geral

O sistema possui tres partes principais:

```text
Usuario
   |
   v
Frontend React/TypeScript
   |
   | HTTP/JSON
   v
API FastAPI/Python
   |
   +--> regras de negocio e integracoes
   |
   v
PostgreSQL
```

### Frontend

O frontend fica em `frontend/src`. Ele mostra as telas, valida e organiza os dados digitados, chama a API e atualiza a interface conforme as respostas chegam.

Tecnologias principais: React, TypeScript, React Router, TanStack Query, Axios e Tailwind CSS.

### Backend

O backend fica em `backend/app`. Ele recebe as requisicoes, valida os dados, verifica usuario e permissoes, executa as regras de negocio e persiste os resultados.

Tecnologias principais: FastAPI, Pydantic, SQLAlchemy assincrono e JWT.

### Banco de dados

O PostgreSQL armazena usuarios, permissoes, transportadoras, cotacoes, volumes, resultados, tabelas de frete, configuracoes e auditoria. O Alembic, em `backend/alembic`, controla as alteracoes de estrutura do banco por migrations.

## 3. Como o frontend e iniciado

### `frontend/src/main.tsx`

E o ponto de entrada do frontend. O `createRoot` conecta o React ao elemento `root` do HTML e renderiza o componente `App`.

O `StrictMode` ajuda a detectar comportamentos problemáticos durante o desenvolvimento.

### `frontend/src/App.tsx`

Este arquivo instala os provedores globais:

- `QueryClientProvider`: gerencia cache, carregamento e atualizacao dos dados da API;
- `CompanyProvider`: fornece os dados e o tema da empresa atual;
- `BrowserRouter`: habilita a navegacao por URL sem recarregar a pagina.

O TanStack Query esta configurado para tentar novamente uma consulta com falha uma vez e para nao refazer todas as consultas quando a janela recebe foco.

### `frontend/src/routes/index.tsx`

Define as rotas da aplicacao. `/login` e publica. As demais telas ficam dentro de `ProtectedRoute` e compartilham o `AppLayout`.

As rotas principais sao:

- `/dashboard`: indicadores do sistema;
- `/cotacoes`: historico de cotacoes;
- `/cotacoes/nova`: formulario de nova cotacao;
- `/transportadoras`: cadastro e tabelas das transportadoras;
- `/integracoes`: configuracoes de integracao;
- `/configuracoes`: administracao protegida por permissao.

`ProtectedRoute.tsx` exige empresa identificada e usuario autenticado. `PermissionRoute.tsx` faz uma verificacao adicional de permissao para telas administrativas.

## 4. Comunicacao do frontend com a API

### `frontend/src/api/client.ts`

Cria uma instancia central do Axios. O endereco base vem de `VITE_API_URL`, o tempo limite e de 20 segundos e `withCredentials: true` permite enviar o cookie de autenticacao.

O interceptor transforma falhas tecnicas em mensagens compreensiveis. Assim, componentes nao precisam repetir o mesmo tratamento de erro.

### `frontend/src/services/cotacaoService.ts`

Concentra as chamadas HTTP relacionadas a cotacoes:

- `listar`: busca o historico com filtros;
- `criar`: envia uma nova cotacao;
- `obter`: consulta o estado e os resultados;
- `selecionar`: registra a transportadora escolhida.

Essa camada separa detalhes HTTP da interface visual.

### `frontend/src/hooks/useCotacao.ts`

Coordena o estado da cotacao usando TanStack Query:

1. `useMutation` envia a nova cotacao;
2. o ID retornado e guardado no estado;
3. `useQuery` consulta esse ID a cada 1,5 segundo enquanto o status for `processing`;
4. o polling para automaticamente quando o processamento termina;
5. ao selecionar uma transportadora, o cache e invalidado para buscar o estado atualizado.

Ponto importante para explicar: o processamento pode demorar porque depende de servicos externos. Por isso, a interface nao fica presa esperando uma unica requisicao longa.

### `frontend/src/pages/NovaCotacao/NovaCotacao.tsx`

E a principal tela do fluxo. Ela controla origem, destino, valor da nota, volumes e transportadoras selecionadas.

A cubagem e o peso total sao calculados na tela para dar retorno imediato ao usuario. O formulario permite varios volumes e consulta o CEP para preencher cidade e UF. Ao confirmar, `handleCalcular` monta o objeto esperado pela API e chama o hook `useCotacao`.

Quando os resultados chegam, a tela diferencia sucesso, erro e timeout, destaca a melhor opcao e permite selecionar outra proposta valida.

## 5. Como a API e iniciada

### `backend/app/main.py`

E o ponto de entrada do FastAPI. Ele:

- cria a aplicacao;
- desabilita Swagger e ReDoc em producao;
- configura CORS e hosts confiaveis;
- identifica a empresa de cada requisicao;
- protege operacoes feitas por cookie contra origens indevidas;
- registra auditoria para alteracoes bem-sucedidas;
- adiciona cabecalhos de seguranca;
- conecta as rotas da API;
- disponibiliza o health check em `/health`.

Em producao, a inicializacao falha se o segredo JWT, a criptografia de credenciais ou a seguranca do cookie estiverem configurados de forma insegura.

### `backend/app/api/v1/router.py`

Funciona como indice dos endpoints. Ele agrupa autenticacao, dashboard, transportadoras, tabelas de frete, cotacoes, configuracoes, integracoes, enderecos, empresas e administracao de tenants sob o prefixo `/api/v1`.

## 6. Contratos e validacao dos dados

### `backend/app/schemas/cotacao.py`

Os schemas Pydantic definem exatamente o que entra e sai da API.

Os principais sao:

- `Endereco`: CEP, cidade e UF;
- `VolumeIn`: quantidade, dimensoes e peso, todos positivos;
- `CotacaoCreate`: origem, destino, nota fiscal, peso, volumes e transportadoras;
- `ResultadoTransportadora`: valor, prazo, status, erro e identificador da requisicao;
- `CotacaoOut`: estado geral, cubagem, melhor opcao e resultados.

Essa validacao impede que dados incompletos ou valores negativos avancem para a regra de negocio.

## 7. Fluxo completo de uma cotacao

O fluxo principal passa por estes arquivos:

```text
NovaCotacao.tsx
      |
      v
useCotacao.ts -> cotacaoService.ts -> POST /cotacoes
                                      |
                                      v
                            endpoints/cotacoes.py
                                      |
                         salva status processing
                                      |
                                      v
                         cotacao_service.py
                    / tabela  / API  / erro controlado
                                      |
                                      v
                       salva resultados no banco
                                      |
                                      v
                frontend faz polling em GET /cotacoes/{id}
```

### Etapa 1: recebimento

Em `backend/app/api/v1/endpoints/cotacoes.py`, `criar_cotacao` recebe um `CotacaoCreate`. A dependencia `require_permission("cotacoes.manage")` bloqueia usuarios sem permissao.

### Etapa 2: calculos confiaveis

O backend recalcula cubagem e peso. Isso e importante porque valores calculados no navegador podem ser alterados pelo cliente.

A cubagem, implementada em `backend/app/services/cubagem.py`, usa:

```text
cubagem em m3 = comprimento_cm * largura_cm * altura_cm * quantidade / 1.000.000
```

O peso total multiplica o peso unitario de cada volume por sua quantidade.

### Etapa 3: persistencia inicial

A cotacao e os volumes sao gravados no banco com status `processing`. A API responde imediatamente com HTTP 201 e agenda o processamento em segundo plano.

### Etapa 4: consulta das transportadoras

`backend/app/services/cotacao_service.py` escolhe o adapter conforme `metodo_calculo` da transportadora:

- `tabela_propria`: procura uma tabela ativa e dentro da vigencia;
- `api`: usa a configuracao de API cadastrada;
- metodo sem adapter: devolve erro controlado;
- no modo sem banco usado por testes, pode usar adapters simulados.

As chamadas de API sao reunidas com `asyncio.gather`, permitindo consultas concorrentes. Cada chamada possui timeout. Uma transportadora com falha nao impede as demais de responderem.

### Etapa 5: resultado geral

`determinar_melhor_opcao` filtra apenas resultados com sucesso e usa `min` para escolher o menor `valor_frete`.

`determinar_status_geral` retorna:

- `completed`: todas responderam com sucesso;
- `completed_with_errors`: pelo menos uma respondeu e outra falhou;
- `failed`: nenhuma proposta valida foi obtida.

### Etapa 6: atualizacao da tela

O frontend consulta `GET /cotacoes/{id}` enquanto o status for `processing`. Quando o status final chega, o polling para e a tela exibe as propostas.

O usuario pode aceitar a sugestao automatica ou selecionar outra resposta bem-sucedida em `POST /cotacoes/{id}/selecionar`.

## 8. Padrao Adapter nas transportadoras

Os adapters ficam em `backend/app/integrations/transportadoras`.

O objetivo do padrao Adapter e oferecer uma interface comum mesmo que cada transportadora tenha uma forma diferente de calcular o frete. Para o restante do sistema, todas devolvem uma resposta padronizada com status, valor, prazo ou erro.

Implementacoes importantes:

- `tabela_frete.py`: calcula usando dados importados de uma tabela propria;
- `api_generica.py`: faz requisicoes HTTP com campos configuraveis;
- `mock/client.py`: simula respostas para desenvolvimento e testes;
- `base.py`: define o contrato comum das integracoes.

Vantagem para apresentar: uma nova transportadora pode ser adicionada sem reescrever a tela ou o contrato da cotacao.

## 9. Importacao de tabelas de frete

### `backend/app/api/v1/endpoints/tabelas_frete.py`

Controla o ciclo de vida completo:

```text
draft -> upload -> analise -> review -> approved -> active
                                           \-> cancelled
```

Uma tabela e criada como rascunho, recebe um documento, passa por extracao e revisao, e aprovada e finalmente ativada. A ativacao exige uma tabela aprovada.

### Servicos em `backend/app/services/tabela_frete`

- `documentos.py`: valida nome, tipo, tamanho e conteudo do arquivo antes de armazena-lo;
- `analise.py`: extrai os dados e gera um diagnostico de confianca;
- `extracao_generica.py`: trata PDF, DOCX e imagens, incluindo OCR quando disponivel;
- `uf_zona_excel.py` e `rodonaves_excel.py`: interpretam modelos especificos de planilha;
- `calculo_uf_zona.py` e `calculo_rodonaves.py`: aplicam as regras tarifarias extraidas;
- `tabela_import.py`: normaliza os dados mostrados na revisao.

A revisao humana antes da ativacao reduz o risco de uma extracao automatica incorreta virar preco de producao.

## 10. Banco de dados e modelos

### `backend/app/models/models.py`

Os modelos SQLAlchemy representam as tabelas de cada empresa. Os grupos essenciais sao:

- acesso: `User`, `Role` e `Permission`;
- operacao: `Transportadora`, `Cotacao`, `CotacaoVolume` e `CotacaoResultado`;
- tabelas tarifarias: `TabelaFrete`, `DocumentoFrete`, `TarifaFrete`, `TaxaFrete` e regras de peso, rota, prazo e cubagem;
- suporte: configuracoes, credenciais, logs de integracao e auditoria.

A separacao entre `Cotacao`, volumes e resultados permite que uma cotacao tenha varios volumes e varias respostas de transportadoras sem duplicar os dados principais.

### Multiempresa

`backend/app/models/master.py` guarda os tenants e temas globais. Ja os dados operacionais ficam separados por schema do PostgreSQL.

`backend/app/core/tenant.py` identifica a empresa pelo cookie. `backend/app/db/session.py` aplica o schema correto na sessao do banco. Assim, a mesma aplicacao atende varias empresas, mas cada requisicao acessa apenas os dados do tenant identificado.

## 11. Autenticacao, autorizacao e seguranca

### Autenticacao

`backend/app/core/security.py` faz hash e verificacao de senha, cria e valida tokens JWT e possui funcoes para TOTP. O token identifica usuario, tenant, tipo do token e versao da sessao.

### Autorizacao

`backend/app/core/deps.py` possui duas dependencias centrais:

- `get_current_user`: valida token, tenant, usuario ativo e versao da sessao;
- `require_permission`: junta as permissoes dos papeis do usuario e exige o codigo necessario.

A versao de sessao permite revogar tokens antigos, por exemplo depois de uma troca de senha.

### Defesa em camadas

O frontend esconde rotas indevidas para melhorar a experiencia, mas a seguranca real esta no backend. Mesmo que alguem chame a API manualmente, cada endpoint sensivel verifica sua permissao.

Outras protecoes incluem CORS restrito, hosts confiaveis, cookies seguros, protecao de origem em operacoes mutaveis, credenciais criptografadas, validacao de uploads, auditoria e cabecalhos HTTP de seguranca.

## 12. Infraestrutura

### `docker-compose.yml`

Orquestra tres servicos:

- `postgres`: banco PostgreSQL com volume persistente e health check;
- `backend`: API na porta 8000, iniciada depois que o banco estiver saudavel;
- `frontend`: aplicacao Vite na porta 5173, iniciada depois do backend.

As portas sao publicadas apenas em `127.0.0.1`, e os containers usam `no-new-privileges`. O volume `postgres_data` preserva os dados entre reinicializacoes.

## 13. Testes

Os testes do backend ficam em `backend/tests`. Eles cobrem cubagem, calculo por tabelas, extracao de documentos, consulta de CEP/CNPJ, dashboard, integracao Sankhya, schemas e permissoes.

O fluxo `e2e/tabela_frete_flow.ps1` testa uma jornada completa: cria uma tabela, importa um CSV, revisa, aprova, ativa e utiliza os valores em uma cotacao.

Para explicar a importancia:

> Os testes unitarios verificam regras isoladas, enquanto o E2E comprova que as camadas funcionam juntas no fluxo que o usuario realmente executa.

## 14. Roteiro sugerido para demonstracao

1. Fazer login e mostrar que existem perfis e permissoes.
2. Abrir o dashboard para contextualizar os indicadores.
3. Mostrar uma transportadora e seu metodo de calculo.
4. Mostrar rapidamente uma tabela ativa e sua vigencia.
5. Criar uma cotacao com origem, destino e pelo menos um volume.
6. Explicar o status de processamento enquanto o polling ocorre.
7. Comparar valores e prazos e apontar a melhor opcao destacada.
8. Abrir o historico para mostrar que a operacao foi persistida.

Durante a demonstracao, conecte cada tela a uma camada: tela React, chamada do service, endpoint FastAPI, regra de negocio e banco.

## 15. Perguntas provaveis e respostas

### Por que o backend recalcula a cubagem?

Porque o navegador nao e uma fonte confiavel. O calculo no frontend serve para feedback visual; o calculo oficial e feito novamente no servidor.

### Por que usar processamento em segundo plano e polling?

As transportadoras podem demorar ou falhar. A API responde rapidamente com um ID, processa as consultas separadamente e o frontend acompanha o status sem bloquear a tela.

### O que acontece se uma transportadora estiver fora do ar?

A consulta possui timeout e a falha vira um resultado individual. As demais consultas continuam, e o estado final pode ser `completed_with_errors`.

### Como e escolhida a melhor transportadora?

Entre as respostas com status de sucesso, o sistema escolhe o menor valor de frete. O usuario ainda pode selecionar outra opcao valida considerando prazo ou preferencia comercial.

### Como o sistema suporta calculos diferentes?

Por meio do padrao Adapter. Cada integracao traduz sua API ou tabela para o mesmo formato de resposta esperado pelo servico de cotacao.

### Como os dados de empresas diferentes ficam separados?

Cada empresa e um tenant. O middleware identifica o tenant e a sessao SQLAlchemy usa o schema PostgreSQL correspondente durante aquela requisicao.

### Por que existem schemas Pydantic e tipos TypeScript?

Pydantic valida os contratos no servidor. Os tipos TypeScript ajudam o frontend a detectar incompatibilidades durante o desenvolvimento. Juntos, deixam a comunicacao entre as camadas mais previsivel.

### Qual e a limitacao atual mais importante?

Nem todos os metodos de transportadora possuem adapter automatico real. Alguns cenarios usam simulacao ou retornam um erro controlado ate que a integracao correspondente seja implementada. O historico detalhado de alteracoes de tabela tambem possui endpoint ainda nao implementado.

## 16. Encerramento sugerido

> A principal decisao do projeto foi separar interface, comunicacao HTTP, regras de negocio, integracoes e persistencia. Essa organizacao permite incluir novas transportadoras e novos formatos de tabela com impacto reduzido nas outras camadas. O fluxo assincrono, as validacoes no backend e o isolamento por tenant tornam o sistema preparado para um processo real de cotacao multiempresa.

## 17. Arquivos essenciais para revisar antes de apresentar

Leia nesta ordem:

1. `frontend/src/pages/NovaCotacao/NovaCotacao.tsx`
2. `frontend/src/hooks/useCotacao.ts`
3. `frontend/src/services/cotacaoService.ts`
4. `backend/app/api/v1/endpoints/cotacoes.py`
5. `backend/app/services/cotacao_service.py`
6. `backend/app/services/cubagem.py`
7. `backend/app/schemas/cotacao.py`
8. `backend/app/models/models.py`
9. `backend/app/core/deps.py`
10. `backend/app/main.py`

Se houver pouco tempo, concentre-se nos itens 1, 2, 4 e 5: eles mostram o caminho completo da principal funcionalidade.
