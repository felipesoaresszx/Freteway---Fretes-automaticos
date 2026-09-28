# Motores de calculo de frete

## Garantias de compatibilidade

- A ausencia de `carrier_calculation_configs` significa `LEGACY` e shadow desligado.
- Nenhuma migracao cria configuracoes para transportadoras existentes.
- `LegacyFreightCalculator` delega para `TabelaFreteCalculoService`; as formulas existentes nao foram movidas.
- O contrato de resposta do Sankhya continua sendo produzido por `SankhyaQuoteProvider`.
- O motor `NEW` aceita inicialmente apenas tabelas `canonical_freight_v1` ativas.

## Configuracao

Consultar:

```http
GET /api/v1/transportadoras/{carrier_id}/calculation-config
```

Ativar shadow mantendo o legado oficial:

```json
{
  "calculation_engine": "LEGACY",
  "shadow_calculation": true,
  "new_engine_version": "canonical-v1"
}
```

Ativar o novo motor depois da homologacao:

```json
{
  "calculation_engine": "NEW",
  "shadow_calculation": false,
  "new_engine_version": "canonical-v1"
}
```

Rollback sem deploy:

```json
{
  "calculation_engine": "LEGACY",
  "shadow_calculation": false,
  "new_engine_version": null
}
```

Os tres payloads usam:

```http
PUT /api/v1/transportadoras/{carrier_id}/calculation-config
```

Selecionar `NEW` e bloqueado quando a transportadora nao usa tabela propria ou nao possui uma
tabela ativa `canonical_freight_v1`.

## Shadow

O resultado LEGACY e devolvido imediatamente. O novo calculo e persistido como job
`freight_shadow` e executado pelo worker em outra sessao de banco. Falhas ou divergencias do
shadow nao alteram o valor oficial.

Consultar as comparacoes:

```http
GET /api/v1/transportadoras/{carrier_id}/calculation-audits?limit=50
```

Cada auditoria contem motor oficial, tabela e versao, duracao, resultado estruturado, trace,
resultado shadow e diferencas por componente.

## Implantacao segura

1. Fazer backup do banco.
2. Aplicar `alembic upgrade head` antes de subir API e worker.
3. Confirmar que transportadoras sem configuracao retornam `is_default=true` e `LEGACY`.
4. Ativar shadow em uma unica transportadora de homologacao.
5. Acompanhar `freight_calculation_audits` e os logs `freight_shadow_completed`.
6. Migrar para `NEW` somente depois de aprovar os baselines.
7. Em caso de divergencia, executar o payload de rollback acima.

## Escopo do primeiro motor novo

O primeiro motor reutiliza o contrato deterministico `canonical_freight_v1` e suporta somente
as regras ja implementadas nele: destino, faixa de peso, cubagem, excedente, GRIS, ad valorem,
pedagio, TAS, adicionais de localidade e ICMS quando resolvido. Outros formatos continuam no
legado e nao recebem fallback silencioso no motor novo.
