"""Searches the official ANTT open-data RNTRC catalog."""

import re
import time
import unicodedata
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import get_settings
from app.schemas.transportadora import somente_digitos


@dataclass(frozen=True)
class AnttCarrier:
    nome: str
    cnpj: str
    rntrc: str
    situacao: str
    categoria: str
    municipio: str | None
    uf: str | None
    cep: str | None


class AnttRntrcService:
    _resource_id: str | None = None
    _resource_expires_at: float = 0

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self.client = client
        self.settings = get_settings()

    async def search(self, query: str, limit: int = 20) -> list[AnttCarrier]:
        term = " ".join(query.split())[:120]
        if len(term) < 3:
            return []
        digits = somente_digitos(term)
        api_term = self._format_cnpj(digits) if len(digits) == 14 else term
        resource_id = await self._latest_resource_id()
        payload = await self._get_json(
            f"{self.settings.ANTT_DATA_BASE_URL.rstrip('/')}/api/3/action/datastore_search",
            params={"resource_id": resource_id, "q": api_term, "limit": min(max(limit * 5, 50), 100)},
        )
        records = payload.get("result", {}).get("records", [])
        carriers = [carrier for row in records if (carrier := self._map(row)) is not None]
        normalized_term = self._normalize_name(term)
        query_words = set(normalized_term.split())
        carriers.sort(key=lambda item: (
            0 if digits and (item.cnpj == digits or item.rntrc == digits) else 1,
            0 if self._normalize_name(item.nome) == normalized_term else 1,
            0 if self._normalize_name(item.nome).startswith(normalized_term) else 1,
            0 if query_words and query_words <= set(self._normalize_name(item.nome).split()) else 1,
            item.nome.casefold(),
        ))
        return carriers[:limit]

    @staticmethod
    def _format_cnpj(value: str) -> str:
        return f"{value[:2]}.{value[2:5]}.{value[5:8]}/{value[8:12]}-{value[12:]}"

    @staticmethod
    def _normalize_name(value: str) -> str:
        ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
        return " ".join(re.findall(r"[A-Z0-9]+", ascii_value.upper()))

    async def find(self, *, cnpj: str, rntrc: str) -> AnttCarrier | None:
        normalized_cnpj = somente_digitos(cnpj)
        normalized_rntrc = somente_digitos(rntrc)
        for query in (normalized_cnpj, normalized_rntrc):
            if len(query) < 3:
                continue
            for carrier in await self.search(query, limit=20):
                if carrier.cnpj == normalized_cnpj and carrier.rntrc == normalized_rntrc:
                    return carrier
        return None

    async def _latest_resource_id(self) -> str:
        now = time.monotonic()
        if self.__class__._resource_id and now < self.__class__._resource_expires_at:
            return self.__class__._resource_id
        fallback = self.settings.ANTT_RNTRC_RESOURCE_ID
        try:
            payload = await self._get_json(
                f"{self.settings.ANTT_DATA_BASE_URL.rstrip('/')}/api/3/action/package_show",
                params={"id": self.settings.ANTT_RNTRC_DATASET_ID},
            )
            resources = [
                item for item in payload.get("result", {}).get("resources", [])
                if item.get("datastore_active") and str(item.get("format", "")).upper() == "CSV"
            ]
            if resources:
                fallback = max(resources, key=lambda item: item.get("created") or "")["id"]
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            # The known official resource keeps search available if CKAN metadata is slow.
            pass
        self.__class__._resource_id = fallback
        self.__class__._resource_expires_at = now + 3600
        return fallback

    async def _get_json(self, url: str, *, params: dict[str, Any]) -> dict[str, Any]:
        own_client = self.client is None
        client = self.client or httpx.AsyncClient(
            timeout=self.settings.ANTT_DATA_TIMEOUT_SECONDS,
            follow_redirects=True,
            headers={"Accept": "application/json", "User-Agent": "FreteWay/1.0"},
        )
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or not payload.get("success"):
                raise ValueError("Resposta inválida do portal de dados da ANTT")
            return payload
        finally:
            if own_client:
                await client.aclose()

    @staticmethod
    def _map(row: dict[str, Any]) -> AnttCarrier | None:
        category = str(row.get("categoria_transportador") or "").strip().upper()
        document = somente_digitos(str(row.get("cpfcnpjtransportador") or ""))
        if category not in {"ETC", "CTC"} or len(document) != 14:
            return None
        name = str(row.get("nome_transportador") or "").strip()
        rntrc = somente_digitos(str(row.get("numero_rntrc") or ""))
        if not name or not rntrc:
            return None
        return AnttCarrier(
            nome=name,
            cnpj=document,
            rntrc=rntrc,
            situacao=str(row.get("situacao_rntrc") or "Não informada").strip(),
            categoria=category,
            municipio=str(row.get("municipio") or "").strip() or None,
            uf=str(row.get("uf") or "").strip().upper()[:2] or None,
            cep=somente_digitos(str(row.get("cep") or ""))[:8] or None,
        )
