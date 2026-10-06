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
- ICMS por dentro sobre o subtotal tributável, com alíquota de rota: a proposta tem
  origem em São Paulo; 7% para DF/GO/TO e demais destinos no Norte, Nordeste,
  Centro-Oeste e ES, e 12% para destinos no Sul/Sudeste. A alíquota precisa ser
  reavaliada se origem, modalidade, destinatário ou regime fiscal forem diferentes.
- Armazenagem de R$ 5,50/m²/dia a partir do 7º dia.
- Paletização de R$ 75,00 por pallet.
- Reentrega de 50% e devolução de 100% do frete original.
- Veículos dedicados: carreta R$ 2.100, truck R$ 1.400, toco R$ 1.100,
  3/4 R$ 850 e van R$ 680.

Não há no documento cobrança adicional de ISS, PIS/COFINS ou DIFAL por cotação.
Isso não significa que não componham os custos fiscais internos da transportadora;
não devem ser acrescentados como taxas separadas sem previsão contratual e validação
tributária. O próprio ICMS pode variar conforme início da prestação, regime e
características da operação.

## TDE e TDA

Na planilha original, R$ 287,50 corresponde a **TDE**, para entregas em redes e
supermercados. **TDA** significa difícil acesso e depende da relação de cidades/CEPs;
portanto não recebe automaticamente o valor fixo de R$ 287,50.

O endpoint não envia e-mails automaticamente. A confirmação comercial continua sendo
um processo externo, evitando disparos sem autorização e sem credenciais configuradas.

## Divergência com o portal SSW

Atualização de 06/10/2026: as composições do SSW identificam adicional de frete
de 8% antes do ICMS para DF, GO e TO. A pedido do usuário, essa regra foi
estendida a todos os destinos Maex. A imagem corrigida do primeiro exemplo
informa R$ 153,05. O motor agora inclui o adicional e reproduz
R$ 153,05, R$ 188,31 e R$ 214,43 para os três pedidos conferidos. Consulte
`maex-validacao-20261006.md` para bases, arredondamento e limites. O relato
abaixo documenta a investigação anterior à disponibilização dessas composições.

Reprocessamos as cotações 28603, 28324 e 28647 a partir dos pesos, dimensões, valores
de nota e tarifas desta proposta. O cálculo reproduz R$ 141,73, R$ 174,37 e R$ 196,08,
respectivamente, que são os totais registrados no FreteWay. A planilha não permite
explicar os totais do portal de R$ 153,03, R$ 188,31 e R$ 502,09; os acréscimos de
R$ 11,30, R$ 13,94 e R$ 306,01 não correspondem, com a informação disponível, a uma
regra comprovada deste contrato. Em particular, não aplicamos automaticamente a TDE
de R$ 287,50, pois ela é restrita a entregas em redes/supermercados. Para paridade,
é necessária a memória detalhada dessas cotações no portal ou confirmação escrita da
MAEX sobre os componentes e respectivos gatilhos.
