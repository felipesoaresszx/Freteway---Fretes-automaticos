# Validação da tabela Carvalima — 05/10/2026

O PDF local foi reconhecido pelo parser `carvalima_combined_v1`: 18 grupos tarifários, 260 destinos normalizados e 2.080 faixas associadas a destinos. Cobertura declarada em AC, MS, MT, PA e RO, com origem São Paulo/SP. Cidades e praças polo equivalentes foram unificadas; distritos permanecem separados quando têm tarifas diferentes.

## Cálculo

- Peso taxado: maior entre peso real e volume em m³ × 300 kg/m³.
- Faixas fechadas até 250 kg; acima disso, última faixa + quilos excedentes × tarifa por tonelada / 1.000.
- Despacho e TAS fixos, pedágio por fração de 100 kg, GRIS e ad valorem sobre a nota fiscal, extraídos por grupo tarifário.
- O GRIS de 7% do grupo 13 foi preservado; não foi substituído pela taxa de 0,5% de outros grupos.
- ICMS por dentro de 7% nas rotas documentadas de SP para AC/MS/MT/PA/RO, conforme [Resolução do Senado 22/1989](https://www.planalto.gov.br/ccivil_03/congresso/rsf/rsf%2022-89.htm). Esta aplicação segue o motor universal existente; a composição comercial ainda precisa ser confrontada com um frete cobrado pela transportadora.
- Cidade de destino necessária: o documento não traz faixas de CEP que permitam selecionar a tarifa específica com segurança.

## Conferência ilustrativa

Origem São Paulo/SP; peso real de 100 kg, sem volume cubado adicional; nota fiscal de R$ 1.000; sem serviços especiais. Valores calculados da tabela, ainda sem confronto com portal ou fatura:

| Destino | Total |
| --- | ---: |
| Campo Grande/MS | R$ 132,52 |
| Rio Branco/AC | R$ 323,11 |
| Belém/PA | R$ 673,28 |
| Alenquer/PA | R$ 834,06 |

## Confirmações e limites

O operador confirmou nesta conversa que os preços estão vigentes e solicitou um ano de vigência a partir de hoje. A vigência operacional foi definida de **05/10/2026 até 05/10/2027**, inclusive. No cadastro, o término corresponde a 05/10/2027 às 23:59:59 no horário de São Paulo. A emissão em 29/09/2026 e a vigência original até 26/02/2026 permanecem preservadas em `metadata.document_original_validity`. A confirmação é representada por `metadata.prices_confirmed_current = true`, com origem da alteração registrada em `metadata.validity_override_source`.

TDE apresenta R$ 250 nas rotas e R$ 500 nas generalidades e depende de uma relação externa de destinatários. Devolução aparece como 100% e 200%. Esses valores não são aplicados automaticamente. Serviços especiais solicitados são rejeitados enquanto suas regras não estiverem confirmadas. Não há prazo de entrega no PDF. A indicação IDA/VOLTA não foi usada para inventar rotas reversas.

## Artefatos para revisão

Executar a partir da raiz:

```powershell
python backend/scripts/validar_carvalima.py --confirm-current-prices --valid-from 2026-10-05 --valid-until 2027-10-05
```

A flag corresponde à confirmação explícita já recebida do operador. A execução produz `tmp/carvalima-validacao/tabela-normalizada.json` e `tmp/carvalima-validacao/cotacoes-conferencia.json`, sem alterar o banco. Para aplicar no ambiente em uso, importar/reanalisar o PDF, atualizar os dados da revisão com o JSON normalizado, informar a vigência válida no cadastro e aprovar/publicar pelo fluxo autenticado e auditado do FreteWay.

## Evidências

134 testes passaram e 4 testes de documentos locais não disponíveis foram ignorados. A validação inclui importação pelo fluxo do backend e 198 cenários de cálculo (18 grupos × 11 pesos), comparados com composição independente em Decimal. Também foram verificados cubagem, taxas por rota, seleção de tarifa específica em vez de estadual, distritos e rejeição de cobertura/serviços não resolvidos. A composição segue o texto da proposta; não representa homologação com cotação do portal.

Os serviços Docker locais estavam parados durante esta validação; nenhuma tabela foi ativada em banco nesta execução.

## Consulta de produção

Consulta somente de leitura por SSH em 05/10/2026: backend, worker e PostgreSQL em execução; backend saudável. Não há transportadora com Carvalima no nome ou nome fantasia, nem documento com Carvalima no nome do arquivo. O módulo `carvalima_pdf` ainda não está instalado na imagem em execução. Portanto, a Carvalima ainda não pode cotar em produção. É necessário publicar o suporte, cadastrar a transportadora e importar/aprovar/ativar a tabela pelo fluxo auditado. Nenhum cadastro ou registro de produção foi modificado nesta consulta.

## Publicação do suporte em produção

Em 05/10/2026, o usuário autorizou publicar apenas o deploy e adiar cadastro, testes de valores e ativação. O pacote restrito a sete arquivos foi aplicado sobre a revisão 186071ad0c7b62523f4f72a0b789f76c6172c0e8, após backup do banco e do código. Backend e worker foram reconstruídos; o módulo carvalima_combined_v1 foi confirmado na imagem em execução. O endereço público /health e /api/v1/health/ready respondeu HTTP 200, com banco disponível. Backup do código: /home/ubuntu/Freteway/backups/carvalima-deploy-20261005T155659Z. Dump: /home/ubuntu/Freteway/backups/freteway_2026-10-05_155659.dump. Nenhuma transportadora ou tabela foi cadastrada ou ativada neste deploy. Os arquivos do suporte estão aplicados no checkout do servidor; ainda não foram incorporados ao histórico Git.
