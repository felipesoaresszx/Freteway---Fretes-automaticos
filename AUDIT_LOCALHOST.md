# Auditoria global de URLs e ambiente

Escopo pesquisado: Python, TypeScript/JavaScript, JSON, Compose/YAML, arquivos de ambiente, Dockerfiles, shell/PowerShell, Markdown, Nginx e Caddy. Foram excluídos apenas `.git`, `node_modules`, `dist`, `build` e caches. O inventário abaixo classifica todas as referências locais relevantes; URLs HTTPS de Sankhya, SSW, Jamef, Risso/Senior, Correios, BrasilAPI, ANTT e mecanismos de pesquisa são endpoints externos legítimos e foram preservados.

## Ocorrências locais mantidas

| Arquivo/valor | Classificação | Motivo |
|---|---|---|
| `frontend/.env.development`: `http://localhost:8000/api/v1` | desenvolvimento legítimo | Vite local chama o backend local. |
| `frontend/.env.example`: mesma URL | documentação/desenvolvimento | Exemplo local, nunca usado pelo build de produção. |
| `docker-compose.yml`: `127.0.0.1:8000`, `127.0.0.1:5173` e URL Vite local | desenvolvimento legítimo | Bind restrito ao loopback do host; mantém o fluxo local. |
| `backend/.env.example` e defaults em `app/core/config.py` | desenvolvimento legítimo | Banco/CORS/hosts locais são defaults de desenvolvimento e são substituídos por env em produção. |
| `backend/alembic.ini`: URL placeholder localhost | desenvolvimento legítimo | `alembic/env.py` sempre substitui pelo `Settings.DATABASE_URL`. |
| `.github/workflows/ci.yml`: PostgreSQL em localhost | teste | Serviço PostgreSQL do runner CI. |
| `e2e/tabela_frete_flow.ps1`: API localhost | teste | Default parametrizável por `ApiBase`. |
| testes de company/TrustedHost: `127.0.0.1`/`localhost` | teste | Exercitam contexto e política de host. |
| `backend/app/core/url_security.py`: bloqueio de localhost | segurança | Impede SSRF contra loopback; não é endpoint de produção. |
| `backend/Dockerfile` e README: `0.0.0.0:8000` | runtime/documentação | Endereço de escuta dentro do container, não URL do navegador. |
| Compose/Dockerfile de produção: health em `127.0.0.1` | produção legítima | Loopback interno do próprio container; permitido em `TRUSTED_HOSTS`. |
| README e `DEPLOYMENT.md`: URLs localhost | documentação | Instruções locais e descrição do risco, não código executável. |
| `deploy/Caddyfile`: `backend:8000` | produção legítima | DNS interno Docker, nunca exposto ao navegador. |
| `N8N_BASE_URL=http://n8n:5678` | serviço interno | Hostname interno Docker/configurável, não localhost. |

## Ocorrências corrigidas

| Origem | Antes | Depois | Classificação |
|---|---|---|---|
| `frontend/src/api/client.ts` | fallback absoluto `http://localhost:8000/api/v1` | módulo único `runtimeConfig`, fallback `/api/v1` | hardcoded incorreto removido |
| Build Vite | dependia do ambiente genérico | `.env.production`, `.env.production.example` e build arg `/api/v1` | produção |
| Verificação de bundle | cobria apenas backend `:8000` | bloqueia localhost/127.0.0.1 nas portas 8000 e 5173 | teste de produção |
| Health backend/frontend | `localhost` | `127.0.0.1` e hosts internos permitidos | produção |
| Hosts/CORS/cookies | defaults locais dispersos | `Settings` + env, validação sem `*`, `COOKIE_SECURE`, SameSite e Domain | produção |
| URL pública futura | inexistente | `PUBLIC_BASE_URL` centralizado e HTTPS obrigatório em produção | produção |
| Storage | paths relativos/defaults | envs explícitos e volume `/app/storage` | produção |
| PostgreSQL de produção | volume configurável poderia apontar para outro banco | volume externo fixo `frete-system_postgres_data` | proteção de dados |

## Resultados negativos relevantes

- Nenhum WebSocket (`ws://`, `wss://` ou implementação WebSocket) encontrado.
- Nenhum OAuth `redirect_uri`/callback interno do FRETEWAY encontrado.
- Nenhuma URL absoluta de download, documento, logo ou relatório gerada com localhost.
- Nenhuma referência ao IP `64.181.183.229:8000` encontrada no código.
- Nenhum path absoluto `C:\...` ou `/home/...` usado pelo runtime versionado.
- Nenhuma migration foi alterada ou criada nesta correção.
