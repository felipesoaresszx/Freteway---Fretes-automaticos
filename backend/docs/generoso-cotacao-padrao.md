# Generoso na cotação padrão

Em 02/10/2026, o cliente confirmou que a proposta comercial anexada vale para a Modial, que a coleta é de 0,20%, que área de risco e Sec-Cat ficam fora da cotação enquanto faltarem as listas e que prazo de entrega pode ficar vazio.

A cotação padrão usa a versão vigente do contrato Generoso, com origem Guarulhos/SP. O adicional de coleta de 0,20% segue os destinos indicados na proposta. A coleta fixa de R$ 12,00 continua desligada. Destinos do PA permanecem sem tarifa. A versão usada, os componentes e os avisos são devolvidos na memória do cálculo. O cadastro administrativo da tabela de documentos permanece em revisão; a cotação usa o contrato versionado da Generoso.

## Tributação aplicada

Para transporte intermunicipal ou interestadual iniciado em Guarulhos/SP, a cotação usa ICMS sobre o valor total do frete. A alíquota é 12% para destinos SP, MG, RJ, PR, SC e RS, e 7% para ES, DF, GO, MS, MT, RO e AC. A regra interestadual vem da [Resolução do Senado 22/1989](https://legis.senado.leg.br/norma/586152/publicacao?tipoDocumento=RSF&tipoTexto=ATU). Para o transporte interno paulista, a [Secretaria da Fazenda de SP informa a alíquota de 12%](https://legislacao.fazenda.sp.gov.br/Paginas/RC20026_2019.aspx). O local de início e o percurso físico determinam a incidência; veja a [Lei Complementar 87/1996](https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp87.htm) e a [consulta paulista sobre transporte de carga](https://legislacao.fazenda.sp.gov.br/Paginas/RC26111_2022.aspx).

Transporte dentro de Guarulhos exige ISS municipal e fica sem preço até parametrização específica. A [Lei Complementar 116/2003](https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp116.htm) enquadra o transporte de natureza municipal no item 16.02. O regime tributário da transportadora e eventual DIFAL ainda requerem validação fiscal; o simulador preserva esses avisos e não emite CT-e.

## Implantação

O contrato versionado precisa estar importado pela migration `041_generoso_tariff_versions`. O código precisa ser implantado para que o fluxo de cotação padrão use esse contrato. Não marcar a tabela documental parcial como ativa, pois ela não contém todos os componentes necessários para preço final.
