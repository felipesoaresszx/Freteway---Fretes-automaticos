# FreteWay

Plataforma web multiempresa para centralizar cotações de frete, comparar transportadoras, administrar tabelas tarifárias e integrar o processo logístico a sistemas externos.

O FreteWay opera como uma instalação dedicada a uma única organização.

## Contexto para colaboradores e assistentes de IA

- Preserve os controles de autenticação, permissões e auditoria nas novas funcionalidades.
- Nunca exponha, registre ou versione credenciais, tokens, arquivos `.env`, dumps ou dados reais de clientes.
- Credenciais de integrações são criptografadas no backend e nunca devem retornar ao frontend.
- O backend é a fonte de verdade para cubagem, cálculo tarifário, permissões e integrações.
- Alterações de contrato exigem revisar schemas Pydantic, endpoints, serviços e os tipos/serviços equivalentes no frontend.
- Toda alteração em modelo persistente requer migration Alembic; não altere o banco manualmente.
- Faça testes proporcionais: Pytest para backend e Vitest para frontend.
- `app.seed` é exclusivo para desenvolvimento local e jamais deve ser executado em produção.

## Recursos principais

- Autenticação por cookie HTTP-only/JWT e permissões.
- Banco PostgreSQL único, com dados operacionais no schema `public`.
- Dashboard e histórico pesquisável de cotações.
- Cotação paralela, retentativas, timeout e circuit breaker por provider.
- Cadastro, importação e enriquecimento de transportadoras.
- Providers para SSW, Risso/Senior TMS, Correios, Braspress, Jamef, Sankhya, API genérica e tabelas próprias.
- Importação de tabelas de frete em CSV, XLS, XLSX, PDF, DOCX, PNG e JPEG, com aprovação e vigência auditáveis.

## Arquitetura

| Camada | Tecnologias |
| --- | --- |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, TanStack Query, Zustand, React Hook Form e Zod |
| API | Python 3.12, FastAPI, SQLAlchemy assíncrono, Pydantic, JWT e Alembic |
| Processamento | Worker Python com tarefas persistidas no PostgreSQL |
| Banco | PostgreSQL 16 |
| Documentos | OpenPyXL, xlrd, pypdf, python-docx, Pillow e Tesseract OCR |
| Infraestrutura | Docker Compose; Nginx e Caddy em produção |

```text
Navegador (React) → API FastAPI → PostgreSQL
                         ├── Worker de cotações
                         ├── Providers de transportadoras
                         └── Integração Sankhya
```

## Estrutura

```text
backend/
  alembic/                 # migrations
  app/
    api/v1/endpoints/      # endpoints REST
    core/                  # configuração e segurança
    integrations/          # providers e adapters externos
    models/                # modelos SQLAlchemy
    schemas/               # contratos Pydantic
    services/              # regras de negócio
  docs/                    # documentação de integrações
  tests/
frontend/src/              # interface React
deploy/                    # proxy e scripts de implantação
e2e/                       # fluxos ponta a ponta
scripts/                   # backup, restore e validações
data/tariffs/              # tabelas tarifárias de referência
```

## Início rápido com Docker

Pré-requisitos: Docker Desktop ou Docker Engine com Docker Compose v2.

```powershell
Copy-Item .env.example .env
Copy-Item backend/.env.example backend/.env
Copy-Item frontend/.env.example frontend/.env
docker volume create frete-system_postgres_data
docker compose up --build -d
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.bootstrap
docker compose exec backend python -m app.seed
```

Antes de subir, altere `POSTGRES_PASSWORD` em `.env`; defina valores seguros e distintos para `JWT_SECRET` e `CREDENTIAL_ENCRYPTION_KEY` em `backend/.env`.

| Serviço | Endereço |
| --- | --- |
| Aplicação | <http://localhost:5173> |
| API | <http://localhost:8000> |
| Swagger | <http://localhost:8000/docs> |
| Health | <http://localhost:8000/health> |

O seed local cria dados demonstrativos; usuário: `admin@fretesystem.com`; senha: `admin123`.

```powershell
docker compose ps
docker compose logs -f backend worker
docker compose down
```

O banco usa o volume externo `frete-system_postgres_data`. Não use `docker compose down -v` se precisar preservar dados.

## Execução sem Docker

Exige Python 3.12, Node.js 20+, npm, PostgreSQL 16 e Tesseract com idioma português para OCR. Crie o banco e configure `DATABASE_URL` em `backend/.env` antes de iniciar.

```powershell
# API
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
alembic upgrade head
python -m app.bootstrap
python -m app.seed
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# worker (outro terminal)
cd backend
.\.venv\Scripts\Activate.ps1
python -m app.worker

# frontend (outro terminal)
cd frontend
npm ci
Copy-Item .env.example .env
npm run dev
```

## Fluxos de domínio

### Acesso multiempresa

1. O usuário informa o código da empresa.
3. O frontend aplica o tema da empresa.
4. O usuário autentica com e-mail e senha.
4. Consultas posteriores usam o banco único da instalação.

### Cotação

1. O usuário informa origem, destino, nota fiscal, volumes e transportadoras.
2. O backend recalcula a cubagem e registra uma tarefa persistente.
3. O worker consulta providers em paralelo e isola falhas individuais.
4. O resultado é `completed`, `completed_with_errors` ou `failed`.
5. Uma proposta válida pode ser escolhida como vencedora.

Transportadoras com tabela própria usam somente a tabela ativa e vigente. A cotação preserva a memória do cálculo e dos componentes tarifários para auditoria.

### Tabelas de frete

```text
draft → upload/análise → review → approved → active
                            └──→ cancelled
```

Cada tabela aceita até dois documentos complementares, consolidados em uma análise única antes da revisão, aprovação e ativação.

## Variáveis de ambiente relevantes

Os exemplos completos estão em `.env.example`, `backend/.env.example` e `frontend/.env.example`.

| Variável | Finalidade |
| --- | --- |
| `DATABASE_URL` | Conexão assíncrona com PostgreSQL |
| `JWT_SECRET` | Assinatura de tokens |
| `CREDENTIAL_ENCRYPTION_KEY` | Criptografia das credenciais integradas |
| `CORS_ORIGINS` / `TRUSTED_HOSTS` | Origens e hosts permitidos |
| `INTEGRATION_*` | Concorrência, retentativas e circuit breaker |
| `SANKHYA_API_KEY` | Chave de entrada legada da Sankhya |
| `VITE_API_URL` | Prefixo da API consumido pelo frontend |

Em produção, use URL pública válida, segredos com pelo menos 32 caracteres, cookies seguros e hosts/origens explícitos. Não troque `CREDENTIAL_ENCRYPTION_KEY` sem um plano de migração: isso impede ler credenciais armazenadas.

## Integrações

| Provider | Configuração principal |
| --- | --- |
| SSW | Domínio, login, senha, CNPJ pagador e mercadoria padrão |
| Risso / Senior TMS | URLs TMS/Bridge, usuário, senha, CNPJ remetente e tipo de frete |
| Correios | URL, credenciais Meu Correios, cartão de postagem e serviços |
| Braspress / Jamef | Credenciais e parâmetros específicos das APIs |
| Sankhya | `X-API-Key`, `CODEMP` e mapeamento de transportadora por empresa |

A entrada Sankhya é `POST /integracoes/sankhya/cotacao`. O mapeamento é administrado em `GET` e `PUT /api/v1/integrations/sankhya/mapeamentos`.

Guias: [SSW](backend/docs/integracoes/ssw.md), [Risso/Senior](backend/docs/integracoes/risso.md), [Sankhya](backend/docs/integracao-sankhya.md) e [Jamef](backend/docs/integracao-jamef.md).

## Testes e qualidade

```powershell
# backend
cd backend
pytest

# frontend
cd frontend
npm ci
npm run lint
npm run test:run
npm run build

# E2E de tabela de frete (API, worker, migrations e seed em execução)
.\e2e\tabela_frete_flow.ps1
```

## Migrations

```powershell
docker compose exec backend alembic upgrade head
docker compose exec backend alembic current
docker compose exec backend alembic revision --autogenerate -m "descricao da alteracao"
```

`python -m app.bootstrap` verifica a conexão com o banco. `python -m app.seed` é estritamente local.

## Produção e documentação

O ambiente de produção utiliza imagens imutáveis, frontend Nginx, proxy Caddy com TLS, rede interna e volumes persistentes. Consulte antes de implantar:

- [Guia de implantação](DEPLOYMENT.md)
- [White-label e multiempresa](backend/docs/white-label.md)
- [Estado do núcleo de cotação](backend/docs/cotacao-core-status.md)
- [Agente de análise de tabelas de frete](backend/docs/agente-tabelas-frete.md)
- [Auditoria local](AUDIT_LOCALHOST.md)
