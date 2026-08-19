#!/bin/bash
set -euo pipefail
exec > >(tee /var/log/freteway-bootstrap.log) 2>&1

AWS_REGION="${AWS_REGION:?}"
ARTIFACT_BUCKET="${ARTIFACT_BUCKET:?}"
ARTIFACT_KEY="${ARTIFACT_KEY:?}"
RDS_ENDPOINT="${RDS_ENDPOINT:?}"
RDS_SECRET_ARN="${RDS_SECRET_ARN:?}"
APP_DB_SECRET_ARN="${APP_DB_SECRET_ARN:?}"
JWT_SECRET_ARN="${JWT_SECRET_ARN:?}"
CREDENTIALS_KEY_ARN="${CREDENTIALS_KEY_ARN:?}"
ADMIN_SECRET_ARN="${ADMIN_SECRET_ARN:?}"
PUBLIC_IP="${PUBLIC_IP:?}"

dnf install -y docker postgresql15 jq unzip
systemctl enable --now docker
mkdir -p /opt/freteway
aws s3 cp "s3://${ARTIFACT_BUCKET}/${ARTIFACT_KEY}" /tmp/freteway.zip --region "$AWS_REGION"
unzip -q -o /tmp/freteway.zip -d /opt/freteway
install -m 0755 /opt/freteway/tools/asm-exec /usr/local/bin/asm-exec
cd /opt/freteway/app

export AWS_REGION AWS_DEFAULT_REGION="$AWS_REGION"
MASTER_USER="{{resolve:secretsmanager:${RDS_SECRET_ARN}:SecretString:username}}"
MASTER_PASSWORD="{{resolve:secretsmanager:${RDS_SECRET_ARN}:SecretString:password}}"
APP_USER="{{resolve:secretsmanager:${APP_DB_SECRET_ARN}:SecretString:username}}"
APP_PASSWORD="{{resolve:secretsmanager:${APP_DB_SECRET_ARN}:SecretString:password}}"

asm-exec -- env PGPASSWORD="$MASTER_PASSWORD" psql -v ON_ERROR_STOP=1 -h "$RDS_ENDPOINT" -U "$MASTER_USER" -d postgres \
  -v app_user="$APP_USER" -v app_password="$APP_PASSWORD" -f /opt/freteway/app/infra/aws/init-databases.sql

PUBLIC_HOST="${PUBLIC_IP//./-}.sslip.io"
DB_BASE="postgresql+asyncpg://${APP_USER}:${APP_PASSWORD}@${RDS_ENDPOINT}:5432"
asm-exec -- env \
  DB_BASE="$DB_BASE" \
  JWT_SECRET="{{resolve:secretsmanager:${JWT_SECRET_ARN}:SecretString:value}}" \
  CREDENTIALS_KEY="{{resolve:secretsmanager:${CREDENTIALS_KEY_ARN}:SecretString:value}}" \
  ADMIN_KEY="{{resolve:secretsmanager:${ADMIN_SECRET_ARN}:SecretString:password}}" \
  PUBLIC_HOST="$PUBLIC_HOST" \
  sh -c 'umask 077; cat > backend/.env.aws <<EOF
ENVIRONMENT=production
DATABASE_URL=${DB_BASE}/postgres?ssl=require
MASTER_DATABASE_URL=${DB_BASE}/postgres?ssl=require
CATALOG_DATABASE_URL=${DB_BASE}/frete_catalog?ssl=require
JWT_SECRET=${JWT_SECRET}
CREDENTIALS_ENCRYPTION_KEY=${CREDENTIALS_KEY}
PLATFORM_ADMIN_API_KEY=${ADMIN_KEY}
COOKIE_SECURE=true
TRUSTED_HOSTS=["${PUBLIC_HOST}"]
CORS_ORIGINS=["https://${PUBLIC_HOST}"]
TABELA_FRETE_STORAGE_DIR=/app/storage
EOF
chmod 600 backend/.env.aws'

set -a
. backend/.env.aws
set +a
docker compose -f docker-compose.aws.yml run --rm backend alembic -c alembic_catalog.ini upgrade head

if ! asm-exec -- env PGPASSWORD="$APP_PASSWORD" psql -h "$RDS_ENDPOINT" -U "$APP_USER" -d frete_catalog -tAc \
  "SELECT 1 FROM tenants WHERE codigo_login='FRETEWAY'" | grep -q 1; then
  asm-exec -- docker compose -f docker-compose.aws.yml run --rm backend python -m app.provision_tenant \
    --codigo FRETEWAY --nome FreteWay --database-name freteway_main \
    --admin-email "{{resolve:secretsmanager:${ADMIN_SECRET_ARN}:SecretString:email}}" \
    --admin-password "{{resolve:secretsmanager:${ADMIN_SECRET_ARN}:SecretString:password}}" \
    --primary-color '#2563EB'
fi

printf 'PUBLIC_HOST=%s\n' "$PUBLIC_HOST" > .env.aws
docker compose --env-file .env.aws -f docker-compose.aws.yml up --build -d
docker image prune -f

