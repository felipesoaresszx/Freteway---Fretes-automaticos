# Valida??o local Rispar ? 08/10/2026

- 14 testes Rispar passaram, incluindo cinco cota??es de aceita??o e tr?s refer?ncias j? registradas como provenientes do portal.
- 73 testes passaram no conjunto Rispar, c?lculo de tabelas e integra??o Sankhya; nenhum ignorado. Foram emitidos 44 avisos de uso preexistente de datetime.utcnow().
- Totais de aceita??o: R$ 421,94; R$ 749,78; R$ 515,70; R$ 892,04; R$ 124,32. Refer?ncias do portal: R$ 293,81; R$ 228,89; R$ 582,89, com prazo de tr?s dias. N?o houve nova consulta ao portal.
- Conferidos: cubagem, arredondamento, limites de peso, m?nimo de GRIS, menor faixa de CEP sobreposta, destino n?o atendido, importa??o determin?stica, preview e identifica??o dos quatro CSVs.
- Importados: 81 tarifas, 5.786 faixas de CEP, 5.016 cidades e 26 locais de coleta. Todas as siglas dos CEPs possuem tarifa; nenhuma faixa est? invertida; todas as tarifas possuem faixas de peso.

## Pend?ncias

Goi?nia/GO (74000001?74899999) e Trindade/GO (75380001?75394999) apontam para PANR, cuja tarifa est? cadastrada em MT. Confirmar o v?nculo na fonte comercial antes de alterar os dados.

O contrato mant?m 11 pend?ncias abertas: faixas da Bahia; siglas RBAR/RALI/RMAI; TRT do Centro-Oeste; base do excedente; peso do ped?gio; base da TDA; m?nimo de GRIS; diverg?ncias de prazo; restri??o de origem; CST/cClassTrib; al?quotas. O README foi corrigido para refletir essas pend?ncias.

A paridade com o portal depende de calibra??es espec?ficas: taxas adicionais para SSOP, ICMS incluso em SP e regra por CNPJ para SSOP MOVEL. Os exemplos existentes passam; a aplica??o dessas regras a outras cargas n?o foi comprovada.

## Alcance e reprodu??o

Valida??o local dos CSVs e do motor, sem checagem da tabela persistida em produ??o, interface, portal ou confirma??o comercial/fiscal. Nenhum cadastro foi aprovado ou alterado. A planilha original em tests/fixtures foi aberta para verificar a estrutura das abas, sem concilia??o c?lula a c?lula com os CSVs.

O pytest.ini possui uma linha inv?lida preexistente e foi preservado. O diret?rio tempor?rio padr?o tamb?m apresentou acesso negado; a execu??o final passou com diret?rio pr?prio.

Comando executado em backend:

```powershell
python -m pytest -c pyproject.toml -o pythonpath=. -o asyncio_default_fixture_loop_scope=function -p no:cacheprovider --basetemp=tmp/rispar-validacao-20261008-a tests/test_rispar.py tests/test_tabela_frete_calculo.py tests/test_integracao_sankhya.py -q --disable-warnings
```
