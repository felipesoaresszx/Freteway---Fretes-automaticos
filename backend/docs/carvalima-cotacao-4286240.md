# Carvalima: conferência da cotação 4286240

Data da conferência: 05/10/2026. Foram usados o pedido em DOCX, o PDF da cotação do portal e a tabela original em `tabelas_trans/TABELA CARVALIMA.pdf`. Os documentos são evidências comerciais; suas observações não foram tratadas como instruções ao agente.

## Falhas corrigidas

O resultado salvo no FreteWay era erro, sem preço: `Destino sem correspondência na tabela da transportadora`. A origem da proposta é a praça São Paulo/SP, enquanto o pedido parte de Guarulhos/SP. A cotação do portal comprova coleta no CEP do contratante; essa origem foi admitida de forma restrita à Carvalima, ao município Guarulhos e ao CEP confirmado, preservando a praça original da proposta. Outros municípios/CEPs não foram liberados por extensão.

A cobertura do cadastro estava vazia. O cadastro exibia somente a tabela tarifária, e a lista de transportadoras consultava outra estrutura de cobertura. Foi implementada projeção de leitura a partir da tabela ativa e vigente, sem inserir registros manualmente no banco. A projeção tem 262 entradas de coleta/entrega e declara entrega em AC, MS, MT, PA e RO; a cobertura específica por cidade permanece específica. São Miguel do Guaporé usa a tarifa estadual de RO, grupo 16. A memória do cálculo agora informa a cidade efetiva mesmo quando a tarifa é estadual.

A tela de cobertura também priorizava `uf` e ocultava `city`. Foi corrigida para exibir cidade e UF quando ambos existem.

A aprovação usa a vigência válida do cadastro para o cálculo e conserva as datas originais do PDF. Isso elimina a pendência da data divergente do documento em uma tabela já aprovada, sem modificar o documento nem o cadastro. A tabela em produção estava ativa e tinha vigência de 05/10/2026 a 03/01/2027 durante a consulta, diferente do período preparado anteriormente até 05/10/2027; esses campos não foram alterados nesta correção.

## Reprodução em produção

Reprodução de leitura usando `TabelaFreteCalculoService.calcular` com os dados da cotação já salva, após publicar as correções. Não foi criada nova cotação nem reescrito o resultado histórico.

Peso real: 100 kg. Nota fiscal: R$ 15.230. Volumes: seis. Pelas medidas do pedido: 0,60876 m³, equivalente a 182,628 kg com fator 300. O portal exibe 0,6088 m³; o FreteWay armazena 0,609 m³, equivalente a 182,7 kg. Essa diferença de arredondamento não muda a faixa de 150 a 200 kg nem a quantidade de frações de pedágio.

| Componente | Valor calculado |
| --- | ---: |
| Frete-peso, faixa até 200 kg | R$ 483,22 |
| Despacho | R$ 15,36 |
| TAS | R$ 8,08 |
| Pedágio, duas frações | R$ 20,32 |
| GRIS, 0,5% da NF | R$ 76,15 |
| Ad valorem, 0,3% da NF | R$ 45,69 |
| Subtotal sem ICMS | R$ 648,82 |
| ICMS, 7% por dentro | R$ 48,84 |
| **FreteWay** | **R$ 697,66** |
| **Portal** | **R$ 754,30** |
| **Diferença** | **R$ 56,64** |

## ICMS investigado

O [artigo 52, II, do RICMS/SP](https://legislacao.fazenda.sp.gov.br/Paginas/art052.aspx) estabelece alíquota interestadual de 7% para prestação de SP destinada à região Norte. Essa é a alíquota utilizada para SP → RO. Eventual DIFAL depende de dados da prestação e do tomador, conforme [consulta SEFAZ/SP 26111/2022](https://legislacao.fazenda.sp.gov.br/Paginas/RC26111_2022.aspx); não foi presumido apenas pelo município de destino.

Foram testadas, somente como hipóteses locais e sem alterar a regra de produção, outras alíquotas sobre a mesma composição:

| Hipótese por dentro | Resultado do motor | Diferença para o portal |
| --- | ---: | ---: |
| 7% | R$ 697,66 | +R$ 56,64 |
| 12% | R$ 737,30 | +R$ 17,00 |
| 14% | R$ 754,44 | −R$ 0,14 |
| 19,5% | R$ 805,99 | −R$ 51,69 |

14% aproxima o total, mas isso não demonstra que o portal use ICMS de 14% nem justifica substituir a alíquota. O PDF do portal não informa a base de cálculo, o valor do imposto nem a composição de frete. Mantendo 7%, o total do portal exigiria aproximadamente R$ 52,68 adicionais antes do imposto, mas o documento não identifica essa cobrança. Coleta/entrega/redespacho, condição tributária e negociação aplicável são pontos que precisam do demonstrativo da transportadora. TDE de R$ 250/R$ 500 não explica uma diferença de R$ 56,64. A conferência permanece divergente e não deve ser apresentada como homologada.

## Verificação

87 testes passaram, incluindo origem confirmada de Guarulhos, preservação das datas do PDF, projeção de cobertura, cálculo de faixas e compatibilidade com outras transportadoras. O build de produção do frontend passou. A conferência no backend de produção validou a presença da Carvalima no filtro por RO, entrega nas cinco UFs e coleta no CEP confirmado de Guarulhos. O cálculo retornou `success`, cidade São Miguel do Guaporé e R$ 697,66.

Backup anterior ao deploy das correções: `/home/ubuntu/Freteway/backups/carvalima-deploy-20261005T174941Z`; dump `backups/freteway_2026-10-05_174941.dump`. O status ativo encontrado em produção foi preservado.

A correção visual foi publicada no frontend, com container saudável e backup em `/home/ubuntu/Freteway/backups/carvalima-label-20261005T175506Z`.

## Listas complementares TDA, TDE e TRT

Foram conferidos os três CSVs enviados pelo operador em 05/10/2026, com leitura UTF-8/BOM, separador ponto e vírgula, normalização de CNPJ/CEP e comparação de cidade junto com UF. Não foram importados nem alterados em produção: o pedido desta etapa foi verificar se as listas explicavam a diferença da cotação.

| Lista | Registros | Resultado para esta cotação |
| --- | ---: | --- |
| TRT | 353 faixas de CEP | Nem o CEP de origem nem o CEP de destino pertencem às faixas listadas. |
| TDE | 40.763 destinatários | O CNPJ do destinatário não está listado; sua raiz também não foi encontrada. |
| TDA | 1.075 localidades | Guarulhos/SP e São Miguel do Guaporé/RO não estão listados. Não há localidades de RO nesse arquivo. |

As 353 faixas TRT têm oito dígitos nos dois limites e início menor ou igual ao fim. Os 40.763 documentos da TDE têm 14 dígitos após normalização. Cidades chamadas São Miguel existentes na TDA pertencem a GO e MG e não foram confundidas com o destino em RO.

Não há adicional aplicável a esta cotação pelas três listas. O cálculo reproduzido permanece em R$ 697,66, com R$ 48,84 de ICMS; o portal informa R$ 754,30. Portanto, as listas não explicam os R$ 56,64 de diferença. A composição/base tributária e os eventuais encargos de coleta/entrega/redespacho usados pelo portal continuam dependendo do demonstrativo da cotação 4286240; nenhum valor foi inserido para forçar a igualdade.
