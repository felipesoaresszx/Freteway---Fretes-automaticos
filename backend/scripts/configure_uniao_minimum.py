"""Configura o piso final somente na tabela ativa da Uniao, com auditoria."""
import asyncio
import json
from copy import deepcopy

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.models import AuditoriaTabela, TabelaFrete, TabelaFreteDadosImportados, Transportadora
from app.services.tabela_frete.contrato import key
from app.services.tabela_frete.calculo_universal import calcular_universal


async def main():
    async with AsyncSessionLocal() as db:
        carriers = (await db.scalars(select(Transportadora).where(
            Transportadora.deleted_at.is_(None), Transportadora.ativa.is_(True),
        ))).all()
        carriers = [c for c in carriers if key(c.nome) == 'UNIAO TRANSPORTES']
        if len(carriers) != 1:
            raise RuntimeError('Esperado exatamente um cadastro ativo Uniao Transportes')
        tables = (await db.scalars(select(TabelaFrete).where(
            TabelaFrete.transportadora_id == carriers[0].id, TabelaFrete.status == 'active',
        ).with_for_update())).all()
        if len(tables) != 1:
            raise RuntimeError('Esperada exatamente uma tabela ativa Uniao')
        table = tables[0]
        imported = await db.scalar(select(TabelaFreteDadosImportados).where(
            TabelaFreteDadosImportados.tabela_frete_id == table.id,
        ).with_for_update())
        if not imported or (imported.dados.get('metadata') or {}).get('parser') != 'proposta_cif_docx_v1':
            raise RuntimeError('Formato da proposta Uniao inesperado')
        data = deepcopy(imported.dados)
        before = deepcopy(data.get('pricing_rules') or {})
        data['pricing_rules'] = {**before, 'minimum_freight_basis': 'TOTAL'}
        # Verifica o motor instalado antes de persistir a nova configuracao.
        for city, uf, cep, weight, nf, volume in [
            ('Pinheiro', 'MA', '65200000', 3, 788.90, .02773),
            ('Olinda Nova do Maranhao', 'MA', '65223000', 4, 1222.90, .056202),
            ('Belem', 'PA', '66913430', 115, 1026, .2376),
        ]:
            result = calcular_universal(data, dict(origem_uf='SP', origem_cidade='Guarulhos',
                origem_cep='07042180', destino_cidade=city, destino_uf=uf, destino_cep=cep,
                peso=weight, valor_nf=nf, volume_total_m3=volume))
            if result.get('status') != 'success' or result.get('valor_total') != 250:
                raise RuntimeError('Motor nao validou o piso final: ' + json.dumps(result))
        if before == data['pricing_rules']:
            print('UNIAO_MINIMUM_ALREADY_CONFIGURED')
            return
        imported.dados = data
        db.add(AuditoriaTabela(tabela_frete_id=table.id, acao='editada',
            descricao='Minimo aplicado ao total final da Uniao conforme referencias 29290, 30067 e 28243; solicitado pelo usuario em 09/10/2026.',
            alteracoes=json.dumps({'pricing_rules': {'anterior': before, 'novo': data['pricing_rules']}}, ensure_ascii=True)))
        await db.commit()
        print(json.dumps({'status': 'configured', 'table_id': table.id, 'minimum_freight_basis': 'TOTAL'}))


if __name__ == '__main__':
    asyncio.run(main())
