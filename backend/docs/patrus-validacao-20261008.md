# Validação local Patrus — 08/10/2026

Executada com a planilha comercial real disponível em `tabelas_trans/Tabela Patrus*.xlsx`, versão V 2.7.7. A descoberta da fixture foi corrigida para buscar nessa pasta e manter compatibilidade com arquivos na raiz.

## Resultado

- 19 testes Patrus passaram, sem testes ignorados.
- 78 testes passaram no conjunto Patrus, cálculo de tabelas e integração Sankhya.
- Conferidos: seleção de nove regiões por CEP, cubagem de 300 kg/m³, excedente acima de 150 kg, pedágio, CT-e, GRIS, TSO, TDA condicional e rejeição de destino sob consulta.
- Importação preservou 1.132 registros TDA, 194 TRT e 839 raízes CNPJ de TAG. TAG tem valor e mínimo zero na tabela.
- Referência já registrada nos testes como proveniente do portal: Rio de Janeiro/RJ, CEP 22281033, peso real 10 kg, volume 0,185193 m³ e nota de R$ 890,00. Peso considerado 55,558 kg, frete base R$ 74,55, ICMS calculado R$ 23,12 e total R$ 192,64. O teste reproduziu esses valores; não houve nova consulta ao portal nesta execução.
- Cenário Sankhya com CEP 17830089, peso 4 kg, nota R$ 519,40 e dimensões 0,27 × 0,32 × 0,46 m: total R$ 92,61, com região SP - Interior resolvida pelo CEP.

## Pendências e alcance

TDE, TDE2 e TDE3 continuam sem listas de incidência no documento. Percentuais e mínimos estão preservados, mas a tabela permanece `NEEDS_REVIEW`. O documento não publica prazo em dias; o cálculo retorna zero conforme o contrato existente, sem comprovar prazo comercial.

Validação local do importador e do cálculo, sem checagem do cadastro, vigência ou tabela persistida em produção e sem validação da interface. Nenhum cadastro foi aprovado ou alterado.

Usada configuração alternativa porque `backend/pytest.ini` contém uma linha inválida preexistente. Esse arquivo foi preservado. Comando executado em `backend`:

```powershell
.\.venv\Scripts\python.exe -m pytest -c pyproject.toml -o pythonpath=. -o asyncio_default_fixture_loop_scope=function -p no:cacheprovider tests/test_patrus_table.py tests/test_tabela_frete_calculo.py tests/test_integracao_sankhya.py -q
```

Avisos emitidos: extensões de formatação não suportadas pelo OpenPyXL e uso preexistente de `datetime.utcnow()` em testes.
