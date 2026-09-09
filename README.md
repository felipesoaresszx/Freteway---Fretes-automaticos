# FreteWay

Plataforma web multiempresa para centralizar cotações de frete, comparar transportadoras, administrar tabelas tarifárias e integrar o processo logístico a sistemas externos.

O projeto é formado por um frontend React, uma API FastAPI, um worker de processamento assíncrono e PostgreSQL. Cada cliente opera em um contexto isolado, identificado pelo código da empresa antes do login, com identidade visual e configurações próprias.

## Recursos principais

- Autenticação por cookie HTTP-only/JWT, perfis, permissões e suporte a 2FA configurável.
- Isolamento multi-tenant por schema e identificação da empresa por código de acesso.
- White-label por empresa, com nome, logotipo, cores e favicon próprios.
- Dashboard operacional e histórico pesquisável de cotações.
- Cotação paralela com cubagem recalculada no backend, retentativas, timeout e circuit breaker.
- Cadastro e enriquecimento de transportadoras por CNPJ, pesquisa web e catálogo RNTRC/ANTT.
- Providers para SSW, Risso/Senior TMS, Correios, Braspress e Jamef, além de API genérica e cálculo por tabela própria.
- Importação de transportadoras em lote por CSV/XLSX.
- Importação e leitura de tabelas de frete em CSV, XLS, XLSX, PDF, DOCX, PNG e JPEG.
- Consolidação de até dois documentos, revisão auditável, aprovação, vigência e ativação de tabelas.
- Integração Sankhya para cotação e de-para de transportadoras por empresa (`CODEMP`).
- Configurações de empresa, usuários, segurança, notificações, integrações globais e auditoria.

## Tecnologias

| Camada | Tecnologias |
| --- | --- |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, TanStack Query, Zustand, React Hook Form, Zod, Axios e Recharts |
| Backend | Python 3.12, FastAPI, SQLAlchemy assíncrono, Pydantic, JWT e Alembic |
| Banco | PostgreSQL 16 |
| Documentos | OpenPyXL, xlrd, pypdf, python-docx, Pillow e Tesseract OCR |
| Infraestrutura | Docker Compose, worker com fila no PostgreSQL, Nginx e Caddy em produção |
| Testes | Pytest, Vitest e fluxo E2E em PowerShell |

## Estrutura

```text
FreteWay/
├── backend/
│   ├── alembic/                 # migrations do banco
│   ├── app/
│   │   ├── api/v1/endpoints/    # endpoints REST
│   │   ├── core/                # segurança, configuração e tenant
│   │   ├── integrations/        # providers e adapters
│   │   ├── models/              # modelos SQLAlchemy
│   │   ├── schemas/             # contratos Pydantic
│   │   └── services/            # regras de negócio
│   ├── docs/                    # documentação das integrações
│   └── tests/
├── frontend/src/
│   ├── api/                     # cliente HTTP
│   ├── components/              # componentes reutilizáveis
│   ├── contexts/                # contexto da empresa
│   ├── hooks/                   # queries e mutations
│   ├── pages/                   # telas da aplicação
│   ├── routes/                  # rotas e controle de acesso
│   ├── services/                # acesso à API
│   └── types/                   # tipos TypeScript
├── deploy/                      # proxy e scripts de implantação
├── e2e/                         # fluxo ponta a ponta
├── scripts/                     # backup, restore e validações
├── docker-compose.yml           # desenvolvimento
└── docker-compose.production.yml
```

## Pré-requisitos

Para o fluxo recomendado de desenvolvimento:

- Docker Desktop ou Docker Engine;
- Docker Compose v2.

Para executar sem Docker:

- Python 3.12;
- Node.js 20 ou superior e npm;
- PostgreSQL 16;
- Tesseract OCR com o idioma português para leitura de imagens.

## Início rápido com Docker

1. Crie os arquivos locais de ambiente:

```powershell
Copy-Item .env.example .env
Copy-Item backend/.env.example backend/.env
Copy-Item frontend/.env.example frontend/.env
```

No Linux ou macOS, use `cp`.

2. Altere `POSTGRES_PASSWORD` em `.env`. Em `backend/.env`, defina valores diferentes e seguros para `JWT_SECRET` e `CREDENTIAL_ENCRYPTION_KEY`.

3. Crie uma vez o volume de banco usado pelo Compose:

```bash
docker volume create frete-system_postgres_data
```

4. Construa e inicie os serviços:

```bash
docker compose up --build -d
```

5. Aplique as migrations e carregue os dados de desenvolvimento:

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.bootstrap
docker compose exec backend python -m app.seed
```

6. Acesse:

- Aplicação: <http://localhost:5173>
- API: <http://localhost:8000>
- Swagger: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>
- Health: <http://localhost:8000/health>
- Readiness: <http://localhost:8000/api/v1/health/ready>

O seed local cria os dados demonstrativos abaixo:

```text
Código da empresa: valor de BOOTSTRAP_TENANT_CODE (MODIAL2026 por padrão)
E-mail: admin@fretesystem.com
Senha: admin123
```

Essas credenciais são exclusivas para desenvolvimento. O seed legado não deve ser executado em produção.

Comandos úteis:

```bash
docker compose ps
docker compose logs -f backend worker
docker compose down
```

O banco permanece no volume externo `frete-system_postgres_data`. Não use `docker compose down -v` se houver dados que precisem ser preservados.

## Execução local sem Docker

Crie o banco PostgreSQL e ajuste `DATABASE_URL` em `backend/.env` antes de iniciar a API.

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
alembic upgrade head
python -m app.bootstrap
python -m app.seed
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

No Linux ou macOS, ative o ambiente com `source .venv/bin/activate`.

Em outro terminal, inicie o worker:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m app.worker
```

### Frontend

```powershell
cd frontend
npm ci
Copy-Item .env.example .env
npm run dev
```

## Variáveis de ambiente

Os exemplos completos ficam em `.env.example`, `backend/.env.example` e `frontend/.env.example`.

### Backend

| Variável | Finalidade | Padrão de desenvolvimento |
| --- | --- | --- |
| `DATABASE_URL` | Conexão assíncrona com PostgreSQL | `postgresql+asyncpg://frete:frete@localhost:5432/frete` |
| `MASTER_DATABASE_URL` | Conexão do catálogo multi-tenant | usa `DATABASE_URL` quando omitida |
| `PUBLIC_BASE_URL` | URL pública da API | `http://localhost:8000` |
| `JWT_SECRET` | Assinatura dos tokens | `change-me` |
| `CREDENTIAL_ENCRYPTION_KEY` | Proteção das credenciais integradas | `change-me-separately` |
| `CORS_ORIGINS` | Origens autorizadas em JSON | `["http://localhost:5173"]` |
| `TRUSTED_HOSTS` | Hosts aceitos pela API em JSON | localhost, loopback e backend |
| `BOOTSTRAP_TENANT_*` | Empresa inicial e schema associado | tenant Modial no schema `public` |
| `TABELA_FRETE_STORAGE_DIR` | Originais das tabelas importadas | `storage/tabelas_frete` |
| `DOCUMENT_STORAGE_DIR` | Documentos processados | `storage/documentos` |
| `EMPRESA_LOGO_STORAGE_DIR` | Logotipos por empresa | `storage/configuracoes/logos` |
| `INTEGRATION_*` | Concorrência, retentativas e circuit breaker | consulte o arquivo de exemplo |
| `ENRICHMENT_*` | Pesquisa para enriquecimento de transportadoras | DuckDuckGo HTML |
| `ANTT_*` | Catálogo público RNTRC | dados abertos da ANTT |
| `SANKHYA_API_KEY` | Chave de entrada legada do Sankhya | sem valor padrão |

Em produção, a aplicação exige URL pública válida, segredos distintos com pelo menos 32 caracteres, hosts/origens explícitos e cookies seguros. Não altere a chave de criptografia de uma instalação existente, pois isso pode impedir a leitura das credenciais armazenadas.

### Frontend

| Variável | Finalidade | Desenvolvimento | Produção |
| --- | --- | --- | --- |
| `VITE_API_URL` | Prefixo consumido pelo navegador | `http://localhost:8000/api/v1` | `/api/v1` |

## Fluxos principais

### Acesso multiempresa

1. O usuário informa o código da empresa.
2. `POST /api/v1/companies/identify` identifica o tenant e grava seu contexto temporário.
3. A tela aplica a identidade visual daquela empresa.
4. O usuário entra com e-mail, senha e, quando habilitado, código 2FA.
5. As consultas seguintes são executadas no schema do tenant identificado.

### Cotação

1. O usuário informa origem, destino, valor da nota, documento do destinatário quando necessário, volumes e transportadoras.
2. O backend recalcula peso cubado e registra uma tarefa persistente.
3. O worker consulta as transportadoras em paralelo, isolando falhas por provider.
4. O resultado termina como `completed`, `completed_with_errors` ou `failed`.
5. Uma proposta válida pode ser selecionada como vencedora.

Transportadoras configuradas com tabela própria usam a tabela ativa e vigente. As cotações guardam memória do cálculo e dos componentes tarifários para manter a auditoria mesmo após mudanças posteriores na tabela.

### Tabelas de frete

```text
draft -> upload/análise -> review -> approved -> active
                              `----> cancelled
```

Cada tabela aceita um ou dois documentos complementares. Os arquivos são consolidados na mesma análise, mantendo referência aos documentos de origem. O usuário revisa os dados antes de aprovar, e somente tabelas aprovadas podem ser ativadas.

### Integrações

| Provider | Configuração principal |
| --- | --- |
| SSW | Domínio, login, senha, CNPJ pagador e mercadoria padrão |
| Risso / Senior TMS | URLs TMS/Bridge, usuário, senha, CNPJ remetente e tipo de frete |
| Correios | URL, credenciais Meu Correios, cartão de postagem e serviços |
| Braspress | Usuário, senha e parâmetros próprios da API |
| Jamef | Credenciais e parâmetros próprios da API |

Segredos são criptografados e não retornam ao frontend. Status, horário e mensagem da última validação permanecem disponíveis para diagnóstico.

Guias específicos:

- [SSW](backend/docs/integracoes/ssw.md)
- [Risso/Senior](backend/docs/integracoes/risso.md)
- [Sankhya](backend/docs/integracao-sankhya.md)
- [Jamef](backend/docs/integracao-jamef.md)

### Sankhya

A entrada principal é `POST /integracoes/sankhya/cotacao`, autenticada por `X-API-Key`. A chave identifica o tenant, e `CODEMP` seleciona o de-para específico da empresa. Também existem aliases sob `/api/v1` para compatibilidade.

Os mapeamentos são administrados em:

```text
GET /api/v1/integrations/sankhya/mapeamentos
PUT /api/v1/integrations/sankhya/mapeamentos/{transportadora_id}
```

Consulte o [contrato completo da integração](backend/docs/integracao-sankhya.md) antes da homologação.

## API

Os endpoints administrativos e de negócio usam o prefixo `/api/v1`. A documentação interativa fica disponível em `/docs` e `/redoc` somente fora de produção.

| Grupo | Rotas principais |
| --- | --- |
| Empresa e autenticação | `/companies/identify`, `/auth/login`, `/auth/me`, `/auth/logout` |
| Dashboard | `/dashboard` |
| Cotações | `/cotacoes` |
| Transportadoras | `/transportadoras`, `/carriers`, `/enrichment` |
| Tabelas | `/tabelas-frete` |
| Integrações | `/transportadoras/.../ssw`, `/integrations/sankhya/...` |
| Configurações | `/configuracoes` |
| Administração de tenants | rotas protegidas de `tenants_admin` |
| Saúde | `/health`, `/health/live`, `/health/ready` |

## Testes e validação

### Backend

```powershell
cd backend
pytest
```

Testes de integração real com APIs externas ficam desabilitados por padrão e exigem credenciais próprias.

### Frontend

```powershell
cd frontend
npm ci
npm run test:run
npm run build
```

### E2E de tabela de frete

Com API, worker, migrations e seed prontos:

```powershell
.\e2e\tabela_frete_flow.ps1
```

O script importa uma fixture CSV, revisa, aprova e ativa a tabela, depois a utiliza em uma cotação.

## Banco e migrations

```bash
# aplicar migrations
docker compose exec backend alembic upgrade head

# conferir a revisão atual
docker compose exec backend alembic current

# criar uma migration após alterar os modelos
docker compose exec backend alembic revision --autogenerate -m "descricao da alteracao"
```

`python -m app.bootstrap` é idempotente e cria apenas o tenant e o tema ausentes. `python -m app.seed` adiciona usuário e transportadoras demonstrativas e deve ser restrito ao desenvolvimento.

## Produção

O ambiente de produção usa imagens imutáveis, frontend Nginx, proxy Caddy com TLS, redes internas para aplicação/banco e volumes persistentes para PostgreSQL e documentos.

Antes de implantar:

1. Leia integralmente [DEPLOYMENT.md](DEPLOYMENT.md).
2. Copie `.env.production.example` e `backend/.env.production.example` para os respectivos arquivos sem `.example`.
3. Defina senha do banco, segredos, domínio, hosts e CORS com valores reais.
4. Preserve e valide backups do banco e do storage.
5. Execute o deploy pelo script documentado, sem rodar o seed de desenvolvimento.

```bash
chmod +x deploy/deploy.sh scripts/*.sh
./deploy/deploy.sh
```

O procedimento detalhado inclui migração de storage, transporte/restauração do banco, healthchecks, rollback e checklist pós-reboot.

## Segurança e cuidados operacionais

- Nunca versione `.env`, dumps, tokens ou credenciais reais.
- Use HTTPS e restrinja `CORS_ORIGINS` e `TRUSTED_HOSTS` aos domínios necessários.
- Não envie credenciais de transportadora no payload de cotação; use as rotas de configuração.
- Preserve `CREDENTIAL_ENCRYPTION_KEY` entre deploys e backups.
- Proteja os volumes de banco, documentos e logotipos com backup periódico.
- Valide cada provider na tela de Integrações antes de usá-lo em produção.
- Providers sem credenciais válidas permanecem indisponíveis; integrações simuladas servem apenas para desenvolvimento.

## Documentação complementar

- [Implantação segura](DEPLOYMENT.md)
- [White-label e multiempresa](backend/docs/white-label.md)
- [Estado do núcleo de cotação](backend/docs/cotacao-core-status.md)
- [Auditoria do ambiente local](AUDIT_LOCALHOST.md)
