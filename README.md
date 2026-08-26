# FreteWay

Sistema web para centralizar cotações de frete, comparar propostas de transportadoras e administrar tabelas tarifárias e integrações. A aplicação reúne um frontend React, uma API FastAPI e persistência em PostgreSQL.

## Principais recursos

- Autenticação JWT, usuários, perfis e permissões (`admin`, `operador` e `visualizacao`).
- Dashboard com indicadores operacionais e desempenho das transportadoras.
- Cadastro, edição, ativação e exclusão de transportadoras, com consulta pública de CNPJ.
- Métodos de cálculo por tabela própria, API, web service ou fluxo manual.
- Configuração de APIs por transportadora, credenciais criptografadas, validação com mensagem persistida e teste de status.
- Providers nativos para SSW, Risso/Senior TMS, Correios, Braspress e Jamef, além do adapter de API genérica.
- Criação de cotações com cálculo de cubagem, CPF/CNPJ opcional do destinatário e consulta paralela às transportadoras.
- Histórico de cotações com busca, filtros e paginação.
- Importação de até dois documentos complementares por tabela em CSV, XLS, XLSX, PDF, DOCX e imagens PNG/JPEG.
- Extração consolidada, revisão com acesso aos documentos de origem, aprovação, vigência e ativação de tabelas tarifárias.
- Configurações da empresa, parâmetros de cotação, notificações, segurança, integrações globais e auditoria.

## Tecnologias

| Camada | Tecnologias |
| --- | --- |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, TanStack Query, Zustand, React Hook Form, Zod, Axios e Recharts |
| Backend | Python 3.12, FastAPI, SQLAlchemy assíncrono, Pydantic, JWT e Alembic |
| Banco de dados | PostgreSQL 16 |
| Documentos | OpenPyXL, xlrd, pypdf, python-docx, Pillow e Tesseract OCR |
| Infraestrutura | Docker, Docker Compose e worker com fila persistente no PostgreSQL |
| Testes | Pytest, Vitest e fluxo E2E em PowerShell |

## Estrutura do projeto

```text
frete-system/
├── backend/
│   ├── alembic/                 # migrations do banco
│   ├── docs/integracoes/        # guias específicos dos providers
│   ├── app/
│   │   ├── api/v1/endpoints/    # endpoints REST
│   │   ├── core/                # configurações, autenticação e dependências
│   │   ├── db/                  # sessão assíncrona do PostgreSQL
│   │   ├── integrations/        # adapters de transportadoras
│   │   ├── models/              # modelos SQLAlchemy
│   │   ├── schemas/             # contratos Pydantic
│   │   └── services/            # regras de negócio e cálculo de frete
│   └── tests/                   # testes do backend
├── frontend/
│   └── src/
│       ├── api/                 # cliente HTTP
│       ├── components/          # componentes reutilizáveis
│       ├── hooks/               # queries e mutations
│       ├── pages/               # telas da aplicação
│       ├── routes/              # rotas públicas e protegidas
│       ├── services/            # acesso à API
│       ├── stores/              # estado de autenticação
│       └── types/               # tipos TypeScript
├── e2e/                         # teste do fluxo completo
└── docker-compose.yml
```

## Pré-requisitos

Para a forma recomendada de execução:

- Docker Desktop com Docker Compose v2.

Para executar sem Docker:

- Python 3.12;
- Node.js 20 e npm;
- PostgreSQL 16;
- Tesseract OCR com o idioma português, caso sejam processadas imagens.

## Início rápido com Docker

1. Crie os arquivos de ambiente:

```powershell
Copy-Item .env.example .env
Copy-Item backend/.env.example backend/.env
Copy-Item frontend/.env.example frontend/.env
```

Em Linux ou macOS, use `cp` no lugar de `Copy-Item`.

2. Troque `JWT_SECRET=change-me` em `backend/.env` por um segredo longo e aleatório.

3. Construa e inicie os serviços:

```bash
docker compose up --build -d
```

4. Aplique as migrations e carregue os dados iniciais:

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.seed
```

5. Acesse:

- Aplicação: http://localhost:5173
- API: http://localhost:8000
- Swagger: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health check: http://localhost:8000/health

O seed de desenvolvimento cria o acesso abaixo:

```text
E-mail: admin@fretesystem.com
Senha:  admin123
```

Essas credenciais são apenas para desenvolvimento e devem ser substituídas antes de qualquer implantação real.

Para acompanhar os logs ou encerrar o ambiente:

```bash
docker compose logs -f
docker compose down
```

Os dados do PostgreSQL permanecem no volume `postgres_data`. Use `docker compose down -v` somente quando quiser apagar definitivamente o banco local.

## Execução local sem Docker

Inicie primeiro um PostgreSQL e crie um banco compatível com a URL definida em `backend/.env`.

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

No Linux ou macOS, ative o ambiente com `source .venv/bin/activate`.

### Frontend

Em outro terminal:

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

## Variáveis de ambiente

### Backend

| Variável | Finalidade | Padrão da aplicação |
| --- | --- | --- |
| `DATABASE_URL` | Conexão assíncrona com PostgreSQL | `postgresql+asyncpg://frete:frete@localhost:5432/frete` |
| `JWT_SECRET` | Assinatura dos tokens e chave derivada para proteger credenciais | `change-me` |
| `JWT_ALGORITHM` | Algoritmo do JWT | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Expiração inicial do token | `60` |
| `CORS_ORIGINS` | Lista JSON de origens autorizadas | `["http://localhost:5173"]` |
| `CNPJ_CONSULTA_BASE_URL` | Provedor de consulta cadastral | BrasilAPI |
| `CNPJ_CONSULTA_TIMEOUT_SECONDS` | Timeout da consulta de CNPJ | `10` |
| `TABELA_FRETE_STORAGE_DIR` | Armazenamento de documentos importados | `storage/tabelas_frete` |
| `TABELA_FRETE_UPLOAD_MAX_BYTES` | Limite por documento | `26214400` (25 MiB) |
| `EMPRESA_LOGO_STORAGE_DIR` | Armazenamento de logotipos | `storage/configuracoes/logos` |
| `EMPRESA_LOGO_MAX_BYTES` | Limite do logotipo | `2097152` (2 MiB) |
| `TIMEOUT_API_INTEGRACAO` | Timeout de integração via API | `15` segundos |
| `TIMEOUT_BROWSER_INTEGRACAO` | Timeout de automação de navegador | `60` segundos |
| `INTEGRATION_RETRY_ATTEMPTS` | Tentativas para falhas transitórias de transportadoras | `3` |
| `INTEGRATION_MAX_CONCURRENCY` | Limite de chamadas externas simultâneas por processo | `10` |
| `INTEGRATION_CIRCUIT_FAILURES` | Falhas consecutivas antes de suspender uma integração | `5` |
| `INTEGRATION_CIRCUIT_RESET_SECONDS` | Tempo para testar novamente uma integração suspensa | `60` |
| `N8N_BASE_URL` | URL de uma futura/externa instância n8n | `http://n8n:5678` |

O Compose substitui `DATABASE_URL` para usar o hostname interno `postgres`. Os valores `JAMEF_API_KEY`, `JADLOG_TOKEN`, `BRASPRESS_USER`, `BRASPRESS_PASSWORD` e `PLAYWRIGHT_HEADLESS` presentes no exemplo são reservados para adapters/automação.

### Frontend

| Variável | Finalidade | Padrão |
| --- | --- | --- |
| `VITE_API_URL` | Prefixo da API consumida pelo navegador | `http://localhost:8000/api/v1` |

## Fluxos principais

### Cotação

1. O usuário informa origem, destino, nota fiscal, CPF/CNPJ do destinatário quando exigido pelo provider, volumes e transportadoras.
2. O backend recalcula a cubagem para não depender de valores enviados pelo navegador.
3. A cotação é gravada junto com uma tarefa persistente e começa com status `processing`.
4. O worker executa as consultas em paralelo, com timeout, retentativas e circuit breaker.
5. O frontend consulta o resultado até chegar a `completed`, `completed_with_errors` ou `failed`.
6. Uma proposta bem-sucedida pode ser selecionada como vencedora.

Transportadoras com `metodo_calculo=tabela_propria` utilizam a tabela ativa e vigente. Integrações do tipo API são resolvidas pelo `adapter_code` no registry compartilhado. SSW, Risso e Correios usam o contrato universal de cotação; Jamef e Braspress também possuem seleção dedicada no fluxo legado de configuração de API. Uma falha fica isolada no resultado daquela transportadora e não interrompe as demais consultas.

### Integrações de transportadoras

| Provider | Configuração principal | Observações |
| --- | --- | --- |
| SSW | Domínio, login, senha, CNPJ pagador e mercadoria padrão | SOAP assíncrono, consulta de mercadorias, teste de conexão e importação de transportadoras em massa |
| Risso / Senior TMS | URLs TMS/Bridge, usuário, senha, CNPJ remetente e tipo de frete | Login Senior com token em memória; requer CPF/CNPJ do destinatário para cotar |
| Correios | URL da API, usuário Meu Correios, senha do componente, cartão de postagem e serviços | Autentica pelo cartão de postagem e consulta preço e prazo de cada serviço configurado |
| Braspress | Usuário, senha e parâmetros da API | Autenticação Basic própria e uso do documento do destinatário |
| Jamef | Credenciais e parâmetros da API | Mantém o adapter dedicado já existente |

As telas específicas ficam em **Integrações**. Segredos são armazenados em `carrier_credentials`, protegidos pelo mecanismo de criptografia da aplicação, e não são devolvidos ao frontend. A configuração não secreta, o status, a data e a mensagem da última validação ficam em `carrier_integrations`.

Documentação detalhada: [`backend/docs/integracoes/ssw.md`](backend/docs/integracoes/ssw.md) e [`backend/docs/integracoes/risso.md`](backend/docs/integracoes/risso.md).

### Tabela de frete

```text
draft → upload/análise → review → approved → active
                                    └──────→ cancelled
```

Cada tabela aceita um ou dois documentos. Quando dois arquivos são enviados, eles entram no mesmo job, são analisados em conjunto e os dados complementares são consolidados em uma única revisão. A API preserva `documento_original` por compatibilidade e também retorna `documentos_originais` e `documento_ids`. Os dados podem ser revisados antes da aprovação; a ativação só é permitida depois que a tabela estiver aprovada.

## API

Todos os endpoints de negócio usam o prefixo `/api/v1` e, exceto o login e os health checks, exigem `Authorization: Bearer <token>`.

| Grupo | Endpoints principais |
| --- | --- |
| Autenticação | `POST /auth/login`, `GET /auth/me` |
| Dashboard | `GET /dashboard` |
| Cotações | `POST/GET /cotacoes`, `GET /cotacoes/{id}`, `POST /cotacoes/{id}/selecionar` |
| Transportadoras | CRUD em `/transportadoras`, consulta de CNPJ, integrações universais e configuração/status de API |
| SSW | Listagem, configuração, teste, mercadorias, cotação direta e importação em massa em `/transportadoras/.../ssw` |
| Tabelas de frete | CRUD, upload, análise de um ou dois documentos, revisão consolidada, aprovação, ativação, cancelamento e documentos em `/tabelas-frete` |
| Configurações | Empresa, cotação, notificações, segurança, usuários, perfis, integrações e auditoria em `/configuracoes` |

O contrato completo, parâmetros, exemplos e respostas ficam disponíveis no Swagger após iniciar o backend.

## Testes e validações

Com os containers em execução:

```bash
docker compose exec backend pytest
docker compose exec frontend npm run build
```

Localmente:

```powershell
cd backend
pytest
pytest tests/test_ssw_client.py tests/test_ssw_parser.py tests/test_ssw_provider.py
pytest tests/test_risso_provider.py tests/test_correios_provider.py tests/test_braspress_adapter.py

cd ../frontend
npm test
npm run build
```

O teste E2E cria uma tabela temporária, importa a fixture CSV, revisa, aprova, ativa e usa a tabela em uma cotação. Execute na raiz, com API, migrations e seed prontos:

```powershell
.\e2e\tabela_frete_flow.ps1
```

Os testes reais de SSW e Risso ficam desabilitados por padrão para evitar chamadas externas. Consulte os guias em `backend/docs/integracoes` para habilitá-los explicitamente com credenciais de teste.

## Banco de dados e migrations

Aplicar todas as migrations:

```bash
docker compose exec backend alembic upgrade head
```

Criar uma migration após alterar modelos:

```bash
docker compose exec backend alembic revision --autogenerate -m "descricao da alteracao"
```

Consultar a revisão atual:

```bash
docker compose exec backend alembic current
```

O script `python -m app.seed` é idempotente para o administrador e para as transportadoras iniciais. As migrations também preparam perfis, permissões, configurações padrão e integrações globais.

As migrations mais recentes adicionam a mensagem de validação das integrações (`018`) e cadastram Risso/Senior (`019`) e Correios (`020`) com seus respectivos `adapter_code`. Depois de atualizar o código, execute obrigatoriamente `alembic upgrade head` antes de configurar esses providers.

## Segurança e produção

- Nunca versionar arquivos `.env` nem credenciais reais.
- Nunca enviar credenciais de transportadora no payload da cotação; use a tela/rota de configuração da integração.
- Definir um `JWT_SECRET` exclusivo, forte e estável; sua alteração invalida tokens e afeta a leitura de segredos já protegidos.
- Remover ou trocar imediatamente o usuário e a senha do seed.
- Restringir `CORS_ORIGINS` aos domínios efetivamente usados.
- Usar HTTPS tanto na aplicação quanto nas APIs de transportadoras; o adapter genérico rejeita URLs inseguras.
- Persistir e proteger os diretórios de documentos/logotipos em produção.
- O frontend servido pelo Compose usa o servidor de desenvolvimento do Vite; para produção, gere `npm run build` e publique `frontend/dist` em um servidor web/CDN.
- Configure backup, observabilidade e rotação de segredos para o PostgreSQL e para as integrações.

## Observações atuais

- O Compose não inclui n8n nem Playwright; esses serviços precisam ser adicionados quando os respectivos adapters forem habilitados.
- O endpoint de histórico de uma tabela de frete ainda responde `501 Not Implemented`.
- A opção de exigir 2FA está modelada nas configurações, mas o fluxo de ativação de 2FA ainda não está disponível.
- Providers sem credenciais válidas permanecem pendentes e não devem ser usados em produção até passarem pelo teste da tela de Integrações.
- Parte das transportadoras iniciais ainda usa adapter simulado enquanto não houver configuração real de tabela/API.

