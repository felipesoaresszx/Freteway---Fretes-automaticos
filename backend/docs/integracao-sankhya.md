# Integração Sankhya → FreteWay

## Cotação

`POST /integracoes/sankhya/cotacao` (aliases: `/integrations/sankhya/cotacao` e
`/api/v1/integrations/sankhya/cotacao`). A autenticação usa `X-API-Key`. Em
A chave é única para a instalação e é configurada por `SANKHYA_API_KEY`.

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

O mapeamento vive no banco da instalação, portanto um `CODPARC` nunca é
reutilizado entre clientes:

- `GET /api/v1/integrations/sankhya/mapeamentos`
- `PUT /api/v1/integrations/sankhya/mapeamentos/{transportadora_id}`

O `PUT` recebe `transportadora_id`, `empresa_sankhya_id` (a `CODEMP`),
`codigo_parceiro`, `nome_parceiro` e, opcionalmente, `codigo_servico`, `servico`
e `ativo`. Mapeamentos sem empresa continuam como fallback geral;
um mapeamento específico da `CODEMP` sempre prevalece. Esses endpoints
administrativos exigem as permissões normais do FreteWay.

Cada chamada de cotação registra empresa, nota, transportadoras retornadas,
total de linhas e request ID no log de auditoria, sem guardar a API key.

## Contrato para homologação

Endpoint oficial:

```text
POST https://modial-fretes.com.br/api/v1/integrations/sankhya/cotacao
Content-Type: application/json
X-API-Key: <API_KEY>
```

Campos obrigatórios:

| Campo | Tipo | Descrição |
|---|---:|---|
| `NUNOTA` | número ou texto | Número único da nota/pedido no Sankhya. |
| `CODEMP` | número ou texto | Código da empresa emissora vinculada no FreteWay. |
| `CepOrigem` | texto | CEP de origem; pontuação é opcional. |
| `CepDestino` | texto | CEP de destino; pontuação é opcional. |
| `VlrNota` | número positivo | Valor total da mercadoria. |
| `Volumes` | array não vazio | Grupos de volumes da carga. |
| `Volumes[].Peso` | número positivo | Peso unitário em kg; é multiplicado por `Quantidade`. |
| `Volumes[].Quantidade` | inteiro positivo | Quantidade de volumes do grupo; padrão `1`. |

Cada volume deve informar `VolumeM3` ou o conjunto `Altura`, `Largura` e
`Comprimento`. As dimensões são unitárias e expressas em centímetros. Peso,
cubagem e quantidade são totalizados pelo motor oficial de cotação.

Uma resposta bem-sucedida usa HTTP `200`. `ShippingPrice` contém duas casas
decimais e `DeliveryTime` contém dias inteiros, ambos como texto por exigência
do parser atual. `Error: true` identifica uma transportadora analisada que não
produziu uma opção válida. Se nenhuma transportadora estiver ativa/elegível, o
retorno controlado é:

```json
{"ShippingSevicesArray":[]}
```

Erros de autenticação retornam HTTP `401`; JSON ou campos inválidos retornam
HTTP `422`; indisponibilidade do banco retorna HTTP `503` com corpo estruturado:

```json
{
  "detail": {
    "codigo": "BANCO_INDISPONIVEL",
    "mensagem": "Nao foi possivel processar a cotacao neste momento",
    "request_id": "<REQUEST_ID>"
  }
}
```

## Chamada manual

Configure uma chave forte e exclusiva em `SANKHYA_API_KEY` no ambiente legado,
Configure `SANKHYA_API_KEY` no ambiente da aplicação. Nunca grave a chave real em arquivos versionados.

```bash
curl --request POST \
  'https://modial-fretes.com.br/api/v1/integrations/sankhya/cotacao' \
  --header 'Content-Type: application/json' \
  --header 'X-API-Key: <API_KEY>' \
  --data '{
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
  }'
```

Procedimento sugerido para o desenvolvedor Sankhya:

1. Configurar a URL, o header `X-API-Key` e timeout superior ao timeout das
   transportadoras no ambiente de homologação.
2. Enviar uma `NUNOTA` e `CODEMP` conhecidas com CEPs atendidos por uma tabela
   ativa do FreteWay.
3. Confirmar HTTP `200`, o único array `ShippingSevicesArray`, `CodParcTransp`,
   transportadora, valor e prazo.
4. Repetir sem a chave e com CEP inválido para confirmar HTTP `401` e `422`.
5. Informar ao time FreteWay o `X-Request-ID` da resposta em caso de divergência;
   ele correlaciona logs sem expor a API key.
