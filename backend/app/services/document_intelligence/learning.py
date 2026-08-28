"""Aprende somente estrutura/aliases; valores comerciais nunca são copiados."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import DocumentPattern,TabelaFrete


async def learn_structure(db:AsyncSession,tabela:TabelaFrete,dados:dict)->DocumentPattern|None:
    format_code=dados.get("formato"); fingerprint=dados.get("document_fingerprint")
    if not format_code or not fingerprint: return None
    item=await db.scalar(select(DocumentPattern).where(DocumentPattern.carrier_id==tabela.transportadora_id,DocumentPattern.document_type=="freight_table",DocumentPattern.format_code==format_code))
    if item:
        item.fingerprint=fingerprint; item.occurrences+=1
    else:
        item=DocumentPattern(carrier_id=tabela.transportadora_id,document_type="freight_table",format_code=format_code,fingerprint=fingerprint,learned_aliases={})
        db.add(item)
    return item
