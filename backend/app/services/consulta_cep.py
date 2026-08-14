"""Consulta de CEP encapsulada no backend."""
from typing import Any

import httpx
from fastapi import HTTPException, status

from app.core.config import get_settings


def _texto(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def normalizar_resposta_cep(cep: str, data: dict[str, Any]) -> dict[str, str | None]:
    cidade = _texto(data.get("city"))
    uf = _texto(data.get("state"))
    if not cidade or not uf:
        raise ValueError("Resposta sem cidade ou UF")
    return {
        "cep": cep,
        "cidade": cidade,
        "uf": uf.upper(),
        "logradouro": _texto(data.get("street")),
        "bairro": _texto(data.get("neighborhood")),
    }


async def consultar_cep(cep: str, client: httpx.AsyncClient | None = None) -> dict[str, str | None]:
    settings = get_settings()
    own_client = client is None
    http = client or httpx.AsyncClient(
        timeout=settings.CEP_CONSULTA_TIMEOUT_SECONDS,
        follow_redirects=False,
        headers={"Accept": "application/json", "User-Agent": "FreteWay/1.0"},
    )
    try:
        response = await http.get(f"{settings.CEP_CONSULTA_BASE_URL.rstrip('/')}/{cep}")
        if response.status_code == status.HTTP_404_NOT_FOUND:
            raise HTTPException(status_code=404, detail="CEP não encontrado.")
        if response.status_code == status.HTTP_400_BAD_REQUEST:
            raise HTTPException(status_code=422, detail="CEP inválido.")
        if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            raise HTTPException(status_code=503, detail="Consulta de CEP temporariamente ocupada.")
        response.raise_for_status()
        try:
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError
            return normalizar_resposta_cep(cep, data)
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=502, detail="Resposta inválida do serviço de CEP.") from exc
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="Consulta de CEP indisponível. Preencha cidade e UF manualmente.") from exc
    finally:
        if own_client:
            await http.aclose()
