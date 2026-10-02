# Validação documental — Transporte Generoso

Data da conferência: 02/10/2026

## Documentos comparados

- `TABELA  GENEROSO.pdf`: proposta comercial de uma página; SHA-256 `0be646b399e127002e17866135b4d102673e63646364e02f2359efb6ec55a80c`.
- `PRAÇAS GENEROSO.xlsx`: abas `CIDADES` (3.939 registros), `PRAÇAS` (mapa de códigos comerciais) e `Emex` (16 linhas de dados).
- O SHA-256 do PDF é idêntico ao documento `TABELA_N.pdf` anexado ao rascunho de produção `f8dab13c-9609-44ef-ac5c-0801f65bf34f`.

## Tarifas conferidas no PDF

Origem: Guarulhos/SP. Cubagem: 300 kg/m³. A extração determinística identifica 36 combinações de UF e classe, cada uma com frete mínimo (R$/CTRC), percentual sobre NF e tarifa por kg. As linhas tarifárias foram verificadas visualmente por coordenadas e comparadas aos códigos comerciais da planilha.

Adicionais expressos no documento:

- GRIS indicado como 0,00%; GRIS mínimo, despacho, pedágio e TAS aparecem como “-”.
- Frete-valor remetido a “CONFORME TABELA”; a matriz da própria proposta contém o percentual “Sobre NF” por praça. Esse componente pode ser calculado pela coluna existente.
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

### Conferência adicional de 02/10/2026

- A pasta `tabelas_trans` contém somente dois arquivos específicos da Generoso: a proposta PDF e a planilha de praças. Nenhum dos anexos comerciais citados abaixo está na pasta.
- O PDF fornece 36 combinações de UF e classe tarifária. A planilha traz 3.939 localidades; 153 registros do PA (classes `CAPITAL` e `INTERIOR`) não têm tarifa correspondente no PDF.
- A aba `Emex` identifica 15 cidades sujeitas a esse adicional, mas não fornece os CEPs de área de risco nem a lista Sec-Cat.
- O PDF identifica cliente/CNPJ diferentes da Modial (`N.VIOLA CORMERCIO DE ARTI (C.)`, CNPJ `42.061.797/0001-87`, e `VM RAMOS E CIA LTDA` em outro campo). A aplicabilidade comercial da proposta à conta de produção precisa ser confirmada.
- Em produção, a transportadora está ativa no cadastro, porém sua única tabela está em `review`, sem tarifas importadas. Duas tentativas de cotação retornaram `TABELA_ATIVA_NAO_ENCONTRADA`.
- O fluxo local de análise foi ajustado para reconhecer deterministicamente os dois arquivos. As 153 localidades sem tarifa do PA são excluídas da cobertura automática; a validação estrutural das demais permanece em modo parcial por pendências comerciais. Essa mudança ainda não foi implantada em produção.
- Como a planilha não contém faixas de CEP, as cotações para os estados cobertos resolvem a praça por cidade e UF informadas, inclusive quando a solicitação também inclui CEP. O PA continua sem correspondência.

**Revisão documental concluída; publicação com preço final bloqueada por dados comerciais ausentes/ambíguos.** O usuário escolheu aguardar o preço completo. Antes de publicar, obter:

1. Prazos de entrega por praça/cidade, ou confirmação de que prazo não faz parte da cotação.
2. A lista de CEPs de área de risco e o anexo/lista Sec-Cat, ou confirmação de que esses adicionais devem ficar fora do cálculo.
3. Regra inequívoca para os dois itens de taxa de coleta (0,20% e R$ 12,00) e sua incidência.
4. Regra fiscal aplicável (ICMS/ISS) para a operação da empresa.
5. Confirmação de que a proposta identificada com outros clientes é válida para a conta Modial.

Na nova conferência de produção, a tabela está em `review`, sem tarifas importadas e sem publicação. A extração local atualizada ainda não foi implantada.
