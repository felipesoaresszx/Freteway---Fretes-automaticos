"""Parser semântico de matrizes UF x peso dos Correios."""

import re
from datetime import datetime

from .reader import DocumentPage

UF_NAMES=[("AC","Acre"),("AL","Alagoas"),("AM","Amazonas"),("AP","Amapá"),("BA","Bahia"),("CE","Ceará"),("DF","Distrito Federal"),("ES","Espírito Santo"),("GO","Goiás"),("MA","Maranhão"),("MG","Minas Gerais"),("MS","Mato Grosso do Sul"),("MT","Mato Grosso"),("PA","Pará"),("PB","Paraíba"),("PE","Pernambuco"),("PI","Piauí"),("PR","Paraná"),("RJ","Rio de Janeiro"),("RN","Rio Grande do Norte"),("RO","Rondônia"),("RR","Roraima"),("RS","Rio Grande do Sul"),("SC","Santa Catarina"),("SE","Sergipe"),("SP","São Paulo"),("TO","Tocantins")]
PRICE=re.compile(r"\d{1,4},\d{2}")
ROW=re.compile(r"(?m)^\s*(Até\s+\d+|Acima\s+de\s+\d+\s+até\s+\d+|kg\s+excedente\s+ou\s+fração)\s+(.+)$",re.I)


def _decimal(value:str)->float: return float(value.replace(".","").replace(",","."))


def _range(label:str)->dict:
    nums=[float(x) for x in re.findall(r"\d+",label)]
    if label.lower().startswith("até"): return {"peso_inicial_kg":0,"peso_final_kg":nums[0],"tipo":"FAIXA"}
    if label.lower().startswith("acima"): return {"peso_inicial_kg":nums[0],"peso_final_kg":nums[1],"tipo":"FAIXA"}
    return {"peso_inicial_kg":15,"peso_final_kg":None,"tipo":"KG_EXCEDENTE_OU_FRACAO"}


def parse(pages:list[DocumentPage])->dict:
    matrices=[]; fields=[]; errors=[]
    for page,(origin_uf,origin_name) in zip(pages[:27],UF_NAMES):
        rows=[]
        for match in ROW.finditer(page.text):
            values=[_decimal(x) for x in PRICE.findall(match.group(2))]
            if len(values)!=28:
                errors.append({"page":page.number,"field":"tarifas","reason":"expected_28_values","found":len(values),"text":match.group(0)[:300]})
                continue
            destinations=["LOCAL","ESTADUAL_DIVISA",*[uf for uf,_ in UF_NAMES if uf!=origin_uf]]
            rows.append({"faixa":_range(match.group(1)),"valores":dict(zip(destinations,values)),"source":{"page":page.number,"method":page.method,"text":match.group(0).strip()[:2000]},"confidence":.99})
        if len(rows)!=32:
            errors.append({"page":page.number,"field":"faixas_peso","reason":"expected_32_rows","found":len(rows)})
        matrices.append({"origem":{"uf":origin_uf,"nome":origin_name},"capital_capital":rows[:16],"capital_interior_e_demais":rows[16:32],"source":{"page":page.number,"method":page.method},"confidence":.98 if len(rows)==32 else .65})
    full="\n".join(page.text for page in pages)
    dates=re.findall(r"\b\d{2}/\d{2}/\d{4}\b",pages[-1].text)
    optional=[]
    for period,value in re.findall(r"(08\s+e\s+12|14\s+e\s+18|18\s+e\s+20).*?R\$\s*([\d.,]+)",pages[-1].text,re.I):
        optional.append({"tipo":"COLETA_ENTREGA_PROGRAMADA","periodo":period,"valor_por_visita_percurso":_decimal(value),"confidence":.98,"source":{"page":pages[-1].number,"method":pages[-1].method}})
    fields.extend([
        {"field":"transportadora","value":"EMPRESA BRASILEIRA DE CORREIOS E TELÉGRAFOS","confidence":1.0,"source":{"page":1,"text":"EMPRESA BRASILEIRA DE CORREIOS E TELÉGRAFOS","method":"pdf_layout"}},
        {"field":"servico","value":"MALOTE","confidence":1.0,"source":{"page":1,"text":"TARIFA - MALOTE","method":"pdf_layout"}},
    ])
    return {
        "formato":"correios_uf_peso_v1","schema_version":"1.0","transportadora":"EMPRESA BRASILEIRA DE CORREIOS E TELÉGRAFOS","servico":"MALOTE",
        "vigencia":{"inicio":datetime.strptime(dates[1],"%d/%m/%Y").date().isoformat() if len(dates)>1 else None,"emissao":datetime.strptime(dates[0],"%d/%m/%Y").date().isoformat() if dates else None},
        "matrizes":matrices,"taxas_adicionais":optional,"regras":{"valor_basico":{"peso_referencia_kg":2,"minimo_remessas_mes":8},"indenizacao_automatica":100.0,"cep_capital":{"status":"documento_complementar_necessario","evidencia":"Consultar aba de CEP Capital"}},
        "field_evidence":fields,"extraction_errors":errors,"missing_fields":["faixas_cep_capital"],
        "estatisticas":{"paginas":len(pages),"origens":len(matrices),"matrizes":len(matrices)*2,"faixas":sum(len(m["capital_capital"])+len(m["capital_interior_e_demais"]) for m in matrices),"tarifas":sum((len(m["capital_capital"])+len(m["capital_interior_e_demais"]))*28 for m in matrices),"taxas":len(optional)},
        "document_fingerprint":{"document_type":"freight_table","carrier":"CORREIOS","layout":"origin_pages_with_weight_rows_and_uf_columns","headers":["PESO","LOCAL","ESTADUAL_DIVISA","UF_DESTINO"],"extra_sections":["SERVIÇOS OPCIONAIS","OUTRAS INFORMAÇÕES","ASSUNTOS GERAIS"]},
        "pipeline":[{"stage":"file_read","status":"success","pages":len(pages)},{"stage":"layout_extraction","status":"success"},{"stage":"classification","status":"success","format":"correios_uf_peso_v1"},{"stage":"normalization","status":"success","tariffs":sum((len(m["capital_capital"])+len(m["capital_interior_e_demais"]))*28 for m in matrices)},{"stage":"validation","status":"partial" if errors else "success","errors":len(errors)}],
    }


def matches(pages:list[DocumentPage])->bool:
    head=" ".join(page.text for page in pages[:2]).upper()
    return "EMPRESA BRASILEIRA DE CORREIOS E TELÉGRAFOS" in head and "TARIFA - MALOTE" in head and "CAPITAL - CAPITAL" in head
