# União — comparação com três comprovantes do portal

Consulta em 14/10/2026, aproximadamente 16:57 BRT, via SSH no adapter instalado em produção, usando tabela ativa `6229fc3d-82fc-4e14-afce-4ef9489a0c85`, vigente de 22/09/2026 a 21/12/2026. Transação PostgreSQL explicitamente somente leitura. Nenhuma alteração de tabela, código ou histórico de cotações em produção. Não é teste HTTP ou da interface.

Script: `tmp/audit_uniao_portal_20261014.py`; respostas completas: `tmp/uniao-portal-20261014-results.jsonl`.

Conferido também o XML do DOCX local da tabela União: tarifa peso R$ 1,25, percentual 7%, mínimo R$ 250, seguro 1%, cubagem 300 kg/m³. A tabela persistida aplica o maior entre peso e percentual, ICMS de 7% por dentro e mínimo no total final. A proposta não explicita todos esses métodos; o teste verifica a configuração atual.

| Portal | Destino | Peso real | Volumes | Mercadoria | Volume m³ | Portal total | Produção | Produção menos portal |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 105257 | Santa Inês/MA, 65300112 | 563 kg | 27 | R$ 9.954,10 | 1,353538 | R$ 853,19 | R$ 863,75 | R$ 10,56 |
| 105162 | Belém/PA, 66645155 | 163 kg | 9 | R$ 5.563,30 | 1,008618 | R$ 478,56 | R$ 478,56 | R$ 0,00 |
| 105336 | Belém/PA, 66645155 | 21 kg | 3 | R$ 2.744,50 | 0,259332 | R$ 250,00 | R$ 250,00 | R$ 0,00 |

Origem em todas: Guarulhos/SP, 07042180. Dimensões transcritas em metros dos comprovantes, ponderadas pela quantidade.

## Santa Inês: base do seguro divergente

Portal mostra frete peso R$ 756,72 e seguro R$ 96,47, cuja soma é R$ 853,19. Produção usa frete peso líquido R$ 703,75, seguro líquido R$ 99,54 e ICMS R$ 60,46, total R$ 863,75. O frete peso do portal é compatível com `703,75 / 0,93 = 756,720430...`; o seguro do portal é compatível com `8972 × 1% / 0,93 = 96,473118...`, e não com a mercadoria de R$ 9.954,10 impressa nesta imagem.

Reteste adicional real em produção, mantendo peso, dimensões e destino e alterando somente a entrada de mercadoria para R$ 8.972,00, retornou exatamente R$ 853,19. Essa é a mercadoria da referência anterior 30778 registrada em `uniao-validacao-20261009.md`. A hipótese de base anterior no seguro explica os componentes e o total; não comprova como o portal armazenou ou modificou a cotação.

## Totais e composição

Em Belém 105162, prevalece 7% da mercadoria. Produção: base R$ 389,43, seguro R$ 55,63, ICMS R$ 33,50. Portal: frete valor R$ 418,74 e seguro R$ 59,82, com ICMS R$ 33,50 informado. Os componentes brutos do portal reproduzem `(5563,30 × 7%) / 0,93` e `(5563,30 × 1%) / 0,93`, respectivamente; somam o mesmo total. O ICMS indicado no portal não deve ser somado novamente a esses componentes.

Em 105336, mínimo final confere, mas a distribuição dos componentes difere: portal frete peso R$ 250, seguro zero e ICMS R$ 17,50; produção base R$ 192,12, seguro R$ 27,45, ICMS R$ 16,53 e complemento de mínimo R$ 13,90. Igualdade do total não significa igualdade da discriminação tributária. IBS/CBS também aparecem nos comprovantes e não aparecem como componentes separados neste retorno de produção; não foi realizada validação fiscal.

Conclusão: duas de três cotações reproduzem exatamente o total com os dados impressos. Santa Inês confere somente quando a base de mercadoria é R$ 8.972,00. Não há evidência para alterar a tarifa em produção para forçar igualdade com a mercadoria impressa de R$ 9.954,10.
