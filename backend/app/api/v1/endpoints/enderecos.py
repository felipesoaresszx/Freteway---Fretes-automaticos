import re

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import require_permission
from app.services.consulta_cep import consultar_cep

router = APIRouter(prefix="/enderecos", tags=["enderecos"])


@router.get("/cep/{cep}")
async def obter_endereco_por_cep(cep: str, _user=Depends(require_permission("cotacoes.manage"))):
    digits = re.sub(r"\D", "", cep)
    if len(digits) != 8:
        raise HTTPException(status_code=422, detail="CEP deve conter 8 dígitos.")
    return await consultar_cep(digits)
