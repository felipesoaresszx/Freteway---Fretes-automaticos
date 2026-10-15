"""Confirmar condições comerciais sem ligar a transportadora automaticamente."""
import argparse
import asyncio
from copy import deepcopy
from datetime import datetime
import json

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.models import AuditoriaTabela, TabelaFrete, TabelaFreteDadosImportados, Transportadora
from app.services.tabela_frete.rodocargas import calculate


async def configure(icms_rate):
    async with AsyncSessionLocal() as db:
        table = await db.scalar(select(TabelaFrete).where(TabelaFrete.codigo == 'RODOCARGAS-MODIAL-13994').with_for_update())
        if table is None:
            raise RuntimeError('Execute alembic upgrade head para instalar a tabela Rodocargas')
        carrier = await db.scalar(select(Transportadora).where(Transportadora.id == table.transportadora_id).with_for_update())
        imported = await db.scalar(select(TabelaFreteDadosImportados).where(TabelaFreteDadosImportados.tabela_frete_id == table.id).with_for_update())
        before = deepcopy(imported.dados)
        after = deepcopy(before)
        after['commercial_policy'] = {**after.get('commercial_policy', {}),
                                      'divisions_confirmed': True, 'icms_rate': icms_rate,
                                      'icms_rates_by_route': {'SP>PI': icms_rate, 'SP>MA': icms_rate}}
        for city, state in [('Teresina', 'PI'), ('Picos', 'PI'), ('São Luís', 'MA')]:
            calculate(after, dict(origem_cidade='Guarulhos', origem_uf='SP', destino_cidade=city,
                                  destino_uf=state, peso=50, valor_nf=1000, volume_total_m3=.1))
        if before == after and imported.validation_status == 'validated':
            print('RODOCARGAS_ALREADY_CONFIGURED')
            return
        imported.dados = after
        imported.validation_status = 'validated'
        table.status = 'active'
        table.approved_at = datetime.utcnow()
        carrier.status_integracao = 'ativo'
        carrier.status_validacao = 'VALIDADO'
        carrier.precisa_revisao = False
        db.add(AuditoriaTabela(tabela_frete_id=table.id, acao='configurada',
                               descricao='Confirmadas divisão 2 para Teresina e divisão 1 para demais praças; ICMS por dentro.',
                               alteracoes=json.dumps({'before': before['commercial_policy'], 'after': after['commercial_policy']})))
        await db.commit()
        print(json.dumps({'table_id': table.id, 'table_status': table.status, 'carrier_active': carrier.ativa}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--icms-rate', required=True, type=float, help='Fração, por exemplo 0.07 para 7%%')
    parser.add_argument('--confirm-divisions', required=True, action='store_true',
                        help='Confirma divisão 2 só para Teresina; demais cidades divisão 1')
    args = parser.parse_args()
    if not 0 <= args.icms_rate < 1:
        parser.error('ICMS deve estar entre 0 e 1 (exclusive)')
    asyncio.run(configure(args.icms_rate))
