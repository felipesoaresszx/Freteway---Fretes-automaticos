# Generoso na cotação padrão

Em 02/10/2026, o cliente confirmou que a proposta comercial anexada vale para a Modial, que a coleta é de 0,20%, que área de risco e Sec-Cat ficam fora da cotação enquanto faltarem as listas e que prazo de entrega pode ficar vazio.

A cotação padrão usa a versão vigente do contrato Generoso, com origem Guarulhos/SP. O adicional de coleta de 0,20% segue os destinos indicados na proposta. A coleta fixa de R$ 12,00 continua desligada. Destinos do PA permanecem sem tarifa. A versão usada, os componentes e os avisos são devolvidos na memória do cálculo. O cadastro administrativo da tabela de documentos permanece em revisão; a cotação usa o contrato versionado da Generoso.

## Tributação aplicada

Para transporte intermunicipal ou interestadual iniciado em Guarulhos/SP, a cotação usa ICMS sobre o valor total do frete. A alíquota é 12% para destinos SP, MG, RJ, PR, SC e RS, e 7% para ES, DF, GO, MS, MT, RO e AC. A regra interestadual vem da [Resolução do Senado 22/1989](https://legis.senado.leg.br/norma/586152/publicacao?tipoDocumento=RSF&tipoTexto=ATU). Para o transporte interno paulista, a [Secretaria da Fazenda de SP informa a alíquota de 12%](https://legislacao.fazenda.sp.gov.br/Paginas/RC20026_2019.aspx). O local de início e o percurso físico determinam a incidência; veja a [Lei Complementar 87/1996](https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp87.htm) e a [consulta paulista sobre transporte de carga](https://legislacao.fazenda.sp.gov.br/Paginas/RC26111_2022.aspx).

Transporte dentro de Guarulhos exige ISS municipal e fica sem preço até parametrização específica. A [Lei Complementar 116/2003](https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp116.htm) enquadra o transporte de natureza municipal no item 16.02. O regime tributário da transportadora e eventual DIFAL ainda requerem validação fiscal; o simulador preserva esses avisos e não emite CT-e.

## Implantação

Em 05/10/2026, os resultados do portal 2701722 (R$ 104,75) e 2701731 (R$ 67,31) não foram reproduzidos pela fórmula documental anterior. Retirar a TEC isoladamente aproxima o primeiro caso, mas ainda deixa o segundo R$ 1,04 acima. Os PDFs do portal não discriminam os componentes. Após os testes controlados abaixo, a cotação padrão usa o perfil `PORTAL`; `GENEROSO_PORTAL_PRICE_VALIDATED` é `true` por padrão e pode ser definido como `false` para suspender preços automáticos.

O PDF 2701722 registra origem no CEP 07013-121; o PDF 2701731 registra 07042-180. Para evitar comparar origens diferentes, a cotação padrão aceita somente o CEP de coleta 07042-180 quando for reabilitada. A proposta importada classifica destino por cidade/UF, sem faixa de CEP; a regra de preço por CEP e por pagador do portal ainda não foi comprovada.

O portal repetiu Marataízes com origem 07042-180 na cotação 2701803 e manteve R$ 104,75; portanto, o CEP diferente da cotação 2701722 não causou a divergência. Nas cotações 2701731 e 2701809, Vitória/ES manteve R$ 67,31 com NF de R$ 1.702,70 e R$ 1.000,00, respectivamente, mantendo peso e cubagem. Isso comprova que o preço de Vitória está em uma faixa de mínimo ou sofre outra regra que neutraliza a diferença no valor da NF. Não há detalhamento de componentes nos PDFs; combinações de TEC, coleta e mínimo que reproduzem esses totais são hipóteses, não regras confirmadas.

Os testes controlados seguintes identificaram um perfil que reproduz os totais: frete base = maior entre mínimo, peso tarifável × R$/kg e percentual sobre NF; TSO = maior entre mínimo e percentual sobre NF; soma da coleta fixa de R$ 12; TEC sobre esse subtotal; ICMS por dentro. Com a tabela importada, as cotações 2701731, 2701809 e 2701832 de Vitória e 2701840 de Paraty/RJ coincidem ao centavo. As cotações de 75 kg com NF abaixo do piso do frete peso ficam R$ 0,03 abaixo do portal. O perfil `PORTAL` foi implementado, mantendo a fórmula documental para simulação e auditoria. Os adicionais e outras regiões poderão ser comparados com o portal conforme surgirem novos testes.

A cotação 2701851 para Pouso Alegre/MG (168 kg, NF de R$ 3.916,20) retornou R$ 395,13 no portal. O perfil com coleta percentual de 0,20% produziria R$ 404,68; sem esse item, produz R$ 395,17. Assim, o perfil `PORTAL` não soma o percentual de coleta. A diferença residual de R$ 0,04 está dentro da tolerância observada de arredondamento/tarifa exibida com três decimais.

A cotação 2701863 para Jales/SP (46 kg reais, 0,7944 m³, NF de R$ 1.356,00) retornou R$ 481,48; o perfil `PORTAL` produz R$ 481,61. O peso cubado de 238,32 kg governa o frete. A diferença residual é R$ 0,13. A causa desses centavos não é identificável a partir do PDF do portal, que não mostra os componentes ou a precisão interna da tarifa.

A cotação padrão exige origem no CEP 07042-180 e usa o perfil em todas as UFs com tarifa no contrato, inclusive cidades EMEX. O perfil foi comparado com ES, RJ sem EMEX, MG e SP; as outras UFs e adicionais seguem a mesma fórmula, mas ainda não têm comparação direta com o portal. O cliente fará validação progressiva e informará divergências. Não há tarifa para PA na proposta, e serviços sem regra completa continuam indisponíveis.

Em 05/10/2026, as cotações 2701974 e 2702015 para Ecoporanga/ES, CEP 29850-000, mostraram que o portal acrescenta R$ 110,00 fixos antes da TEC e do ICMS, independentemente do peso testado. O componente `ADICIONAL_PORTAL_VERIFICADO` reproduz exatamente R$ 382,28 e R$ 237,28. O portal não identifica o nome comercial do adicional. A pedido do cliente, a cobrança aplica-se ao destino Ecoporanga/ES, CEP 29850-000, independentemente do CNPJ do destinatário; outros CEPs não recebem esse adicional.

O contrato versionado precisa estar importado pela migration `041_generoso_tariff_versions`. O código precisa ser implantado para que o fluxo de cotação padrão use esse contrato. Não marcar a tabela documental parcial como ativa, pois ela não contém todos os componentes necessários para preço final.
