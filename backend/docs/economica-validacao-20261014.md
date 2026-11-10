# Transportadora Econômica — teste de produção em 14/10/2026

## Correção publicada — 14/10/2026, reteste às 17:24 BRT

Correção solicitada explicitamente pelo usuário. O motor agora permite definir `pricing_rules.cubage_volume_decimal_places` por tabela, com arredondamento decimal HALF_UP antes de multiplicar pelo fator de cubagem. A tabela da Econômica recebeu precisão de quatro casas decimais para volume, reproduzindo os pesos cubados e valores das referências recebidas. Essa precisão é inferida das referências, não é regra documentada pelo portal para toda a malha.

Eusébio e Pacatuba foram incluídas em `cities` da praça FORP e excluídas das praças de interior FORI/SOBI na rota de Guarulhos. A configuração foi aplicada apenas à tabela da transportadora CNPJ 70.037.379/0009-47, com versionamento para `1.economica-20261014` e `AuditoriaTabela` contendo os dados anteriores e novos. Cadastro ativo, vigência, documento original e cotações históricas foram preservados. Script idempotente `backend/scripts/configure_economica.py` valida os quatro pedidos distintos antes de gravar.

62 testes passaram (referências da Econômica, tabela combinada, piso da União e serviço de cálculo); Ruff aprovado. `backend/pytest.ini` continha uma linha inválida preexistente, então os testes utilizaram a configuração alternativa existente `tmp/pytest-maex.ini`. Backend e worker publicados, backend saudável. Backup de código `/home/ubuntu/Freteway/backups/economica-fix-20261014T202021Z`, banco `backups/freteway_2026-10-14_202021.dump`.

Reexecução no adapter de produção com seleção automática e medidas originais, transação somente leitura, sem praça explícita ou peso cubado imposto:

| Cotação portal | Destino | Portal | Produção após correção | Diferença |
| --- | --- | ---: | ---: | ---: |
| 013292 | Fortaleza | R$ 326,09 | R$ 326,09 | R$ 0,00 |
| 013584 | Iguatu | R$ 323,24 | R$ 323,24 | R$ 0,00 |
| 013657 | Eusébio | R$ 2.156,02 | R$ 2.156,02 | R$ 0,00 |
| 013688 | Pacatuba | R$ 438,31 | R$ 438,31 | R$ 0,00 |
| 013700 | Eusébio | R$ 2.156,02 | R$ 2.156,02 | R$ 0,00 |

Cinco respostas comerciais conferem exatamente, correspondendo a quatro pedidos distintos. Peso cobrado de Eusébio 1.358,730 kg e Pacatuba 231,990 kg também conferem com os PDFs. Evidência: `tmp/economica-all-after-fix-20261014.jsonl`. Validação direta do cálculo instalado; não foi teste pela interface/HTTP nem criação de cotações históricas. Novas referências de outras cidades/pesos continuam necessárias para homologação de toda a malha. As seções abaixo preservam as constatações anteriores à correção.

## Reteste consolidado — 14/10/2026 às 17:17 BRT

Conferidos os cinco PDFs reenviados com sufixo `(1)` e repetidos todos os pedidos no `TabelaFreteAdapter.cotar` do backend de produção, usando seleção automática, medidas e pesos originais das imagens, sem informar praça ou substituir peso por aquele do portal. Transportadora ativa, método tabela própria; tabela ativa e vigente `579dd8ef-cd1f-4aa9-a028-b93b95e10542`, versão 1. Transação somente leitura; sem criação de histórico ou alteração de produção. Não é teste HTTP nem pela interface.

| Cotação portal | Pedido | Destino | Portal | Produção automática | Produção menos portal |
| --- | --- | --- | ---: | ---: | ---: |
| 013292 | 29526 | Fortaleza | R$ 326,09 | R$ 326,09 | R$ 0,00 |
| 013584 | 31275 | Iguatu | R$ 323,24 | R$ 323,24 | R$ 0,00 |
| 013657 | 31344 | Eusébio | R$ 2.156,02 | R$ 3.253,70 | R$ 1.097,68 |
| 013688 | 31273 | Pacatuba | R$ 438,31 | R$ 625,70 | R$ 187,39 |
| 013700 | 31344 | Eusébio | R$ 2.156,02 | R$ 3.253,70 | R$ 1.097,68 |

Todos os cálculos retornaram sucesso, mas somente dois dos cinco PDFs conferem em preço. São quatro pedidos distintos: duas respostas comerciais para o mesmo pedido de Eusébio. A seleção automática usa rota 3/polo para Fortaleza e rota 2/interior para os demais. Eusébio e Pacatuba permanecem divergentes. Evidência local: `tmp/economica-all-production-20261014.jsonl`; script: `tmp/audit_economica_all.py`. A reprodução usa a tabela vigente atual, sem reconstrução das versões históricas.

Consulta via SSH no backend de produção, às 07:41 BRT, em transação PostgreSQL explicitamente somente leitura. Executado `TabelaFreteAdapter.cotar` com a tabela persistida, incluindo validação de status e vigência. Não foi criada cotação no histórico, nem alterado cadastro, código ou tabela. Não foi teste HTTP ou pela interface.

## Cadastro e tabela

- Transportadora: TRANSPORTADORA ECONOMICA, CNPJ 70.037.379/0009-47, ativa, sem exclusão.
- Método: `tabela_propria`; integração: `tabela`; cadastro: `A_VALIDAR`.
- Indicadores persistidos: sucesso 0%, tempo médio 0 ms; não representam o resultado deste teste.
- Tabela `579dd8ef-cd1f-4aa9-a028-b93b95e10542`, versão 1, ativa, de 24/09/2026 a 23/12/2026.
- Importação `tabela_frete_universal_v1`, `TABLE_VALIDATED`, documento `Tabela_Combinada_MODIAL.pdf`, parser `tabela_combinada_pdf_v1`.
- Os dados normalizados indicam validade documental até 20/04/2027, diferente do término cadastrado. O teste passou pela vigência atual; nenhuma data foi alterada.

## Cotação 31344

Referência enviada: 13/10/2026. Origem CEP 07042180 (Guarulhos/SP), destino CEP 61760000 (Eusébio/CE), CIF incluso no boleto. Valor dos itens R$ 18.996,00. Quarenta volumes de 15 kg e um de 8 kg: 608 kg. Todos com altura 34 cm, comprimento 57 cm e largura 57 cm. Volume total: 4,529106 m³.

O retorno real foi `success`, R$ 3.253,70, sem prazo informado. Fator de cubagem 300 kg/m³; peso cobrado 1.358,732 kg, conforme arredondamento do motor.

| Componente | Valor |
| --- | ---: |
| Frete peso | R$ 2.794,97 |
| GRIS, 0,2% da mercadoria | R$ 37,99 |
| Ad valorem, 0,6% da mercadoria | R$ 113,98 |
| Despacho | R$ 79,00 |
| ICMS, 7% por dentro | R$ 227,76 |
| Total | R$ 3.253,70 |

As parcelas apresentadas são arredondadas; o total utiliza a precisão interna do motor.

Selecionada a rota 2, praça FORI (Fortaleza/interior), contratos CO236685/CO236684, tarifa acima de 100 kg de R$ 2,05704114/kg sobre o peso total. A importação não lista Eusébio nominalmente: o motor possui regra de cobertura de interior CE para FORI. O enquadramento deve ser confirmado com a malha comercial da transportadora antes de considerar o preço homologado.

A imagem não apresenta preço de frete da transportadora: R$ 18.996,00 é o total dos itens. Portanto o teste confirma o retorno operacional de produção, mas não homologa igualdade de preço com uma cotação externa.

## Referência externa recebida posteriormente

PDF `ssw1601TE5[1]172300.pdf`, cotação SSW 013657, inclusão 13/10/2026, validade 20/10/2026. Mesmos remetente, destinatário, rota, NF de R$ 18.996,00, 41 volumes e dimensões do pedido 31344. Peso apresentado: 1.358,730 kg (cubado); volume apresentado: 4,53 m³. Frete final R$ 2.156,02; ICMS 7%, R$ 150,92, incluído nesse total. Documento identifica a matriz CNPJ 70.037.379/0001-90; cadastro da aplicação identifica a filial 70.037.379/0009-47.

Diferença do retorno automático: R$ 1.097,68 acima do portal. Em 14/10/2026 às 08:53 BRT, um teste somente leitura no mesmo adapter de produção, explicitando `destino_codigo=FORP` e `nivel_atendimento=POLO`, retornou exatamente R$ 2.156,02, inclusive ICMS R$ 150,92. Frete peso R$ 1.774,13; GRIS R$ 37,99; ad valorem R$ 113,98; despacho R$ 79,00. A tarifa FORP é R$ 1,30572612/kg, contrato CO236686.

O resultado sustenta que, neste caso, o portal utiliza tarifa equivalente a Fortaleza/polo para Eusébio. O PDF não discrimina a praça ou essas parcelas, portanto a identificação da tarifa é inferida pela reprodução exata do total e ICMS. O cadastro e a seleção automática de produção ainda não foram corrigidos; o teste com código explícito demonstra a regra necessária para este caso, sem justificar estendê-la a todas as cidades do CE.

## Pedido 31275 — Iguatu/CE

Referência `ssw1601TE5[1]165850.pdf`, SSW 013584, de 08/10/2026, validade 15/10/2026, previsão 20/10/2026. Origem Guarulhos/SP, CEP 07042180, destino Iguatu/CE, CEP 63500068. Mercadoria R$ 575,90, três volumes: dois de 30 × 36 × 44 cm e 23 kg cada; um de 25 × 24 × 34 cm e 12 kg. Peso real 58 kg; volume calculado 0,11544 m³, peso cubado 34,632 kg. Portal apresenta 0,12 m³ e cobrança pelo peso real de 58 kg.

Teste no adapter de produção atual com seleção automática: `success`, R$ 323,24, igual ao PDF, ICMS R$ 22,63 também igual. Praça FORI, faixa acima de 50 até 70 kg, frete peso R$ 296,00, GRIS R$ 1,15, ad valorem R$ 3,46. Despacho não aplicado neste retorno. O motor não informa prazo; a previsão absoluta no PDF não foi convertida em prazo contratual.

Comparações somente leitura com praça explícita: FORI R$ 323,24; SOBI R$ 323,24 (mesma tarifa); FORP R$ 207,11; SOBP R$ 265,17. Assim, este pedido confirma a tarifa de interior, mas não distingue FORI de SOBI pelo preço. Não cabe trocar todo o CE para polo por causa do caso Eusébio.

O script inicialmente carregou a tabela sem a relação `dados_importados` e encontrou erro de lazy loading assíncrono. Foi corrigido o carregamento do próprio script com `joinedload`, seguindo a consulta usada pelo serviço de cotações. Os valores acima são da reexecução bem-sucedida; esse erro inicial não comprova falha no fluxo real da aplicação. Nenhuma configuração ou código de produção foi alterado nesta conferência.

## Pedido 29526 — Fortaleza/CE

O usuário confirmou que a imagem é o pedido enviado à transportadora e o PDF é a resposta comercial. Imagem de 29/09/2026, resposta `ssw1601TE5[1]142243.pdf`, SSW 013292, incluída em 30/09/2026, validade e previsão 07/10/2026. Remetente Dimepor, destinatário Complexo Santa Rita Ltda, destino Fortaleza/CE, CEP 60866607, origem CEP 07042180. NF R$ 1.755,10, sete volumes de 30 × 36 × 44 cm e 23 kg cada, total 161 kg. Volume exato 0,33264 m³; portal exibe 0,33 m³. Peso cubado 99,792 kg; cobrança pelos 161 kg reais.

Teste somente leitura no adapter atual de produção, sem praça explícita: `success`, R$ 326,09, exatamente igual ao PDF; ICMS 7%, R$ 22,83, também igual. Frete peso R$ 210,22, GRIS R$ 3,51, ad valorem R$ 10,53, despacho R$ 79,00. Praça FORP/polo; tarifa acima de 100 kg R$ 1,30572612/kg aplicada ao peso total. FORP explícito reproduz o mesmo total; FORI explícito retornou R$ 456,15. Neste pedido acima de 100 kg, despacho aplicado; no pedido Iguatu de 58 kg, não aplicado.

A reprodução verifica a tabela vigente atual, não reconstrói uma versão histórica de setembro. Não foi criado histórico nem alterada a produção. Três referências até aqui: Fortaleza e Iguatu conferem automaticamente; Eusébio confere com FORP explícito, permanecendo pendente a correção do enquadramento automático desse destino.

## Nova resposta para o pedido 31344 — SSW 013700

PDF `ssw1601TE5[1]161029.pdf`, inclusão 14/10/2026, validade 21/10/2026, previsão 21/10/2026. Repete os dados de Eusébio da resposta 013657: NF R$ 18.996,00, 41 volumes, mesmas medidas, peso cobrado apresentado 1.358,730 kg cubado. Repete também frete R$ 2.156,02 e ICMS R$ 150,92. Trata-se de nova resposta para o mesmo pedido, não de cenário adicional de cálculo.

Reteste somente leitura em produção em 14/10/2026 às 16:12 BRT: seleção automática R$ 3.253,70; FORP/POLO explícito R$ 2.156,02. Diferença automática permanece R$ 1.097,68. Nenhuma alteração de produção nesta conferência. A segunda resposta reforça a reprodução pela tarifa de polo para Eusébio; a seleção automática continua pendente de correção.

## Pedido 31273 — Pacatuba/CE

Imagem de 14/10/2026, origem Guarulhos/SP CEP 07042180, destino Pacatuba/CE CEP 61802530, mercadoria R$ 3.213,00, sete volumes de 57 × 34 × 57 cm e 15 kg cada: peso real 105 kg, volume exato 0,773262 m³. PDF `ssw1601TE5[1]150832.pdf`, SSW 013688, inclusão 14/10/2026, validade/previsão 21/10/2026, apresenta peso cubado 231,990 kg, frete R$ 438,31 e ICMS R$ 30,68. Destinatário não preenchido no PDF, mas cidade, NF, volumes e medidas coincidem.

Teste somente leitura no adapter atual: automático/FORI R$ 625,70, peso cubado 231,979 kg; FORP explícito com as mesmas medidas R$ 438,29. Diferença automática R$ 187,39; diferença com polo R$ 0,02 abaixo do portal. SOBI R$ 625,70; SOBP R$ 524,17.

Teste adicional FORP com volume 0,7733 m³, equivalente ao peso cubado apresentado pelo portal (231,990 kg): R$ 438,31, ICMS R$ 30,68, exatamente como o PDF. Composição desse teste: peso R$ 302,92, GRIS R$ 6,43, ad valorem R$ 19,28, despacho R$ 79,00. O volume de quatro casas reproduz o portal neste caso, mas não prova uma regra geral de arredondamento: em Eusébio o peso exibido é compatível com outras precisões. Nenhuma regra global de cubagem foi alterada.

Conclusão: Pacatuba também requer tarifa equivalente a FORP/polo para reproduzir este preço. A diferença residual de centavos é explicada pelo peso cubado do portal. Enquadramento automático e regra de precisão continuam pendentes de implementação/validação; produção não foi alterada nestes testes.
