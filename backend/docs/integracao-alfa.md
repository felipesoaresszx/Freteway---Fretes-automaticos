# Integração Alfa Transportes

## Status da Integração

**Status:** Implementada e pronta para homologação  
**Tipo:** API  
**Adapter Code:** `alfa`  
**Transportadora Code:** `alfa`  
**Revisão:** 027_alfa_carrier

---

## Situação

A Alfa Transportes confirma que possui integração por API e que a API de cotação depende de **liberação dos setores regional e comercial**.

### Informações Confirmadas Oficialmente pela Alfa

- Possui API de cotação
- Acesso depende de liberação regional/comercial

### Informações Descobertas na Implementação Pública

A partir de implementações públicas descobertas, identificamos o seguinte endpoint de cotação:

- **Endpoint:** `GET https://api.alfatransportes.com.br/cotacao/`
- **Autenticação:** API Key enviada como parâmetro `idr` na URL
- **Formato:** Parâmetros na query string
- **Resposta:** JSON com estrutura de cotação

**IMPORTANTE:** Estas informações são baseadas em implementações públicas e **NÃO são oficialmente confirmadas pela Alfa**. Devem ser validadas junto à transportadora antes da homologação.

---

## Implementação no FreteWay

### Arquitetura

A integração segue o padrão do FreteWay:

```
Carrier
    ↓
CarrierIntegration (API)
    ↓
CarrierAdapter (CarrierAdapter)
    ↓
AlfaProvider
    ↓
AlfaClient
    ↓
HTTP API Alfa
```

### Componentes

| Componente | Arquivo | Responsabilidade |
|-----------|---------|-----------------|
| Schemas | `app/integrations/alfa/schemas.py` | Validação de credenciais, request e response |
| Exceptions | `app/integrations/alfa/exceptions.py` | Tratamento de erros normalizados |
| Client | `app/integrations/alfa/client.py` | Chamadas HTTP com retry e timeout |
| Mapper | `app/integrations/alfa/mapper.py` | Conversão entre modelos FreteWay e Alfa |
| Provider | `app/integrations/alfa/provider.py` | Implementação do CarrierAdapter |
| Registry | `app/integrations/transportadoras/registry.py` | Registro do adapter `alfa` |
| Migration | `alembic/versions/027_alfa_carrier.py` | Criação da transportadora e integração |

---

## Como Cadastrar

### 1. Executar Migração

```bash
# A migração 027_alfa_carrier já cria a transportadora e integração
alembic upgrade head
```

### 2. Configurar Credenciais

**Via API:**

```bash
# Criar transportadora (já criado pela migração)
POST /api/v1/carriers
{
  "code": "alfa",
  "name": "Alfa Transportes",
  "legal_name": "Alfa Transportes Ltda",
  "cnpj": "04917818000124"
}

# Criar integração API (já criado pela migração)
POST /api/v1/carriers/alfa/integrations
{
  "integration_type": "API",
  "adapter_code": "alfa",
  "active": true,
  "priority": 100,
  "configuration": {}
}

# Configurar credenciais
PUT /api/v1/carriers/alfa/integrations/{integration_id}/credentials
{
  "credentials": {
    "api_key": "SUA_API_KEY_ALFA",
    "base_url": "https://api.alfatransportes.com.br",
    "endpoint": "/cotacao/",
    "login": "",  # Opcional
    "password": ""  # Opcional
  }
}
```

**Credenciais Armazenadas:**
- As credenciais são criptografadas em repouso usando Fernet (chave derivada do JWT_SECRET ou CREDENTIAL_ENCRYPTION_KEY)
- Nunca são logadas ou expostas em respostas da API
- A API Key é mascarada em logs e metadata

### 3. Testar Conexão

```bash
POST /api/v1/carriers/alfa/integrations/{integration_id}/validate
```

Resposta esperada:
```json
{
  "success": true,
  "message": "Conexão com Alfa Transportes realizada com sucesso."
}
```

### 4. Testar Cotação

```bash
POST /api/v1/carriers/alfa/integrations/{integration_id}/quote
{
  "origin_zipcode": "07042-180",
  "destination_zipcode": "19500-000",
  "weight_kg": 29.0,
  "volumes": 1,
  "total_value": 5668.00,
  "cubage_m3": 0.0832,
  "products": [
    {"documento_destinatario": "24526470000151"}
  ]
}
```

Resposta esperada:
```json
[
  {
    "carrier_id": "...",
    "carrier_name": "Alfa Transportes",
    "service_id": null,
    "service_name": "Alfa Transportes",
    "price": 113.11,
    "delivery_days": 6,
    "source": "carrier_api",
    "external_service_code": null,
    "metadata": {
      "provider": "Alfa Transportes"
    }
  }
]
```

---

## Parâmetros da API

### Request (GET Query Parameters)

| Parâmetro | Tipo | Obrigatório | Descrição |
|-----------|------|------------|-----------|
| `idr` | string | Sim | API Key / IDR |
| `cliTip` | string | Sim | Tipo de cliente: `1` = Jurídica, `0` = Física |
| `cepRem` | string | Sim | CEP de origem (8 dígitos) |
| `cliCep` | string | Sim | CEP de destino (8 dígitos) |
| `cliCnpj` | string | Não | CNPJ do destinatário (14 dígitos) |
| `merVlr` | float | Sim | Valor da mercadoria/NF |
| `merPeso` | float | Sim | Peso tarifável (kg) |
| `merM3` | float | Sim | Cubagem total (m³) |
| `modoJson` | string | Sim | Formato: `1` (JSON) |

### Response (JSON)

```json
{
  "cotacao": {
    "emissao": {
      "diasEntrega": 6,
      "valoresCotacao": {
        "valorTotal": 113.11
      }
    }
  }
}
```

### Mapeamento FreteWay → Alfa

```
FreightQuoteRequest:
  origin_zipcode  →  cepRem (sanitizado)
  destination_zipcode → cliCep (sanitizado)
  products[0].documento_destinatario → cliCnpj (sanitizado)
    - Se CNPJ (14 dígitos): cliTip = "1"
    - Se CPF (11 dígitos) ou vazio: cliTip = "0"
  total_value → merVlr (float)
  weight_kg → merPeso (float)
  cubage_m3 → merM3 (float, 0 se None)

Credenciais:
  api_key → idr
  base_url → URL base (default: https://api.alfatransportes.com.br)
  endpoint → endpoint (default: /cotacao/)
  modo_json → "1" (fixo)
```

---

## Tratamento de Erros

### Códigos de Erro Normalizados

| Erro | Descrição | HTTP Status |
|------|-----------|-------------|
| `AlfaAuthenticationError` | Credencial inválida ou acesso negado | 401, 403 |
| `AlfaRateLimitError` | Limite de requisições excedido | 429 |
| `AlfaInvalidRequestError` | Requisição inválida | 400 |
| `AlfaNoQuoteError` | Nenhuma cotação disponível | 200 (sem cotacao) |
| `AlfaResponseError` | Resposta inválida (JSON, estrutura) | 200 |
| `AlfaConnectionError` | Falha de conexão | 500+, 404 |
| `AlfaTimeoutError` | Timeout na requisição | - |

### Logging

Os logs seguem o padrão:

```
carrier_quote carrier=ALFA operation=quote status=success/error duration_ms=123 freight_value=113.11
carrier_request carrier=ALFA operation=quote status=timeout/connection_error attempt=1 error=TimeoutError
```

**Nunca são logados:**
- API Key
- Senha
- Credenciais
- URLs completas com credenciais (parâmetro `idr` é mascarado)

---

## Configuração

### Variáveis de Ambiente

```bash
# Configuração global do FreteWay
TIMEOUT_API_INTEGRACAO=15          # Timeout em segundos
INTEGRATION_RETRY_ATTEMPTS=3       # Tentativas de retry
CREDENTIAL_ENCRYPTION_KEY=...      # Chave de criptografia (recomendado)
```

### Configuração por Transportadora

A integração Alfa pode ser configurada com:

```python
# Em carrier_management.py
configuration = {
    "base_url": "https://api.alfatransportes.com.br",
    "endpoint": "/cotacao/",
    "timeout": 15,  # Sobrescreve global
    "retry_attempts": 3
}
```

---

## Testes

### Testes Unitários

Localizados em: `tests/test_alfa_provider.py`

Cobrem:
1. Validação de credenciais
2. Sanitização de CEP
3. Sanitização de documentos
4. Determinação de tipo de cliente (CNPJ -> 1, CPF -> 0)
5. Montagem da query
6. Parse da resposta
7. Tratamento de erros HTTP (400, 401, 403, 404, 429, 500)
8. Timeout
9. JSON inválido
10. Resposta sem valorTotal
11. Resposta sem diasEntrega
12. Cotação bem-sucedida
13. Mascaramento de credenciais

Executar:
```bash
pytest tests/test_alfa_provider.py -v
```

### Testes de Integração Live

Localizados em: `tests/integration/test_alfa_live.py`

Requerem:
- Ambiente de homologação (`FRETEWAY_ENV=homologation`)
- Credenciais válidas (`ALFA_API_KEY`)
- Acesso liberado pela Alfa

Executar:
```bash
FRETEWAY_ENV=homologation ALFA_API_KEY=your_key pytest tests/integration/test_alfa_live.py -v
```

**NOTA:** Estes testes são pulados automaticamente em CI/CD.

---

## Teste de Homologação

### Dados para Teste

```
Origem: CEP 07042-180
Destino: CEP 19500-000
CNPJ Destinatário: 24.526.470/0001-51
Valor NF: R$ 5.668,00
Peso: 29 kg
Cubagem: 0,0832 m³
Volumes: 1
```

### Resultado Esperado

```
HTTP válido (200)
Resposta JSON
cotacao.emissao.diasEntrega presente
cotacao.emissao.valoresCotacao.valorTotal presente
Conversão para FreightQuoteResult
```

### Comparação com Motor de Tabelas

Para comparar a cotação da API Alfa com o motor de tabela do FreteWay:

1. Obter cotação via API Alfa
2. Obter cotação via tabela (se cadastrada)
3. Comparar valores e prazos

**IMPORTANTE:** A comparação NÃO altera automaticamente os valores do motor. É apenas uma ferramenta de validação.

---

## Segurança

### Checklist de Segurança

- Credenciais armazenadas criptografadas (Fernet)
- Credenciais nunca expostas em logs
- Credenciais nunca expostas em respostas da API
- Credenciais nunca expostas no frontend
- API Key mascarada em metadata de respostas
- URLs completas com credenciais no log (parâmetro idr mascarado)

### Requisitos de Produo

```bash
# O FreteWay exige em produo:
CREDENTIAL_ENCRYPTION_KEY= [32+ caracteres, diferente de JWT_SECRET]
ENVIRONMENT=production
PUBLIC_BASE_URL=https://...
COOKIE_SECURE=true
ALLOW_INSECURE_HTTP=false
```

---

## Mensagem para Solicitao

**Assunto:** Liberao e documentao da API de Cotao — Modial

Ola, equipe Alfa Transportes.

Estamos integrando o sistema de gesto de fretes **FreteWay**  Alfa Transportes para realizar cotaoes automticas usando o contrato comercial da **Modial (CNPJ 04.917.818/0001-24)**.

**Solicitamos:**

1. **Liberao da API de cotao** junto aos setores regional e comercial
2. **Chave exclusiva** para a Modial (API Key / IDR)
3. **Documentao tcnica atualizada** contendo:
   - URLs de homologao e produo
   - Mtodo de autenticao (atualmente desconhecemos se apenas `idr` ou se requer login/senha)
   - Endpoint completo de cotao
   - Modelo completo do request (todos os parmetros obrigatrios e opcionais)
   - Modelo completo do response (todos os campos e suas estruturas)
   - Tipos de dados, unidades e casas decimais
   - Identificao do CNPJ pagador/remetente (CNPJ da Modial)
   - Cdigos de servio/modalidade disponveis
   - Limites de requisio (rate limiting)
   - Timeout recomendado
   - Poltica de retentativa
   - Catlogo de erros e exemplos de sucesso e falha

**Nossa implementao:**

- Armazenamento criptografado de credenciais
- Timeout configurvel (padro: 15 segundos)
- Retentativas com backoff para erros transitrios
- Auditoria e logging seguro (sem credenciais)
- Tratamento de indisponibilidade
- Mapeamento para modelo cannico do FreteWay

**Ambiente atual:**
- Usamos como base: `https://api.alfatransportes.com.br/cotacao/`
- Enviamos `idr` como API Key na URL
- Esperamos response JSON com `cotacao.emissao.valoresCotacao.valorTotal`

**Informaes para confirmao:**
- O CNPJ da Modial (04.917.818/0001-24) est habilitado para cotao?
- Est vinculado  tabela/negociao comercial correta?
- H necessidade de liberao de IP?
- A autenticao requer apenas `idr` ou tambm login/senha?

Assim que recebermos o contrato tcnico e a chave, concluiremos a homologao.

Obrigado.
