# Generoso: simulação e auditoria

## Fontes e instalação

O contrato inicial em `backend/data/tariffs/generoso/contract-2026.json` foi gerado de `tabelas_trans/PRAÇAS GENEROSO.xlsx` e `tabelas_trans/TABELA  GENEROSO.pdf`. A aba CIDADES contém 3.939 linhas de destinos; PRAÇAS é apenas referência; Emex contém **15 cidades** (conferido com a planilha e o PDF). O importador preserva a classificação de cada cidade. O código da praça é exibido, mas não escolhe o preço. O PDF forneceu 36 tarifas; PA está na malha, mas não tem tarifa.

A migration `041_generoso_tariff_versions` cria as tabelas de versões e operações e insere o contrato inicial de forma idempotente. Execute `alembic upgrade head`. Para importar outra revisão dos anexos, execute:

```powershell
cd backend
python scripts/import_generoso.py "../tabelas_trans/PRAÇAS GENEROSO.xlsx" "../tabelas_trans/TABELA  GENEROSO.pdf" --effective-on 2026-10-02
```

O importador usa o SHA-256 do conteúdo para evitar versões duplicadas. Ajustes e mudanças de parâmetros criam nova linha; versões anteriores permanecem disponíveis pelo `version_id` para auditar CT-e histórico. O contrato carrega os hashes dos dois anexos de origem.

## Regras de cálculo

Peso tarifável = maior entre peso real e volume em m³ × fator de cubagem. Frete peso = maior entre mínimo e peso tarifável × R$/kg. Frete valor = NF × percentual da tarifa. Cada componente monetário é arredondado a centavos com `Decimal` e `ROUND_HALF_UP`; o ICMS é obtido por dentro sobre o subtotal arredondado. CBS e IBS de 2026 aparecem somente como informação e não aumentam o frete. O sistema apenas simula e audita: a Generoso emite o CT-e.

O caso de teste de Rio de Janeiro/RJ inclui Emex automática e totaliza R$ 146,50. Os totais com o arredondamento especificado são R$ 1.172,23 para Guarulhos/SP e R$ 271,58 para Vitória/ES.

## Parâmetros e premissas editáveis

O arquivo `policy-2026.json` documenta os valores iniciais. Em produção, `GET /api/v1/generoso/contract` devolve a versão ativa. `POST /api/v1/generoso/policy` recebe `effective_on` e as chaves que serão modificadas em `parameters`, `taxes`, `lists` ou `validity`; cria uma versão nova. `POST /api/v1/generoso/adjustments` recebe `kind` (`NTC` ou `DIESEL`), `percent` e `effective_on` e cria nova tarifa. Diesel aplica a variação acumulada × peso configurado somente quando atinge o gatilho configurado. Todos esses endpoints exigem permissão `transportadoras.manage` e registram a mudança no log de auditoria.

As premissas comerciais pendentes constam em `parameters.unconfirmed_assumptions` e aparecem nos avisos de cada cálculo:

1. Piso mínimo somente no frete peso; `minimum_scope` aceita `FRETE_PESO` ou `FRETE_PESO_E_VALOR`.
2. TEC sobre frete peso mais frete valor; `tec_base` aceita `FRETE_PESO_E_VALOR` ou `FRETE_PESO`.
3. Coleta fixa de R$ 12 desligada por padrão; `collection_fixed_default` ou flag por simulação.
4. Listas de CEP de risco, cidades SecCat e destinatários TDE estão vazias; importar em `lists.risk_ceps`, `lists.seccat_cities`, `lists.tde_recipients`. SecCat exige `seccat_amount` antes de cobrar.
5. PA retorna erro `NO_TARIFF` até inclusão de tarifa confirmada.
6. Regime da transportadora não confirmado; o pedido de simulação aceita `NORMAL`, `SIMPLES_NACIONAL` ou `UNCONFIRMED`.
7. Alíquotas de ICMS estão em `taxes.icms_by_uf` e precisam validação pelo contador.

Outros adicionais, veículos dedicados, mínimos, gatilho de diesel e fator de cubagem estão em `parameters`. `adjustment_fields` define quais campos da tarifa recebem NTC/diesel (inicialmente mínimo e R$/kg). `taxes.ibs_cbs_by_year` aceita anos novos; 2027 não tem alíquota presumida. Crédito recuperável e DIFAL começam desligados. O crédito exige percentual configurado e sempre retorna o aviso “validar com contador”. DIFAL só pode ser solicitado para destinatário não contribuinte; alíquota e base devem ser configuradas antes da cobrança. `taxes.cte_group` e `taxes.validation_activation` guardam CST, cClassTrib e a data de validação, sem emitir CT-e.

## Vigência e uso

A proposta não tem data final fixa. A cotação e a auditoria ficam indisponíveis 30 dias após a última operação registrada. `POST /api/v1/generoso/operations` recebe uma referência única de CT-e e `occurred_on`; registrar uma operação requer `transportadoras.manage` e deixa log. Quando ainda não há operação, o prazo é contado da carga inicial da proposta. As simulações não são consideradas operações.

`POST /api/v1/generoso/quote` e `/audit` exigem `cotacoes.manage`. A auditoria recebe também `charged_total`, data opcional do CT-e (`cte_date`) e, quando conhecidos, `cte_components`; escolhe a versão vigente na data e devolve diferença absoluta, percentual e o componente com maior divergência. Falta ou avaria só é aceita quando anotada no CT-e na entrega.

## Referências fiscais verificadas em 02/10/2026

- [Receita Federal: reforma tributária do consumo](https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/acoes-e-programas/programas-e-atividades/reforma-tributaria-do-consumo/entenda): alíquotas de teste de 2026 e compensação com PIS/Cofins.
- [Receita Federal: Simples Nacional em 2026](https://www.gov.br/receitafederal/pt-br/assuntos/noticias/2026/agosto/simples-nacional-nfs-e-nacional-sera-obrigatoria-para-me-e-epp-a-partir-de-1o-de-novembro-de-2026): regras de CBS/IBS para optantes passam a produzir efeitos em 2027.
- [Portal do CT-e](https://www.cte.fazenda.gov.br/portal/informe.aspx?informe=6): NT 2026.002 v1.01 e adiamento de validações. A obrigação e o leiaute do documento cabem à emissora do CT-e.
