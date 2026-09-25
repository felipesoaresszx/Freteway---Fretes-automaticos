# Agente de análise de tabelas de frete

## Auditoria da arquitetura existente

O fluxo foi implementado sobre os componentes existentes, sem criar um segundo motor:

- `TabelaFrete`, `DocumentoFrete` e `TabelaFreteDadosImportados` continuam sendo os registros de tabela, fontes originais e contrato persistido.
- `ProcessamentoJob` e `app.worker` continuam sendo a fila durável e o worker assíncrono.
- Os parsers existentes de PDF, Excel, CSV, Word e imagem continuam sendo a primeira camada de extração.
- `canonical_tariff_v2` e `tabela_frete_universal_v1` continuam sendo o contrato canônico consumido por `TabelaFreteCalculoService`.
- Os calculadores legados (Rodonaves, UF/zona, Transwells e contratos anteriores) foram preservados porque ainda são roteados pelo serviço de cálculo.
- `TabelaFreteAdapter` continua exigindo tabela ativa e vigente. O motor não recebe nenhuma informação sobre a origem por IA.

## Fluxo

1. `POST /api/v1/tabelas-frete` cria o rascunho.
2. Um ou dois documentos são persistidos por `POST /{id}/upload`.
3. `POST /{id}/analisar` cria um `ProcessamentoJob` e retorna imediatamente.
4. `TableAnalysisService` executa extração, detecção, IA opcional, normalização, validação e testes.
5. Cada etapa é gravada em `analise_tabela_eventos`; `GET /jobs/{job_id}` fornece progresso, histórico, falha e resumo.
6. O resultado fica em revisão. Regras ambíguas exigem confirmação humana explícita.
7. `POST /{id}/aprovar-publicar` repete validação/testes para contratos de IA, persiste o canônico, expira a versão ativa anterior e publica a nova em uma transação.
8. `POST /{id}/rollback` reativa a versão anterior ainda vigente, sem apagar versões.

## Isolamento da IA

`AIProvider` é uma porta assíncrona. A implementação `OpenAIResponsesProvider` usa saída JSON Schema, `store=false` e valida o resultado com Pydantic (`extra=forbid`). O provider recebe texto extraído e contexto da transportadora; não recebe conexão de banco, ferramentas, SQL nem função de publicação.

O resultado da IA é intermediário. `normalize_ai_analysis` o converte para `canonical_tariff_v2`; `validate_ai_contract` aplica regras determinísticas e `TableTestService` chama o calculador canônico em memória. Apenas o endpoint de aprovação pode publicar.

## Configuração

Por padrão, `AI_PROVIDER=disabled` preserva integralmente os parsers atuais. Para ativar o provider incluído no worker:

```env
AI_PROVIDER=openai
AI_API_KEY=...
AI_MODEL=gpt-5-mini
AI_BASE_URL=https://api.openai.com/v1
AI_TIMEOUT_SECONDS=120
AI_MAX_DOCUMENT_CHARS=120000
AI_MIN_CONFIDENCE=0.90
```

As chaves devem existir apenas no secret/env do backend e do worker. Elas não são retornadas pela API nem incluídas nos logs.

## Migração e operação

Execute `alembic upgrade head` antes de subir a nova versão. Backend e worker precisam compartilhar o mesmo banco, storage de documentos e configuração de IA. A interface consulta o job a cada segundo; não mantém a requisição de análise aberta.

## Validação e testes gerados

A validação cobre CEPs, UFs, faixas invertidas/sobrepostas, tarifas negativas, duplicidades geográficas, vigência, transportadora, baixa confiança, conflitos e lacunas. Os testes gerados exercitam início e fim das faixas e ausência de cobertura usando o motor canônico puro, sem gravar cotações ou alterar tabelas ativas.
