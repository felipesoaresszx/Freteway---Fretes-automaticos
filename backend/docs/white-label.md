# Identidade empresarial (white-label)

O acesso sempre inicia com a marca neutra FRETEWAY. `POST /api/v1/companies/identify`
normaliza e valida o código, registra a tentativa e grava o contexto em cookie HttpOnly
assinado. O token não é exposto ao JavaScript. `GET /api/v1/companies/context` restaura e
revalida a empresa; `DELETE /api/v1/companies/context` encerra o contexto.

## Configuração

- `TENANT_CONTEXT_EXPIRE_MINUTES`: validade do contexto pré-login (padrão: 10).
- `JWT_SECRET`: assina os tokens de contexto e autenticação.
- `COOKIE_SECURE=true`: obrigatório em produção HTTPS.
- `PLATFORM_ADMIN_API_KEY`: protege o cadastro administrativo.
- `MASTER_DATABASE_URL`: banco do control plane; usa `DATABASE_URL` quando omitido.

Execute `alembic upgrade head`. Configure a identidade por
`PUT /api/v1/platform/tenants/{tenant_id}/theme` com `X-Platform-API-Key`. Todas as
cores devem usar hexadecimal completo (`#RRGGBB`). URLs de logo, ícone e favicon devem
apontar para arquivos públicos acessíveis pelo navegador.

O frontend persiste somente um marcador de ID no `localStorage`. Tema, status e
roteamento são sempre recuperados novamente do backend; schema, conexão e credenciais
nunca fazem parte da resposta pública.
