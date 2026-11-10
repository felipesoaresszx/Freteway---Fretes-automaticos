"""Aplica a malha e precisão da Econômica verificadas nas referências SSW."""
import asyncio
import json
from copy import deepcopy
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.models import AuditoriaTabela, TabelaFrete, TabelaFreteDadosImportados, Transportadora
from app.services.tabela_frete.calculo_universal import calcular_universal

CASES = [
    ('Fortaleza', '60866607', 161, 1755.10, 7*.30*.36*.44, 326.09),
    ('Iguatu', '63500068', 58, 575.90, 2*.30*.36*.44+.25*.24*.34, 323.24),
    ('Eusebio', '61760000', 608, 18996, 41*.34*.57*.57, 2156.02),
    ('Pacatuba', '61802530', 105, 3213, 7*.57*.34*.57, 438.31),
]

def configure(data):
    data = deepcopy(data)
    assert data['metadata']['parser'] == 'tabela_combinada_pdf_v1'
    assert any('CO236686' in d.get('source', {}).get('contract_codes', []) for d in data['destinations'])
    for collection in ('destinations', 'pracas'):
        for destination in data.get(collection, []):
            if destination.get('origin_code') != 'GRUP':
                continue
            if destination.get('destination_code') == 'FORP':
                destination['cities'] = sorted(set(destination.get('cities', []) + ['EUSEBIO', 'PACATUBA']))
            elif destination.get('destination_code') in ('FORI', 'SOBI'):
                conditions = destination.setdefault('conditions', {})
                conditions['excluded_cities'] = sorted(set(conditions.get('excluded_cities', []) + ['EUSEBIO', 'PACATUBA']))
    data['pricing_rules'] = {**data.get('pricing_rules', {}), 'cubage_volume_decimal_places': 4}
    return data

def validate(data):
    for city, cep, weight, nf, volume, expected in CASES:
        result = calcular_universal(data, dict(origem_cidade='Guarulhos', origem_uf='SP', origem_cep='07042180', destino_cidade=city, destino_uf='CE', destino_cep=cep, peso=weight, valor_nf=nf, volume_total_m3=volume))
        assert result['valor_total'] == expected, (city, result, expected)

async def main():
    async with AsyncSessionLocal() as db:
        carrier = await db.scalar(select(Transportadora).where(Transportadora.cnpj_cpf == '70037379000947', Transportadora.ativa.is_(True), Transportadora.deleted_at.is_(None)))
        assert carrier is not None
        tables = list((await db.scalars(select(TabelaFrete).where(TabelaFrete.transportadora_id == carrier.id, TabelaFrete.status == 'active').with_for_update())).all())
        assert len(tables) == 1
        table = tables[0]
        imported = await db.scalar(select(TabelaFreteDadosImportados).where(TabelaFreteDadosImportados.tabela_frete_id == table.id).with_for_update())
        before = deepcopy(imported.dados)
        after = configure(before)
        validate(after)
        if before == after:
            print('ECONOMICA_ALREADY_CONFIGURED')
            return
        imported.dados = after
        old_version = table.versao
        table.versao = old_version + '.economica-20261014'
        db.add(AuditoriaTabela(tabela_frete_id=table.id, acao='editada', descricao='Eusebio e Pacatuba na praca FORP e volume com quatro casas decimais, conforme referencias SSW 013292, 013584, 013657, 013688 e 013700; correcao solicitada pelo usuario em 14/10/2026.', alteracoes=json.dumps({'before': before, 'after': after, 'version_before': old_version, 'version_after': table.versao}, ensure_ascii=True)))
        await db.commit()
        print(json.dumps({'status': 'configured', 'table_id': table.id, 'version': table.versao}))

if __name__ == '__main__':
    asyncio.run(main())
