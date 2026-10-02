from __future__ import annotations

import logging
import time
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.observability import log_event
from app.models.models import AnaliseTabelaEvento, DocumentoFrete, ProcessamentoJob, TabelaFrete, Transportadora
from app.services.tabela_frete.analise import (
    AnaliseDocumentoError,
    adicionar_diagnostico_confianca,
    analisar_documento_local,
    combinar_resultados_documentos,
)
from app.services.tabela_frete.table_engine.extraction.document import extract_document
from app.services.tabela_frete.tabela_import import normalizar_preview
from app.services.tabela_frete.rispar import build_contract as build_rispar_contract
from .ai_analysis.normalizer import normalize_ai_analysis
from .ai_analysis.provider import get_ai_provider
from .ai_analysis.testing import TableTestService
from .ai_analysis.validation import validate_ai_contract
from .ai_analysis.v3 import (
    V3TableTestService,
    normalize_ai_analysis_v3,
    requires_v3,
    validate_ai_contract_v3,
)


logger = logging.getLogger("freteway.table_analysis")


def _rispar_sources(documents: list[DocumentoFrete], storage: Path) -> dict[str, Path]:
    expected = {
        "tarifas": "tarifas_por_sigla", "ceps": "faixas_cep",
        "cidades": "cidades_atendidas", "coletas": "coleta",
    }
    sources: dict[str, Path] = {}
    for document in documents:
        name = document.nome_arquivo.casefold()
        if document.tipo_arquivo != "csv":
            continue
        for key, marker in expected.items():
            if marker in name:
                sources[key] = (storage.resolve() / document.caminho_storage).resolve()
    return sources


class TableAnalysisService:
    """Orquestra extração, IA, normalização, validação, testes e approval gate."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()

    async def _stage(
        self,
        job: ProcessamentoJob,
        table: TabelaFrete,
        stage: str,
        progress: int,
        *,
        status: str = "completed",
        details: dict | None = None,
    ) -> None:
        safe_details = details or {}
        job.current_step = stage
        job.progress = progress
        self.db.add(AnaliseTabelaEvento(
            job_id=job.id, tabela_frete_id=table.id, etapa=stage,
            status=status, progresso=progress, detalhes=safe_details,
        ))
        await self.db.commit()

    async def run(
        self,
        job: ProcessamentoJob,
        table: TabelaFrete,
        documents: list[DocumentoFrete],
    ) -> dict:
        started = time.perf_counter()
        storage = Path(self.settings.TABELA_FRETE_STORAGE_DIR)
        await self._stage(job, table, "ANALYZING", 10, details={"documents": len(documents)})
        log_event(logger, "table_analysis_started", job_id=job.id, carrier_id=table.transportadora_id, status="ANALYZING")
        carrier = await self.db.get(Transportadora, table.transportadora_id)
        is_rispar = bool(carrier and (
            carrier.cnpj_cpf == "34185588000117"
            or (carrier.codigo or "").casefold() == "rispar"
        ))
        rispar_sources = _rispar_sources(documents, storage) if is_rispar else {}
        if is_rispar:
            missing = sorted({"tarifas", "ceps", "cidades", "coletas"} - set(rispar_sources))
            if missing or len(documents) != 4:
                raise AnaliseDocumentoError(
                    "A tabela Rispar exige exatamente os quatro CSVs: tarifas por sigla, "
                    "faixas de CEP, cidades atendidas e coleta."
                )
            contract = build_rispar_contract(
                rispar_sources["tarifas"], rispar_sources["ceps"],
                rispar_sources["cidades"], rispar_sources["coletas"],
            )
            deterministic_results = [{
                "dados_extraidos": contract, "confianca_extracao": 1.0,
                "erros_validacao": [],
                "avisos": [item["description"] for item in contract["pendencies"]],
                "campos_com_duvida": [],
            }]
            formats = ["rispar_freight_v1"]
        else:
            deterministic_results = []
            for document in documents:
                parsed = analisar_documento_local(document, table, storage)
                parsed_data = parsed.get("dados_extraidos", {})
                if parsed_data.get("proposal_model") == "generoso_minimum_kg_nf_v1" or (
                    parsed_data.get("formato") == "canonical_freight_v1"
                    and any(region.get("proposal_model") == "generoso_minimum_kg_nf_v1"
                            for region in parsed_data.get("regions", []))
                ):
                    # Retain the deterministic tariff parser's high confidence.
                    parsed["confianca_extracao"] = 1.0
                    parsed["avisos"] = ["Tarifa base Generoso extraída deterministicamente por praça."]
                elif any(region.get("proposal_model") == "generoso_minimum_kg_nf_v1"
                         for region in parsed_data.get("regions", [])):
                    parsed["confianca_extracao"] = 1.0
                deterministic_results.append(parsed)
            formats = [
                item.get("dados_extraidos", {}).get("formato", "UNKNOWN")
                for item in deterministic_results
            ]
        await self._stage(job, table, "FORMAT_DETECTED", 25, details={"formats": formats})

        combined = combinar_resultados_documentos(deterministic_results)
        await self._stage(job, table, "EXTRACTING_RULES", 42, details={
            "documents": len(documents), "deterministic_confidence": combined.get("confianca_extracao"),
        })

        provider = get_ai_provider(self.settings)
        provider_result = None
        extracted_line_count = 0
        if provider is not None and not is_rispar:
            inputs = []
            is_deterministic_generoso = False
            per_document_limit = max(
                1, self.settings.AI_MAX_DOCUMENT_CHARS // len(documents)
            )
            for document in documents:
                path = (storage.resolve() / document.caminho_storage).resolve()
                if document.tipo_arquivo == "pdf":
                    from app.services.tabela_frete.pdf_tarifario import extract_generoso_proposal
                    if extract_generoso_proposal(path):
                        is_deterministic_generoso = True
                        break
                text = extract_document(path)
                extracted_line_count += len(text.splitlines())
                excerpt = text[:per_document_limit]
                inputs.append({"document_ref": document.nome_arquivo, "content": excerpt})
            if not is_deterministic_generoso:
                provider_result = await provider.analyze_documents(inputs, {
                    "carrier_id": table.transportadora_id,
                    "table_name": table.nome,
                    "table_code": table.codigo,
                    "table_version": table.versao,
                })

        deterministic_data = combined.get("dados_extraidos") or {}
        use_ai_contract = provider_result is not None and (
            deterministic_data.get("formato") == "documento_generico_v1"
            or bool(normalizar_preview(deterministic_data).get("requer_mapeamento_tarifario"))
        )
        validation = None
        tests = None
        if use_ai_contract:
            analysis = provider_result.analysis
            use_v3 = requires_v3(analysis)
            normalizer = normalize_ai_analysis_v3 if use_v3 else normalize_ai_analysis
            canonical = normalizer(
                analysis, carrier_id=table.transportadora_id, table_code=table.codigo,
                table_version=table.versao, default_cubage_factor=table.fator_cubagem,
            )
            validator = validate_ai_contract_v3 if use_v3 else validate_ai_contract
            validation = validator(
                canonical, analysis, minimum_confidence=self.settings.AI_MIN_CONFIDENCE,
                expected_carrier_id=table.transportadora_id,
            )
            canonical["validation"] = validation
            canonical["ai_analysis"] = analysis.model_dump(mode="json", exclude_none=True)
            combined = {
                "dados_extraidos": canonical,
                "confianca_extracao": analysis.confidence,
                "erros_validacao": validation["issues"],
                "avisos": list(dict.fromkeys([*analysis.warnings, *validation["warnings"]])),
                "campos_com_duvida": [
                    item.field for item in [*analysis.unknowns, *analysis.conflicts]
                ],
                "quantidade_documentos": len(documents),
            }
        await self._stage(job, table, "NORMALIZING", 58, details={
            "canonical_schema": (combined.get("dados_extraidos") or {}).get("canonical_schema"),
            "ai_used": provider_result is not None,
        })

        data = combined.get("dados_extraidos") or {}
        if validation is None:
            validation = data.get("validation") or {
                "status": "NEEDS_REVIEW" if combined.get("erros_validacao") else "LEGACY_VALIDATED",
                "issues": combined.get("erros_validacao") or [],
                "warnings": combined.get("avisos") or [],
                "confidence": combined.get("confianca_extracao", 0),
            }
        await self._stage(job, table, "VALIDATING", 72, details={
            "status": validation.get("status"), "issues": len(validation.get("issues") or []),
        })

        if data.get("formato") in {"tabela_frete_universal_v1", "freight_rules_v3"}:
            test_service = V3TableTestService() if data.get("formato") == "freight_rules_v3" else TableTestService()
            tests = test_service.run(data)
        else:
            tests = {"status": "LEGACY_ENGINE", "total": 0, "passed": 0, "failed": 0, "cases": []}
        combined["automatic_tests"] = tests
        await self._stage(job, table, "TESTING", 86, details={
            "status": tests["status"], "total": tests["total"], "passed": tests["passed"],
        })

        blocking = list(validation.get("issues") or [])
        if tests["status"] == "FAILED":
            blocking.append("Testes automáticos do motor canônico falharam")
        confidence = float(combined.get("confianca_extracao") or 0)
        approval_ready = not blocking and confidence >= self.settings.AI_MIN_CONFIDENCE
        partial_commercial = (
            (data.get("policy") or {}).get("quote_is_base_only") is True
            or (data.get("metadata") or {}).get("parser") == "generoso_minimum_kg_nf_v1"
            or any(region.get("proposal_model") == "generoso_minimum_kg_nf_v1" for region in data.get("regions", []))
        )
        if partial_commercial:
            approval_ready = False
            blocking.extend((data.get("policy") or {}).get("commercial_pending_items")
                            or (data.get("metadata") or {}).get("commercial_pending_items")
                            or ["Componentes comerciais da proposta estão pendentes"])
        combined["approval_gate"] = {
            "ready": approval_ready,
            "minimum_confidence": self.settings.AI_MIN_CONFIDENCE,
            "blocking_reasons": blocking,
        }
        combined["ai"] = (
            provider_result.model_dump(mode="json", exclude={"analysis"})
            if provider_result else {
                "provider": "disabled", "model": None, "prompt_version": None,
                "reason": "AI_PROVIDER não configurado; parsers determinísticos preservados",
            }
        )
        combined["preview_estruturado"] = normalizar_preview(data)
        combined = adicionar_diagnostico_confianca(combined)

        statistics = validation.get("statistics") or {}
        summary = {
            "table_type": data.get("table_type") or data.get("formato") or "UNKNOWN",
            "documents": len(documents),
            "rules": statistics.get("weight_bands", statistics.get("brackets", 0)),
            "coverage_ranges": statistics.get("destinations", statistics.get("cep_ranges", 0)),
            "surcharges": statistics.get("surcharges", len(data.get("surcharges") or [])),
            "confidence": confidence,
            "review_items": len(combined.get("campos_com_duvida") or []),
            "tests": {key: tests[key] for key in ("status", "total", "passed", "failed")},
            "approval_ready": approval_ready,
            "ai": combined["ai"],
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        }
        combined["analysis_summary"] = summary
        job.resultado = summary
        await self._stage(
            job, table, "AWAITING_APPROVAL", 95, status="waiting",
            details={"approval_ready": approval_ready, "review_items": summary["review_items"]},
        )
        log_event(
            logger, "table_analysis_completed", job_id=job.id,
            carrier_id=table.transportadora_id, provider=combined["ai"].get("provider"),
            model=combined["ai"].get("model"), duration_ms=summary["duration_ms"],
            document_count=len(documents), rule_count=summary["rules"],
            page_count=sum(item.quantidade_paginas or 0 for item in documents),
            line_count=extracted_line_count or None,
            inconsistency_count=summary["review_items"], test_count=tests["total"],
            test_result=tests["status"], input_tokens=combined["ai"].get("input_tokens"),
            output_tokens=combined["ai"].get("output_tokens"), status="AWAITING_APPROVAL",
        )
        return combined
