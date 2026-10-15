# Rodocargas — MODIAL 13994

Fonte: `TABELA RODOCARGAS.pdf`, emitida em 24/09/2026, CNPJ
07.494.510/0001-01. Cobertura extraída das células dos PDFs de PI e MA,
usando a posição do preenchimento colorido para identificar exclusões.
O arquivo `backend/data/tariffs/rodocargas/coverage.json` guarda texto,
página, coordenadas e SHA-256 dos documentos. Não há consulta de API.

Foram extraídas 223 localidades de PI (171 atendidas, 52 excluídas) e
216 de MA (168 atendidas, 48 excluídas). Município ausente também é bloqueado.
`Bom Jesus +500kg` está colorido: permanece excluído, inclusive acima de 500 kg,
conforme a instrução do usuário sobre todas as cidades marcadas.

## Cálculo

- Arredondar o volume total para três casas decimais (HALF_UP), antes da cubagem.
- Peso tarifável: maior entre peso real e volume total arredondado × 300 kg/m³.
- Divisão 1: máximo entre R$ 288 e peso tarifável × R$ 1,69.
- Divisão 2: máximo entre 90 kg e peso tarifável, multiplicado por R$ 1,23.
- Ad valorem: 5 por mil (0,5%) da NF; GRIS: 2 por mil (0,2%) da NF.
- Pedágio: R$ 0,03 por kg tarifável; outros: R$ 47 por CTRC.
- Subtotal: frete peso + ad valorem + GRIS + pedágio + outros.
- ICMS por dentro: subtotal ÷ (1 − alíquota), após os valores negociados.
- Valores monetários arredondados em centavos, half-up.

A aplicação adotada é divisão 2 só para Teresina e divisão 1 para demais
cidades atendidas. O rótulo `/ the` sugere Teresina, mas o documento não explicita
essa correspondência, portanto trata-se de interpretação do documento.
O usuário pediu pesquisa do ICMS conforme os estados: foi aplicada a regra
geral de 7% para SP → PI e SP → MA, conforme [RICMS-SP art. 52, II](https://legislacao.fazenda.sp.gov.br/Paginas/art052.aspx)
e [Resolução do Senado 22/1989](https://www.planalto.gov.br/ccivil_03/congresso/rsf/rsf%2022-89.htm).
O cálculo por dentro segue o [art. 49](https://legislacao.fazenda.sp.gov.br/Paginas/textoricms.aspx/1000).
Não foram atribuídos benefícios fiscais específicos da transportadora.
Os mínimos foram interpretados como
mínimo do frete peso; o pedágio usa peso tarifável antes do piso de 90 kg.
As referências 31448 (Chapadinha, R$ 698,90) e 31259 (Viana, R$ 713,80),
informadas pelo usuário em 15/10/2026, reproduzem exatamente o cálculo ao
arredondar o volume total para três casas decimais antes de multiplicar por
300 kg/m³. Chapadinha: 1,120213 → 1,120 m³ → 336 kg. Viana:
1,11385 → 1,114 m³ → 334,2 kg. A memória registra o volume original e o
volume utilizado. A referência Viana usa a dimensão de 120 cm registrada
na cotação de produção; a imagem fornecida contém 1120 cm nesse campo.

Não existe prazo de entrega ou término de vigência nos documentos. O prazo
retornado é nulo. O término 9999-12-31 é sentinela administrativa para tabela
sem término informado, não uma validade comercial atribuída ao PDF.

## Instalação

A revisão `044_rodocargas_table` instala o contrato e coloca a tabela em
`active`, com dados `validated` e ICMS configurado por rota. Também ativa a
transportadora para cotação, conforme solicitado em 15/10/2026.

No deploy, executar no backend:

```powershell
python -m alembic upgrade head
```

A migração já instala as condições de cálculo, sem um comando adicional de
configuração. A transportadora já fica ativa para cotar após a migração.
O script `configure_rodocargas` permanece disponível caso a transportadora
informe posteriormente uma alíquota comercial diferente; não altera `ativa`.
Os arquivos em `backend/data` são incluídos pelo Dockerfile do backend.

## Verificação local

70 testes passaram, cobrindo Rodocargas, serviço de cálculo, fluxo de tabelas
e recomendação. A alíquota de 7% está aplicada ao contrato comercial e aos
testes. A consulta da revisão local do banco falhou com conexão recusada;
nenhuma migração ou configuração de banco foi executada nesta implementação.

O `backend/pytest.ini` existente contém uma linha de e-mail inválida; a
verificação usou `-c pyproject.toml` sem alterar esse arquivo:

```powershell
python -m pytest -c pyproject.toml -p no:cacheprovider -o asyncio_default_fixture_loop_scope=function tests/test_rodocargas.py tests/test_tabela_frete_calculo.py tests/test_tabela_frete_fluxo.py tests/test_cotacao_recomendacao.py -q
```
