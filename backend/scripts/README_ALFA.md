# Setup Rápido: Alfa Transportes

## 🚀 Opções para Configurar

### Opção 1: Usar o Endpoint de Setup (Recomendado)

**Endpoint:** `POST /api/v1/alfa-setup/configure`

```bash
curl -X POST "http://localhost:8000/api/v1/alfa-setup/configure" \
  -H "Authorization: Bearer SEU_TOKEN_ADMIN" \
  -H "Content-Type: application/json" \
  -d '{
    "api_key": "SUA_CHAVE_ALFA"
  }'
```

**Parâmetros opcionais:**
- `base_url`: URL base (default: `https://api.alfatransportes.com.br`)
- `endpoint`: Endpoint (default: `/cotacao/`)

**Resposta:**
```json
{
  "success": true,
  "message": "Alfa Transportes configurada com sucesso!",
  "carrier_id": "00000000-0000-4000-8000-000000000027",
  "integration_id": "00000000-0000-4000-8000-000000000127",
  "status": "configured",
  "next_steps": [...]
}
```

---

### Opção 2: Executar Script Completo

```bash
# Dar permissão
chmod +x scripts/setup_alfa_complete.sh

# Executar (no diretório backend/)
./scripts/setup_alfa_complete.sh
```

O script:
1. Executa a migração (se necessário)
2. Solicita a API Key interativamente
3. Configura tudo automaticamente
4. Mostra os próximos passos

---

### Opção 3: Executar Script Python

```bash
# No diretório backend/
python3 scripts/setup_alfa.py
```

O script:
1. Cria/obtém a transportadora Alfa
2. Cria/obtém a integração API
3. Solicita a API Key de forma segura (getpass)
4. Salva credenciais criptografadas
5. Testa a conexão
6. Atualiza status

---

### Opção 4: Manual (Via UI do FreteWay)

1. **Executar migração:**
   ```bash
   cd backend
   alembic upgrade head
   ```

2. **Acessar UI:**
   - Acesse: `http://localhost:5173/` (frontend)
   - Vá em: **Transportadoras**
   - Localize: **Alfa Transportes** (já estará na lista)

3. **Configurar credenciais:**
   - Clique em: **Integrações**
   - Clique em: **[ Editar Credenciais ]** ou **[ Salvar Credenciais ]**
   - Preencha:
     - **API Key:** a chave IDR fornecida pela Alfa
     - **Base URL:** `https://api.alfatransportes.com.br`
     - **Endpoint:** `/cotacao/`
   - Clique em: **Salvar**

4. **Testar conexão:**
   - Clique em: **[ Testar conexão ]**
   - Deve aparecer: ✅ "Conexão com Alfa Transportes realizada com sucesso."

5. **Ativar transportadora:**
   - Clique em: **[ Ativar ]** ou **[ Salvar ]**

---

## 📋 Verificar Status

Para verificar se a Alfa está configurada:

```bash
curl -X GET "http://localhost:8000/api/v1/alfa-setup/status" \
  -H "Authorization: Bearer SEU_TOKEN_ADMIN"
```

**Resposta (configurada):**
```json
{
  "configured": true,
  "carrier_id": "00000000-0000-4000-8000-000000000027",
  "carrier_name": "Alfa Transportes",
  "carrier_active": true,
  "integration_id": "00000000-0000-4000-8000-000000000127",
  "integration_status": "configured",
  "integration_active": true,
  "has_credentials": true,
  "ready_for_quoting": true
}
```

---

## 🧪 Testar Cotação

Após configurar, teste uma cotação:

```bash
curl -X POST "http://localhost:8000/api/v1/carriers/alfa/integrations/{INTEGRATION_ID}/quote" \
  -H "Authorization: Bearer SEU_TOKEN_ADMIN" \
  -H "Content-Type: application/json" \
  -d '{
    "origin_zipcode": "07042-180",
    "destination_zipcode": "19500-000",
    "weight_kg": 29,
    "volumes": 1,
    "total_value": 5668.00,
    "cubage_m3": 0.0832,
    "products": [
      {"documento_destinatario": "24526470000151"}
    ]
  }'
```

**Resposta esperada:**
```json
[{
  "carrier_id": "00000000-0000-4000-8000-000000000027",
  "carrier_name": "Alfa Transportes",
  "service_name": "Alfa Transportes",
  "price": 113.11,
  "delivery_days": 6,
  "source": "carrier_api"
}]
```

---

## 📝 Dados para Teste de Homologação

| Campo | Valor | Tipo |
|-------|-------|------|
| CEP Origem | 07042-180 | CEP |
| CEP Destino | 19500-000 | CEP |
| CNPJ Destinatário | 24.526.470/0001-51 | CNPJ |
| Valor NF | 5668.00 | Decimal |
| Peso | 29 kg | Decimal |
| Cubagem | 0.0832 m³ | Decimal |
| Volumes | 1 | Integer |

---

## 🔒 Segurança

✅ **Todas as credenciais são:**
- Passadas no **body da requisição** (NÃO na URL)
- **Criptografadas** antes de serem armazenadas (Fernet AES-128)
- **NUNCA** exibidas em logs ou respostas
- Armazenadas em `carrier_credentials.encrypted_payload`

✅ **A API Key NÃO está armazenada em:**
- Código-fonte
- Git/Commits
- Frontend
- Arquivos de configuração

---

## 🛠️ Solução de Problemas

### Erro: "Transportadora não encontrada"
**Solução:** Execute a migração:
```bash
alembic upgrade head
```

### Erro: "Integração não encontrada"
**Solução:** Verifique se a migração foi executada. A integração deve ter `adapter_code = 'alfa'`.

### Erro: "Credenciais inválidas"
**Solução:** Verifique:
1. A API Key está correta
2. A Base URL está correta
3. A Alfa liberou acesso para o CNPJ da Modial (04.917.818/0001-24)

### Erro: "Endpoint não encontrado"
**Solução:** Verifique se o endpoint está correto. Teste manualmente:
```bash
curl "https://api.alfatransportes.com.br/cotacao/?idr=YOUR_API_KEY&cliTip=1&cepRem=07042180&cliCep=19500000&cliCnpj=24526470000151&merVlr=5668&merPeso=29&merM3=0.0832&modoJson=1"
```

---

## 📚 Documentação Completa

Consulte: `/backend/docs/integracao-alfa.md`

---

## 🎯 Resumo

| Ação | Comando | Status |
|------|---------|--------|
| Executar migração | `alembic upgrade head` | ✅ |
| Configurar API Key | `POST /api/v1/alfa-setup/configure` | ✅ |
| Verificar status | `GET /api/v1/alfa-setup/status` | ✅ |
| Testar conexão | `POST /carriers/alfa/integrations/{id}/validate` | ✅ |
| Fazer cotação | `POST /carriers/alfa/integrations/{id}/quote` | ✅ |

**Tudo pronto! A Alfa Transportes está configurada e pronta para uso.** 🎉
