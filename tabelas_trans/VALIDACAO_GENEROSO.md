# Validação documental — Transporte Generoso

Data da conferência: 02/10/2026

## Documentos comparados

- `TABELA  GENEROSO.pdf`: proposta comercial de uma página; SHA-256 `0be646b399e127002e17866135b4d102673e63646364e02f2359efb6ec55a80c`.
- `PRAÇAS GENEROSO.xlsx`: abas `CIDADES` (3.939 registros), `PRAÇAS` (mapa de códigos comerciais) e `Emex` (16 linhas de dados).
- O SHA-256 do PDF é idêntico ao documento `TABELA_N.pdf` anexado ao rascunho de produção `f8dab13c-9609-44ef-ac5c-0801f65bf34f`.

## Tarifas conferidas no PDF

Origem: Guarulhos/SP. Cubagem: 300 kg/m³. A matriz apresenta 35 linhas de destino, cada uma com frete mínimo (R$/CTRC), percentual sobre NF e tarifa por kg. As linhas tarifárias foram verificadas visualmente por coordenadas e comparadas aos códigos comerciais da planilha.

Adicionais expressos no documento:

- GRIS indicado como 0,00%; GRIS mínimo, despacho, pedágio e TAS aparecem como “-”.
- Frete-valor remetido a “CONFORME TABELA”, sem a tabela referenciada.
- EMEX: R$ 23,71 + 0,15% para a lista de cidades indicada; R$ 38,24 + 0,15% para São Gonçalo. A aba `Emex` tem 16 registros correspondentes.
- Taxa de área de risco: R$ 50,88/CTRC, com consulta a uma lista de CEPs não anexada.
- Sec-Cat: documento/anexo referenciado, mas ausente.
- Reentrega 50% e devolução 100% do frete original.
- TSO 0,10%, mínimo R$ 2,80; TEC 6,93%; taxa de coleta: 0,20% em destinos especificados e também R$ 12,00, sem deixar clara a composição/aplicabilidade entre as duas linhas.
- ICMS/ISS não inclusos, a cobrar conforme legislação.
- Validade declarada: indeterminada, salvo manifestação ou 30 dias sem operação. O rascunho usa vigência administrativa de 02/10/2026 a 31/12/2026.

## O que a planilha de praças comprova

- 3.939 cidades classificadas em `CAPITAL` (335), `INTERIOR I` (726), `INTERIOR II` (2.649) e `INTERIOR` (229).
- A aba `PRAÇAS` lista códigos e localidades especiais; a aba `Emex` discrimina cidades e códigos comerciais.
- Não há colunas de CEP inicial/final nem prazo de entrega. O prazo é remetido pelo PDF a um link externo que não respondeu durante a conferência.

## Resultado para produção

**Revisão documental concluída; validação para cotação bloqueada por dados comerciais ausentes/ambíguos.** Não alterar/aprovar/publicar o rascunho até obter:

1. A tabela de frete-valor referenciada como “CONFORME TABELA”.
2. Prazos de entrega por praça/cidade, ou confirmação de que prazo não faz parte da cotação.
3. A lista de CEPs de área de risco e o anexo/lista Sec-Cat, ou confirmação de que esses adicionais devem ficar fora do cálculo.
4. Regra inequívoca para os dois itens de taxa de coleta (0,20% e R$ 12,00) e sua incidência.
5. Regra fiscal aplicável (ICMS/ISS) para a operação da empresa.

O rascunho de produção permanece `draft`, sem análise registrada e sem mudanças feitas nesta validação. A produção está saudável (`/api/v1/health/ready` retornou `ready`, banco `ok`).
