# Integração Maex / Modial

O FreteWay calcula a proposta Maex Brasil - SPO usando a tabela importada e ativa da
transportadora. A fonte homologada é a planilha `Tabela maex.xls` (proposta Modial),
com cubagem de 300 kg/m³ e as praças GYN, BSB, TOC, CWB, CMP e RBP.

## Endpoint dedicado

`POST /api/v1/cotacao/modial`

Requer a permissão `cotacoes.manage` e uma tabela Maex ativa e vigente no cadastro de
transportadoras.

```json
{
  "peso": 150,
  "volume_m3": 0,
  "valor_nf": 1000,
  "destino": "GYN",
  "regiao": "POLO",
  "referencia_pedido": "PED-123456",
  "servicos": {
    "zona_rural": false,
    "zmrc": false,
    "tde": false,
    "paletizacao": 0,
    "armazenagem_dias": 0,
    "armazenagem_m2": 0,
    "veiculo_dedicado": null,
    "reentrega": false,
    "devolucao": false
  }
}
```

A resposta separa frete base, taxas obrigatórias, serviços adicionais, subtotal sem
ICMS, ICMS e total final. Também informa peso de cobrança, prazo, versão da tabela e
referência do pedido.

## Regras confirmadas

- Frete até 100 kg, acrescido do valor por kg excedente acima desse limite.
- Peso de cobrança igual ao maior entre peso real e volume × 300 kg/m³.
- Despacho de R$ 17,25 por CT-e.
- Pedágio de R$ 6,33 por fração iniciada de 100 kg.
- GRIS e seguro de 0,3% cada sobre o valor da nota.
- Armazenagem de R$ 5,50/m²/dia a partir do 7º dia.
- Paletização de R$ 75,00 por pallet.
- Reentrega de 50% e devolução de 100% do frete original.
- Veículos dedicados: carreta R$ 2.100, truck R$ 1.400, toco R$ 1.100,
  3/4 R$ 850 e van R$ 680.

## TDE e TDA

Na planilha original, R$ 287,50 corresponde a **TDE**, para entregas em redes e
supermercados. **TDA** significa difícil acesso e depende da relação de cidades/CEPs;
portanto não recebe automaticamente o valor fixo de R$ 287,50.

O endpoint não envia e-mails automaticamente. A confirmação comercial continua sendo
um processo externo, evitando disparos sem autorização e sem credenciais configuradas.
