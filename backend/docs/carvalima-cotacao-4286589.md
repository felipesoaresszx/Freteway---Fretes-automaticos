# Carvalima: cotação 4286589 — Araguaína/TO

Conferência em 05/10/2026 usando o pedido 29411 apresentado na imagem, o PDF `Cotacao-4286589.pdf`, a proposta `tabelas_trans/TABELA CARVALIMA.pdf` e os três CSVs complementares. Os documentos foram tratados como evidência comercial.

## Dados e resultado

- Origem: Guarulhos/SP, CEP 07042180.
- Destino: Araguaína/TO, CEP 77803130.
- NF: R$ 4.769,90; três volumes; peso real: 59 kg.
- Medidas em metros: 0,23 × 0,31 × 0,39; 0,34 × 0,57 × 0,57; 0,30 × 0,33 × 0,57.
- Volume calculado: 0,194703 m³; portal: 0,1947 m³.
- Peso cubado, fator 300: 58,4109 kg. Peso cobrado: 59 kg.
- Portal: R$ 675,34; FreteWay: destino sem correspondência.

## Causa identificada

A proposta original tem destinos em AC, MS, MT, PA e RO. A leitura integral das 12 páginas não encontrou nenhuma entrada `TO/`, e os 260 destinos normalizados também não incluem TO. Portanto não há tarifa documentada para selecionar para Araguaína. A reprodução local com os dados acima retorna `CalculoUniversalError: Destino sem correspondência na tabela da transportadora`.

O portal comprova atendimento a Araguaína, mas o total isolado não fornece as oito faixas de peso, excedente e encargos da rota. Não foi atribuída tarifa de outra UF nem criado preço a partir desse total. É necessária a tabela complementar SP → TO ou o detalhamento tarifário da Carvalima para cadastrar e conferir essa rota.

## Listas complementares

Nenhuma faixa TRT contém os CEPs de origem/destino. O CNPJ do destinatário, normalizado para 37413655000100, não consta na TDE. Araguaína/TO não consta na TDA. Essas listas não fornecem a tarifa ausente.

Sem frete-base documentado, esta cotação ainda não permite comparar ICMS ou calcular um total independente. Nenhuma alteração em produção foi feita nesta conferência.
