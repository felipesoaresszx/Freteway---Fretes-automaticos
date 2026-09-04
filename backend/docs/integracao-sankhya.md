# Integração Sankhya → FreteWay

## Cotação

`POST /integracoes/sankhya/cotacao` (aliases: `/integrations/sankhya/cotacao` e
`/api/v1/integrations/sankhya/cotacao`). A autenticação usa `X-API-Key`. Em
ambientes multi-tenant, a chave identifica o cliente e seleciona seu schema.

Contrato recomendado:

```json
{
  "NUNOTA": 21259,
  "CODEMP": 1,
  "CepOrigem": "01001-000",
  "CepDestino": "30110-000",
  "VlrNota": 6781.00,
  "Volumes": [{
    "Quantidade": 2,
    "Peso": 12.5,
    "Altura": 30,
    "Largura": 40,
    "Comprimento": 50
  }]
}
```

Também são aceitos os nomes internos `numero_pedido`, `empresa_sankhya_id`,
`valor_mercadoria`, `origem`, `destino` e `itens`. Cidade e UF podem acompanhar
os endereços e aumentam a cobertura de tabelas baseadas em localidade. Cada
volume aceita as dimensões em centímetros ou `volume_m3`.

Resposta:

```json
{"ShippingSevicesArray":[{"ServiceCode":"04014","ServiceDescription":"SEDEX","Carrier":"Correios","CarrierCode":"CORREIOS","CodParcTransp":1234,"ShippingPrice":"89.90","DeliveryTime":"3","Error":false,"Msg":""}]}
```

`ShippingSevicesArray` mantém propositalmente o typo usado pela Frenet e pelo
parser atual. A resposta contém exatamente um array, somente objetos planos e
strings sem aspas, colchetes ou chaves. Opções indisponíveis permanecem no array
com `Error: true`. Uma transportadora sem de-para continua disponível com
`CodParcTransp: 0`.

Se o motor falhar antes de produzir resultados, o contrato adotado até a
homologação é retornar uma linha indisponível (`FRETEWAY_COTACAO_ERRO`). Isso
preserva um diagnóstico visível na grade. Confirme essa decisão no teste ponta a
ponta; ela pode ser alterada para array vazio sem mudar o parser.

## De-para de transportadoras

O mapeamento vive no schema de cada tenant, portanto um `CODPARC` nunca é
reutilizado entre clientes:

- `GET /api/v1/integrations/sankhya/mapeamentos`
- `PUT /api/v1/integrations/sankhya/mapeamentos/{transportadora_id}`

O `PUT` recebe `transportadora_id`, `empresa_sankhya_id` (a `CODEMP`),
`codigo_parceiro`, `nome_parceiro` e, opcionalmente, `codigo_servico`, `servico`
e `ativo`. Mapeamentos antigos sem empresa continuam como fallback do tenant;
um mapeamento específico da `CODEMP` sempre prevalece. Esses endpoints
administrativos exigem as permissões normais do FreteWay.

Cada chamada de cotação registra empresa, nota, transportadoras retornadas,
total de linhas e request ID no log de auditoria, sem guardar a API key.
