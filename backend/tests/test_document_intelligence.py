from app.services.document_intelligence.correios import UF_NAMES,matches,parse
from app.services.document_intelligence.reader import DocumentPage
from app.services.tabela_frete.analise import adicionar_diagnostico_confianca


def fixture_pages():
    pages=[]
    for number,(uf,name) in enumerate(UF_NAMES,start=1):
        rows=[]
        for matrix in range(2):
            for end in range(1,16):
                label=f"Até {end}" if end==1 else f"Acima de {end-1} até {end}"
                values=" ".join(f"{10+matrix+end+column/100:.2f}".replace(".",",") for column in range(28))
                rows.append(f"{label} {values}")
            rows.append("kg excedente ou fração "+" ".join("5,10" for _ in range(28)))
        text=f"EMPRESA BRASILEIRA DE CORREIOS E TELÉGRAFOS\nTARIFA - MALOTE\nOrigem: {name}\nCAPITAL - CAPITAL\n"+"\n".join(rows)
        pages.append(DocumentPage(number,text,"pdf_layout"))
    pages.append(DocumentPage(28,"EMPRESA BRASILEIRA DE CORREIOS E TELÉGRAFOS SERVIÇO DE MALOTE Emissão: 16/04/2026 Vigência: 12/04/2026\nDiurna entre 08 e 12 horas: acréscimo de R$ 17,65 por visita/percurso\nIndenização Automática: R$ 100,00\nConsultar aba de CEP Capital","pdf_layout"))
    return pages


def test_extracts_multipage_uf_weight_matrix_without_fixed_columns():
    pages=fixture_pages(); assert matches(pages)
    result=parse(pages)
    assert result["formato"]=="correios_uf_peso_v1"
    assert result["estatisticas"]=={"paginas":28,"origens":27,"matrizes":54,"faixas":864,"tarifas":24192,"taxas":1}
    assert result["extraction_errors"]==[]
    first=result["matrizes"][0]["capital_capital"][0]
    assert first["faixa"]=={"peso_inicial_kg":0,"peso_final_kg":1.0,"tipo":"FAIXA"}
    assert first["valores"]["LOCAL"]==11.0
    assert first["source"]["page"]==1


def test_missing_complementary_capital_zip_does_not_discard_extracted_tariffs():
    data=parse(fixture_pages())
    diagnosed=adicionar_diagnostico_confianca({"dados_extraidos":data,"confianca_extracao":.98,"campos_com_duvida":["faixas_cep_capital"],"erros_validacao":[],"resumo":data["estatisticas"]})
    assert diagnosed["diagnostico_confianca"]["aceito_para_cadastro"] is True
    assert diagnosed["diagnostico_confianca"]["nivel"]=="revisao"
    assert diagnosed["diagnostico_confianca"]["motivos"][0]["impeditivo"] is False
