# Validação Maex em produção — 06/10/2026

Validação executada em transação somente de leitura, sem alteração de cadastro,
tabelas, credenciais ou código em produção.

## Ambiente e tabela

- API pública pronta; banco disponível e serviços em execução.
- MAEX TRANSPORTES ativa, integração por tabela, status cadastral `A_VALIDAR`.
- Uma tabela ativa, versão 1, vigente de 17/09/2026 a 16/12/2026.
- Documento original `Tabela_maex.xls` presente no storage configurado.
- 12 destinos/regiões e fator de cubagem de 300 kg/m³.
- 72 cenários comparando a tabela persistida com a leitura atual do documento
  original: nenhuma diferença de total ou prazo.
- As 12 combinações de praça/região calcularam com sucesso no código do endpoint
  dedicado, invocado internamente; autenticação e interface não foram testadas.
- Testes locais: 12 passaram, 4 foram ignorados por ausência da fixture real na
  raiz local. Usada configuração isolada, pois o `pytest.ini` existente contém
  uma linha inválida; arquivo existente preservado.

## Divergência demonstrada pelas imagens

Pedido 28603: peso real 49 kg, volume 0,4375 m³, nota R$ 930,30,
destino Brasília/DF, CEP 72460320. Peso cobrado de 131,25 kg.
Reprodução com o código e a tabela de produção: R$ 141,73.

| Componente | FreteWay | SSW na imagem |
| --- | ---: | ---: |
| Frete peso | 96,31 | 96,31 |
| Frete valor / seguro | 2,79 | 2,79 |
| Despacho | 17,25 | 17,25 |
| GRIS | 2,79 | 2,79 |
| Pedágio | 12,66 | 12,66 |
| Adicional de frete | 0,00 | 10,54 |
| ICMS / impostos repassados | 9,93 | 10,71 |
| Total informado | 141,73 | 153,03 |

A divergência principal está identificada: adicional de frete do SSW, ausente
do cálculo pela proposta importada. R$ 10,54 equivale aproximadamente a 8% do
subtotal de R$ 131,80. Um único exemplo não comprova percentual, base, vigência
ou gatilho contratual da cobrança.

Os componentes exibidos pelo SSW somam R$ 153,05, enquanto o total informado é
R$ 153,03. Os R$ 0,02 restantes exigem verificar arredondamento ou a memória
interna do SSW; não há evidência para escolher uma regra de arredondamento.

A busca nas linhas do documento por adicional, 8%, 0,08, ICMS, seguro e GRIS
não encontrou uma previsão explícita desse adicional de 8%. A proposta prevê
adicional por veículo dedicado, um serviço distinto e não cobrado na imagem.

## Complemento: três referências SSW e ajuste

A imagem corrigida do SSW para DF informa R$ 153,05, eliminando a divergência
de dois centavos da primeira captura. Foram recebidas também as composições
de Alexânia/GO e Araguatins/TO:

| Destino | Subtotal sem adicional/ICMS | Adicional 8% | ICMS | Total SSW |
| --- | ---: | ---: | ---: | ---: |
| Gama/DF | 131,80 | 10,54 | 10,71 | 153,05 |
| Alexânia/GO | 162,16 | 12,97 | 13,18 | 188,31 |
| Araguatins/TO | 184,65 | 14,77 | 15,01 | 214,43 |

A compatibilidade Maex aplica 8% sobre frete peso + despacho + GRIS + seguro
+ pedágio (e taxas regionais ordinárias), antes dos serviços opcionais e do
ICMS. Adicional e ICMS usam arredondamento comercial para centavos. A memória
expõe `MAEX_ADDITIONAL_FREIGHT`, percentual, base de cálculo e referências SSW.
O endpoint dedicado classifica esse componente entre as taxas obrigatórias.

As referências do portal comprovam DF/GO/TO com origem SP. Por solicitação
do usuário, o adicional foi estendido a todas as praças da Maex, incluindo
CWB/PR, CMP/SP e RBP/SP, polo e interior, preservando a alíquota de cada rota.
Essa extensão foi validada por testes de cálculo; não há imagens do SSW para
confirmar os destinos de SP/PR. A fórmula dos serviços opcionais foi preservada.
O ajuste é aplicado em memória ao contrato Maex; não altera dados importados,
vigência, cadastro ou histórico. Uma regra explícita no contrato pode sobrescrever
`pricing_rules.maex_ssw_additional_freight`.

Validação da extensão: 59 testes passaram na seleção que inclui regressões do
cálculo universal e Carvalima. Os 32 testes de Maex e do endpoint dedicado
passaram também com a planilha original recuperada temporariamente do storage
de produção, incluindo os quatro testes antes ignorados por falta da fixture.
Os três exemplos foram também conferidos usando o serviço real de cálculo e a
tabela ativa de produção em transação somente de leitura.
