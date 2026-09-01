# FRETEWAY — deploy seguro em produção

Este procedimento preserva o banco e o volume legado `frete-system_postgres_data`. Nenhum script executa `DROP`, `TRUNCATE`, downgrade, `docker compose down -v` ou remoção de volume. O restore não usa `--clean` e, por segurança, destina-se a banco novo/vazio.

## Auditoria e decisões

- O frontend tinha fallback para `http://localhost:8000/api/v1`; agora desenvolvimento usa `frontend/.env.development` e produção usa `/api/v1` em `frontend/.env.production`.
- O Compose local continua publicando apenas `127.0.0.1:5173` e `127.0.0.1:8000`.
- Produção publica somente 80/443 pelo Caddy; PostgreSQL, backend e frontend ficam nas redes Docker.
- O volume PostgreSQL de produção é externo e fixo em `frete-system_postgres_data`, impedindo que uma variável incorreta crie um banco aparentemente vazio.
- `TRUSTED_HOSTS`, CORS, cookies, banco e segredos vêm do ambiente. Produção rejeita curingas e segredos/cookies inseguros.
- `python -m app.bootstrap` cria somente o tenant/tema ausentes. Não cria nem inventa empresa, CNPJ, usuário, credenciais ou integrações e não sobrescreve dados existentes.
- O seed legado não integra o deploy: ele contém dados demonstrativos e uma credencial padrão, portanto não deve ser executado em produção.
- Não foi criada migration. O head permanece `024_doc_intel`; os scripts só executam `alembic upgrade head` depois do backup.

## Preparar o servidor

1. Aponte o registro DNS A de `app.freteway.com.br` para o IP público da VM e libere 80/443 no firewall/NSG.
2. Instale Git, Docker Engine e o plugin Docker Compose. Adicione o usuário de deploy ao grupo Docker conforme a política do host.
3. Clone o repositório. Copie `.env.production.example` para `.env.production` e `backend/.env.production.example` para `backend/.env.production`; use `chmod 600` nos dois.
4. Gere três valores independentes e estáveis: senha PostgreSQL, `JWT_SECRET` e `CREDENTIAL_ENCRYPTION_KEY`. Preencha `POSTGRES_PASSWORD_URLENCODED` com a mesma senha usando percent-encoding nos caracteres reservados (por exemplo, `@` vira `%40`). Não troque a chave de criptografia de uma instalação existente: isso pode tornar credenciais armazenadas ilegíveis.
5. Ajuste `DOMAIN`, `CORS_ORIGINS` e `TRUSTED_HOSTS` ao domínio/IP efetivo. Não use `*`. Mantenha `localhost` nos hosts confiáveis para o healthcheck interno.
6. Confirme com `docker volume ls` que `frete-system_postgres_data` existe. O deploy interrompe se ele estiver ausente. Nunca renomeie/remova esse volume sem dump validado.

### Migrar arquivos do bind mount atual

Antes de montar o volume de produção, confira `du -sh backend/storage` e liste uma amostra com `find backend/storage -maxdepth 3 -type f | head -30`. Se houver arquivos, execute:

```bash
chmod +x scripts/*.sh
./scripts/migrate_storage_to_volume.sh
```

O script cria primeiro `backups/storage_<timestamp>.tar.gz`, recusa copiar para volume não vazio, copia sem apagar a origem e valida a contagem. O deploy fica bloqueado quando encontra arquivos legados e o volume ainda não existe.

O Caddy fica desativado com `ACTIVATE_PROXY=false`, evitando conflito com o Nginx atual em `:80`. Somente na janela de troca, depois de validar backend/frontend e liberar 80/443, pare o Nginx, altere para `ACTIVATE_PROXY=true` e rode o deploy. O Caddy então obtém/renova TLS; certificados ficam no volume `caddy_data`, nunca no Git.

## Estratégia A — transportar o banco local

Com o PostgreSQL local ativo, use as variáveis/credenciais reais já configuradas, sem assumir `postgres/postgres`:

```bash
COMPOSE_FILE=docker-compose.yml ENV_FILE=.env ./scripts/backup_db.sh
```

Copie o `.dump` resultante para `backups/` no servidor por SCP/SFTP. Em um banco de destino novo/vazio, suba apenas o PostgreSQL e restaure:

```bash
docker compose --env-file .env.production -f docker-compose.production.yml up -d postgres
./scripts/restore_db.sh backups/freteway_AAAA-MM-DD_HHMMSS.dump
```

O dump custom preserva schemas, dados, sequences, constraints, IDs e UUIDs. O restore para no primeiro conflito e não limpa o destino. Se o destino já tiver dados, não tente mesclar automaticamente: faça novo backup de ambos e planeje uma migração específica.

Depois, valide antes de liberar tráfego:

```bash
docker compose --env-file .env.production -f docker-compose.production.yml exec postgres \
  sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT version_num FROM alembic_version; SELECT codigo_login, schema_name, ativo FROM public.tenants;"'
```

## Estratégia B — banco novo

O deploy cria o volume apenas após confirmação textual, aplica migrations e executa o bootstrap idempotente. `MODIAL2026` usa `public` por compatibilidade, a menos que `BOOTSTRAP_TENANT_SCHEMA` indique um schema já existente e corretamente migrado. Empresa principal e usuário não são inventados; cadastre-os depois com valores reais ou restaure o banco local.

```bash
chmod +x deploy/deploy.sh scripts/*.sh
./deploy/deploy.sh
```

O fluxo valida env/Compose, faz backup se o banco já estiver ativo, constrói imagens, sobe PostgreSQL, aplica migrations, executa bootstrap, sobe backend/worker/frontend/proxy e testa saúde. Qualquer erro interrompe o script sem apagar dados.

## Testar antes do deploy

```bash
cd backend && pytest
cd ../frontend && npm ci && npm run lint && npm test -- --run && npm run build
cd .. && ./scripts/check_frontend_bundle.sh
docker compose -f docker-compose.yml config --quiet
docker compose --env-file .env.production -f docker-compose.production.yml config --quiet
docker compose --env-file .env.production -f docker-compose.production.yml build
```

Um teste completo de migrations em banco vazio ou cópia do banco existente deve usar um volume descartável identificado exclusivamente para teste, nunca o volume local/produção. Faça dump primeiro e compare contagens de tabelas críticas antes/depois.

## Rollback

1. Preserve o dump pré-deploy e anote o commit anterior.
2. Volte o código ao commit anterior com Git e reconstrua os containers, mantendo o volume `frete-system_postgres_data` intacto.
3. Não execute `alembic downgrade`. Se o código anterior não aceitar o schema atualizado, avance o código ou restaure o dump em um banco/volume separado e validado; não sobrescreva o volume original.
4. Para incidente de frontend/backend sem mudança incompatível de schema: `git switch --detach <commit>` e execute novamente `./deploy/deploy.sh`.

## Reboot e observabilidade

Todos os serviços usam `restart: unless-stopped`. Após uma janela aprovada, reinicie a VM e valide `docker compose ... ps`, `/health`, `/api/v1/health/ready`, login, worker e logs. A reinicialização real da VM não é automatizada por este repositório.

## Checklist final

- [ ] backup local criado e restauração ensaiada
- [ ] backup do servidor criado
- [ ] `.env.production` e `backend/.env.production` protegidos
- [ ] segredos reais fora do Git e chaves antigas preservadas
- [ ] volume PostgreSQL existente confirmado pelo nome
- [ ] migrations testadas em banco vazio e cópia do banco existente
- [ ] bootstrap idempotente executado duas vezes
- [ ] frontend build concluído e sem `localhost:8000`/`127.0.0.1:8000`
- [ ] trusted hosts e CORS restritos
- [ ] proxy, DNS e HTTPS válidos
- [ ] healthchecks saudáveis
- [ ] worker processando e reiniciando
- [ ] PostgreSQL persistente e acessível somente internamente
- [ ] login `MODIAL2026`, contexto, autenticação e logout validados
- [ ] empresas e vínculos validados com valores reais
- [ ] transportadoras e tabelas de frete validadas
- [ ] Sankhya, SSW e demais APIs validadas sem regravar credenciais
- [ ] importação/visualização de documentos e storage persistente validados
- [ ] cotações, jobs, enriquecimento e histórico validados
- [ ] logs e rotação verificados
- [ ] serviços retornam após reboot
