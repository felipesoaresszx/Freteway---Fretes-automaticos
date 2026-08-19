SELECT format(
    'CREATE ROLE %I LOGIN CREATEDB PASSWORD %L',
    :'app_user',
    :'app_password'
)
WHERE NOT EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname = :'app_user'
) \gexec

SELECT format(
    'CREATE DATABASE frete_catalog OWNER %I',
    :'app_user'
)
WHERE NOT EXISTS (
    SELECT 1 FROM pg_database WHERE datname = 'frete_catalog'
) \gexec
