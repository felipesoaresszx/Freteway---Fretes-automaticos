from __future__ import annotations

import json
from typing import Protocol

import httpx

from app.core.config import Settings, get_settings
from .prompt import PROMPT_VERSION, SYSTEM_PROMPT, build_input
from .schemas import AIAnalysisResult, AIProviderResult


class AIProviderError(RuntimeError):
    pass


class AIProvider(Protocol):
    async def analyze_documents(
        self, documents: list[dict[str, str]], carrier_context: dict[str, str]
    ) -> AIProviderResult: ...


class OpenAIResponsesProvider:
    """Adaptador externo; nenhuma decisão de publicação é delegada ao modelo."""

    def __init__(self, settings: Settings):
        if not settings.AI_API_KEY:
            raise AIProviderError("AI_API_KEY não configurada")
        self.settings = settings

    async def analyze_documents(
        self, documents: list[dict[str, str]], carrier_context: dict[str, str]
    ) -> AIProviderResult:
        schema = AIAnalysisResult.model_json_schema()
        payload = {
            "model": self.settings.AI_MODEL,
            "instructions": SYSTEM_PROMPT,
            "input": build_input(documents, carrier_context),
            "store": False,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "freight_table_analysis",
                    "description": "Regras extraídas de documentos de tabela de frete",
                    "schema": schema,
                    "strict": False,
                }
            },
        }
        headers = {
            "Authorization": f"Bearer {self.settings.AI_API_KEY}",
            "Content-Type": "application/json",
        }
        url = f"{self.settings.AI_BASE_URL.rstrip('/')}/responses"
        try:
            async with httpx.AsyncClient(timeout=self.settings.AI_TIMEOUT_SECONDS) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AIProviderError("Falha ao consultar o provider de IA") from exc

        body = response.json()
        output_text = body.get("output_text") or self._find_output_text(body)
        if not output_text:
            raise AIProviderError("Provider de IA não retornou saída estruturada")
        try:
            analysis = AIAnalysisResult.model_validate(json.loads(output_text))
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise AIProviderError("Saída da IA não corresponde ao schema obrigatório") from exc
        usage = body.get("usage") or {}
        return AIProviderResult(
            analysis=analysis,
            provider="openai",
            model=self.settings.AI_MODEL,
            prompt_version=PROMPT_VERSION,
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
        )

    @staticmethod
    def _find_output_text(body: dict) -> str | None:
        for item in body.get("output") or []:
            for content in item.get("content") or []:
                if content.get("type") == "output_text" and content.get("text"):
                    return content["text"]
        return None


def get_ai_provider(settings: Settings | None = None) -> AIProvider | None:
    settings = settings or get_settings()
    provider = settings.AI_PROVIDER.strip().lower()
    if provider in {"", "disabled", "none"}:
        return None
    if provider == "openai":
        return OpenAIResponsesProvider(settings)
    raise AIProviderError(f"AI_PROVIDER não suportado: {settings.AI_PROVIDER}")
