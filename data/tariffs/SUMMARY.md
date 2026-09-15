# Sumário da Extração de Dados - ALFA e RISPA

## Arquivos Gerados

### ALFA (TABELA ALFA.pdf)
- `data/tariffs/alfa/metadata.json` - Metadados da transportadora
- `data/tariffs/alfa/destinos.json` - 204 destinos com códigos de tarifa
- `data/tariffs/alfa/faixas_peso.json` - 16 zonas com 5 faixas de peso cada
- `data/tariffs/alfa/percentuais.json` - 3 registros (frete_valor, gris padrão, gris RJ)
- `data/tariffs/alfa/taxas_fixas.json` - Vazio (não identificado no PDF)
- `data/tariffs/alfa/taxas_globais.json` - Vazio (não identificado no PDF)
- `data/tariffs/alfa/adicionais.json` - Vazio (não identificado no PDF)
- `data/tariffs/alfa/prazos.json` - Vazio (NÃO EXISTE no PDF)
- `data/tariffs/alfa/README.md` - Pendências

### RISPA (TABELA RISPA TODO BRASIL V1 26.xlsx)
- `data/tariffs/rispa/metadata.json` - Metadados da transportadora
- `data/tariffs/rispa/resolucao_destino_cep.json` - 5786 faixas de CEP
- `data/tariffs/rispa/resolucao_destino_cidades.json` - 5016 cidades atendidas (fallback)
- `data/tariffs/rispa/faixas_peso.json` - 81 zonas com faixas de peso
- `data/tariffs/rispa/percentuais.json` - 81 percentuais (gris_advalorem por zona)
- `data/tariffs/rispa/taxas_fixas.json` - 81 taxas fixas por zona
- `data/tariffs/rispa/taxas_globais.json` - Vazio (não identificado)
- `data/tariffs/rispa/adicionais.json` - Vazio (não identificado)
- `data/tariffs/rispa/prazos.json` - Vazio (não identificado)
- `data/tariffs/rispa/README.md` - Pendências

## Status
✅ Extração concluída
⚠️ Alguns campos não foram identificados nos documentos (listados nos README.md)
