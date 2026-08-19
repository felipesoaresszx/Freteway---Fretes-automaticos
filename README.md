# FreteWay

Sistema web para centralizar cotações de frete, comparar propostas de transportadoras e administrar tabelas tarifárias e integrações. A aplicação reúne um frontend React, uma API FastAPI e persistência em PostgreSQL.

## Principais recursos

- Autenticação JWT, usuários, perfis e permissões (`admin`, `operador` e `visualizacao`).
- Dashboard com indicadores operacionais e desempenho das transportadoras.
- Cadastro, edição, ativação e exclusão de transportadoras, com consulta pública de CNPJ.
- Métodos de cálculo por tabela própria, API, web service ou fluxo manual.
- Configuração de APIs por transportadora, credenciais criptografadas e teste de status.
- Criação de cotações com cálculo de cubagem e consulta paralela às transportadoras.
- Histórico de cotações com busca, filtros e paginação.
- Importação de tabelas de frete em CSV, XLS, XLSX, PDF, DOCX e imagens PNG/JPEG.
- Extração, revisão, aprovação, vigência e ativação de tabelas tarifárias.
- Configurações da empresa, parâmetros de cotação, notificações, segurança, integrações globais e auditoria.

## Tecnologias

| Camada | Tecnologias |
| --- | --- |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, TanStack Query, Zustand, React Hook Form, Zod, Axios e Recharts |
| Backend | Python 3.12, FastAPI, SQLAlchemy assíncrono, Pydantic, JWT e Alembic |
| Banco de dados | PostgreSQL 16 |
| Documentos | OpenPyXL, xlrd, pypdf, python-docx, Pillow e Tesseract OCR |
| Infraestrutura | Docker e Docker Compose |
| Testes | Pytest, Vitest e fluxo E2E em PowerShell |

## Estrutura do projeto

```text
frete-system/
├── backend/
│   ├── alembic/                 # migrations do banco
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
Copy-Item backend/.env.example backend/.env
Copy-Item frontend/.env.example frontend/.env
```

Em Linux ou macOS, use `cp` no lugar de `Copy-Item`.

2. Troque `JWT_SECRET=change-me` em `backend/.env` por um segredo aleatório com pelo menos 32 caracteres. Em `ENVIRONMENT=production`, a API recusa a inicialização se a variável estiver vazia, mantiver o valor padrão ou for curta demais.

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

### Migração da chave de credenciais

Gere uma chave independente do JWT e grave-a no gerenciador de segredos do ambiente:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Instalações novas precisam apenas definir o resultado em `CREDENTIALS_ENCRYPTION_KEY`. Se o desenvolvimento já possuir credenciais criptografadas pela chave antiga, faça backup do banco, mantenha a API parada e execute uma única vez, a partir de `backend`:

```powershell
$env:LEGACY_CREDENTIALS_ENCRYPTION_KEY="valor-atual-do-JWT_SECRET"
$env:CREDENTIALS_ENCRYPTION_KEY="nova-chave-gerada"
python -m scripts.reencrypt_credentials
```

O script recriptografa credenciais de integrações, APIs de transportadoras e segredos 2FA em todos os schemas. Só depois de concluí-lo, atualize o `.env`, remova `LEGACY_CREDENTIALS_ENCRYPTION_KEY` e rotacione `JWT_SECRET`. O script é transitório e pode ser excluído após a migração validada.

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
| `JWT_SECRET` | Assinatura dos tokens JWT (mínimo de 32 caracteres em produção) | `change-me` |
| `CREDENTIALS_ENCRYPTION_KEY` | Chave exclusiva para credenciais de integração e segredos 2FA | Sem padrão; obrigatória para criptografia e em produção |
| `JWT_ALGORITHM` | Algoritmo do JWT | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Expiração inicial do token | `60` |
| `LOGIN_RATE_LIMIT_WINDOW_SECONDS` | Janela do bloqueio de login em segundos | `900` |
| `LOGIN_RATE_LIMIT_EMAIL_ATTEMPTS` | Falhas permitidas por e-mail e tenant na janela | `5` |
| `LOGIN_RATE_LIMIT_IP_ATTEMPTS` | Falhas permitidas por IP e tenant na janela | `20` |
| `CORS_ORIGINS` | Lista JSON de origens autorizadas | `["http://localhost:5173"]` |
| `CNPJ_CONSULTA_BASE_URL` | Provedor de consulta cadastral | BrasilAPI |
| `CNPJ_CONSULTA_TIMEOUT_SECONDS` | Timeout da consulta de CNPJ | `10` |
| `TABELA_FRETE_STORAGE_DIR` | Armazenamento de documentos importados | `storage/tabelas_frete` |
| `TABELA_FRETE_UPLOAD_MAX_BYTES` | Limite por documento | `26214400` (25 MiB) |
| `EMPRESA_LOGO_STORAGE_DIR` | Armazenamento de logotipos | `storage/configuracoes/logos` |
| `EMPRESA_LOGO_MAX_BYTES` | Limite do logotipo | `2097152` (2 MiB) |
| `TIMEOUT_API_INTEGRACAO` | Timeout de integração via API | `15` segundos |
| `TIMEOUT_BROWSER_INTEGRACAO` | Timeout de automação de navegador | `60` segundos |
| `N8N_BASE_URL` | URL de uma futura/externa instância n8n | `http://n8n:5678` |

O Compose substitui `DATABASE_URL` para usar o hostname interno `postgres`. Os valores `JAMEF_API_KEY`, `JADLOG_TOKEN`, `BRASPRESS_USER`, `BRASPRESS_PASSWORD` e `PLAYWRIGHT_HEADLESS` presentes no exemplo são reservados para adapters/automação.

### Frontend

| Variável | Finalidade | Padrão |
| --- | --- | --- |
| `VITE_API_URL` | Prefixo da API consumida pelo navegador | `http://localhost:8000/api/v1` |

## Fluxos principais

### Cotação

1. O usuário informa origem, destino, nota fiscal, peso, volumes e transportadoras.
2. O backend recalcula a cubagem para não depender de valores enviados pelo navegador.
3. As consultas são executadas em paralelo e a cotação começa com status `processing`.
4. O frontend consulta o resultado até chegar a `completed`, `completed_with_errors` ou `failed`.
5. Uma proposta bem-sucedida pode ser selecionada como vencedora.

Transportadoras com `metodo_calculo=tabela_propria` utilizam a tabela ativa e vigente. Integrações do tipo API usam a configuração cadastrada; os demais métodos sem adapter disponível retornam um erro controlado.

### Tabela de frete

```text
draft → upload/análise → review → approved → active
                                    └──────→ cancelled
```

O documento passa por validação, extração e diagnóstico de confiança. Os dados podem ser revisados antes da aprovação. A ativação só é permitida depois que a tabela estiver aprovada.

## API

Todos os endpoints de negócio usam o prefixo `/api/v1` e, exceto o login e os health checks, exigem `Authorization: Bearer <token>`.

| Grupo | Endpoints principais |
| --- | --- |
| Autenticação | `POST /auth/login`, `GET /auth/me` |
| Dashboard | `GET /dashboard` |
| Cotações | `POST/GET /cotacoes`, `GET /cotacoes/{id}`, `POST /cotacoes/{id}/selecionar` |
| Transportadoras | CRUD em `/transportadoras`, consulta de CNPJ e configuração/status de API |
| Tabelas de frete | CRUD, upload, análise, revisão, aprovação, ativação, cancelamento e documentos em `/tabelas-frete` |
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

cd ../frontend
npm test
npm run build
```

O teste E2E cria uma tabela temporária, importa a fixture CSV, revisa, aprova, ativa e usa a tabela em uma cotação. Execute na raiz, com API, migrations e seed prontos:

```powershell
.\e2e\tabela_frete_flow.ps1
```

## Banco de dados e migrations

### Onboarding de novo cliente

Primeiro aplique a migration do catálogo isolado:

```bash
cd backend
alembic -c alembic_catalog.ini upgrade head
```

Depois provisione o database operacional, branding e administrador inicial em um único comando:

```bash
python -m app.provision_tenant \
  --codigo MODIAL \
  --nome "Modial" \
  --database-name frete_modial \
  --admin-email administrador@cliente.com \
  --admin-password "senha-temporaria-forte" \
  --primary-color "#2563EB" \
  --logo-url "https://cdn.exemplo.com/modial.svg"
```

O comando cria um banco físico, executa as migrations operacionais, cria somente o admin informado e registra no catálogo a URL criptografada. Não execute `app.seed` no banco provisionado. Entregue a senha temporária por canal seguro e troque-a no primeiro acesso.

### Atenção na transição do single-tenant

- O conteúdo atual de `tenants`/`company_themes` no banco operacional não é copiado para o novo catálogo. Cadastre novamente cada tenant com uma URL criptografada.
- Tenants antigos baseados em schemas não são roteados automaticamente. Crie um database por cliente e faça uma migração de dados separada antes de ativá-lo.
- Tokens antigos com claim `tsc` deixam de ser aceitos; todos os usuários precisam entrar novamente para receber `tid` e `tcd`.
- `POST /auth/login` agora exige `codigo_cliente`; clientes de API antigos precisam atualizar o payload.
- `python -m app.seed` continua existindo apenas para desenvolvimento e atua sobre `DATABASE_URL`; não o execute nos databases provisionados.
- Alterações na URL de um tenant exigem reinício dos processos do backend para invalidar o cache de engines atual.
- O provisionador pressupõe que o usuário de `DATABASE_URL` possa executar `CREATE DATABASE`; em PostgreSQL gerenciado, crie o database pela plataforma e adapte essa etapa.

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

## Segurança e produção

- [ ] `JWT_SECRET` exclusivo, aleatório e com pelo menos 32 caracteres; a API recusa iniciar em produção com valor vazio, curto ou `change-me`.
- [ ] `CREDENTIALS_ENCRYPTION_KEY` definida, com pelo menos 32 caracteres e diferente do `JWT_SECRET`; guarde-a em um gerenciador de segredos e faça backup antes de rotacioná-la.
- [ ] `CORS_ORIGINS` contém somente os domínios HTTPS efetivamente usados, sem `*`; uma configuração vazia ou curinga gera alerta no startup de produção.
- [ ] Rate limiting do login está ativo e dimensionado por `LOGIN_RATE_LIMIT_*`; para múltiplos workers/instâncias, substitua o armazenamento em memória por Redis para ter contagem compartilhada.
- [ ] Usuário/senha de administrador criados pelo seed foram removidos ou trocados imediatamente.
- [ ] HTTPS está habilitado na aplicação e nas APIs de transportadoras, com `COOKIE_SECURE=true`; o adapter genérico rejeita URLs inseguras.
- [ ] Arquivos `.env` e credenciais reais nunca são versionados.
- Persistir e proteger os diretórios de documentos/logotipos em produção.
- O frontend servido pelo Compose usa o servidor de desenvolvimento do Vite; para produção, gere `npm run build` e publique `frontend/dist` em um servidor web/CDN.
- Configure backup, observabilidade e rotação de segredos para o PostgreSQL e para as integrações.

### Deploy mínimo com Docker Compose

1. Copie `backend/.env.example` para `backend/.env`. Defina `ENVIRONMENT=production`, `COOKIE_SECURE=true`, `JWT_SECRET`, `CREDENTIALS_ENCRYPTION_KEY`, `DATABASE_URL`/`MASTER_DATABASE_URL`, `TRUSTED_HOSTS`, `CORS_ORIGINS` e as chaves das integrações utilizadas. Na raiz, defina `POSTGRES_PASSWORD` no arquivo `.env`.
2. Gere as imagens sem iniciar o servidor de desenvolvimento:

   ```bash
   docker compose -f docker-compose.prod.yml build
   ```

3. Inicie os bancos e aplique as duas cadeias de migrations:

   ```bash
   docker compose -f docker-compose.prod.yml up -d postgres catalog_postgres
   docker compose -f docker-compose.prod.yml run --rm backend alembic -c alembic_catalog.ini upgrade head
   docker compose -f docker-compose.prod.yml run --rm backend alembic -x database_per_tenant=true upgrade head
   ```

4. Inicie a aplicação:

   ```bash
   docker compose -f docker-compose.prod.yml up -d
   ```

Não execute `python -m app.seed` em produção. Esse comando cria dados de desenvolvimento, incluindo `admin@fretesystem.com`. Crie o administrador de produção por um procedimento controlado próprio, com senha temporária forte e troca obrigatória, e confirme que o usuário do seed não existe no banco.

### Backup dos dados persistentes

Crie backups regulares, mantenha cópias fora do host do Docker e teste a restauração. Para exportar o PostgreSQL em formato compactado:

```bash
mkdir -p backups
docker compose -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U frete -d frete -Fc > backups/frete-$(date +%Y%m%d-%H%M%S).dump
```

O volume `backend_storage` é montado em `/app/storage`; por padrão, `TABELA_FRETE_STORAGE_DIR=storage/tabelas_frete` fica dentro dele. Para preservar documentos importados e os demais arquivos persistidos:

```bash
docker compose -f docker-compose.prod.yml exec -T backend \
  tar -C /app/storage -czf - . > backups/frete-storage-$(date +%Y%m%d-%H%M%S).tar.gz
```

Faça o dump do banco e o arquivo do storage na mesma janela operacional. Antes de uma restauração, pare frontend e backend, valide os arquivos de backup e mantenha uma cópia anterior até confirmar a integridade dos dados restaurados.

## Observações atuais

- O Compose não inclui n8n nem Playwright; esses serviços precisam ser adicionados quando os respectivos adapters forem habilitados.
- O endpoint de histórico de uma tabela de frete ainda responde `501 Not Implemented`.
- A opção de exigir 2FA está modelada nas configurações, mas o fluxo de ativação de 2FA ainda não está disponível.
- Parte das transportadoras iniciais usa adapter simulado enquanto não houver configuração real de tabela/API.
