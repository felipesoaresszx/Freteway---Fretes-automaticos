# Ajuste comercial Carvalima confirmado nas cinco referências

Em 05/10/2026, a cotação independente 4287045 (Santa Maria das Barreiras/PA) confirmou o fator definido a partir das quatro referências anteriores, sem alteração do fator: subtotal 279,6056 × 1,162572233814173621632312438, arredondado uma vez em centavos, resulta em R$ 325,06, exatamente o portal. O cálculo anterior retornava R$ 300,66. Peso real 14 kg; volume do pedido 0,110466 m³ (portal 0,1105); peso cubado aproximadamente 33,14 kg; faixa até 40 kg, grupo 12. Nenhuma TDA/TDE/TRT correspondente nos arquivos enviados. O pedido tem CEP 68567000 e o portal 68565000; ambos foram conferidos na TRT e a tarifa é por cidade/UF.

## Aplicação autorizada

O operador autorizou aplicar o fator após confirmar PA. A calibração é aplicada em tempo de execução somente à proposta original com SHA-256 `d7fc5f3fc63af20df7d163baecf7adb7e9fff2726cc11f33f9a63454ca615c84`, parser Carvalima, cadastro aprovado/ativo e datas cadastradas em ordem. Não se estende automaticamente a documentos futuros de outra negociação. Todos os 260 destinos e suas faixas recebem o mesmo fator; as tarifas, peso real/cubado e adicionais documentados são preservados.

A composição apresenta `AJUSTE_COMERCIAL_CARVALIMA`, separado do ICMS de 7% já configurado. O ajuste cobre a diferença entre o total anterior e o total calculado pelo fator. Não é classificado como arredondamento de centavos nem substitui a alíquota legal. A origem do fator e os cinco números de referência são registrados na memória; `tax_composition_pending` permanece verdadeiro até a resposta da transportadora. É uma calibração comercial autorizada, não confirmação dos impostos ou garantia para cargas ainda não comparadas.

| Referência | UF | Total com dados do portal |
| --- | --- | ---: |
| 4286240 | RO | 754,30 |
| 4286702 | AC | 813,29 |
| 4286736 | MS | 83,66 |
| 4286765 | MT | 323,10 |
| 4287045 | PA | 325,06 |

AC exige a mesma cubagem de 0,8379 m³ informada no portal. As medidas originais da imagem somam 0,818436 m³, inferior à faixa de 250 kg cubados; a correção não altera os dados de entrada para forçar igualdade. Tabelas novas sem o hash confirmado, cadastros em rascunho e outras transportadoras conservam o comportamento anterior. Não são alterados resultados históricos ou status/validade da tabela.

## Verificação

Testes verificam as cinco referências, preservação do documento, separação do ICMS/ajuste, isolamento por proposta/status e 2.600 combinações de destino/faixa/excedente, conservando as tarifas-base. A comparação anterior de formatos e cobertura também faz parte da regressão.

Resultado: 94 testes passaram e Ruff aprovou os arquivos alterados. Backend e worker publicados em produção, com backend saudável. Conferência em leitura usando `TabelaFreteCalculoService.calcular` na tabela ativa reproduziu os cinco totais acima; não é teste HTTP autenticado nem criação de cotações. Backup de código: `/home/ubuntu/Freteway/backups/carvalima-deploy-20261005T202607Z`; backup do banco: `backups/freteway_2026-10-05_202607.dump`. Cadastro, vigência, status e histórico foram preservados.
