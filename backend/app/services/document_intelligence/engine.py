"""Orquestrador extensível do Document Intelligence Engine."""

import logging
from pathlib import Path

from . import correios
from .reader import read_pdf

logger=logging.getLogger("freteway.document_intelligence")


class DocumentIntelligenceEngine:
    def analyze(self,path:Path,file_type:str)->dict|None:
        if file_type!="pdf": return None
        pages=read_pdf(path)
        logger.info("document_stage=file_read file=%s type=pdf pages=%s",path.name,len(pages))
        if correios.matches(pages):
            result=correios.parse(pages)
            stats=result["estatisticas"]
            logger.info("document_stage=classified file=%s format=%s origins=%s ranges=%s tariffs=%s errors=%s",path.name,result["formato"],stats["origens"],stats["faixas"],stats["tarifas"],len(result["extraction_errors"]))
            return result
        logger.info("document_stage=classification file=%s format=unknown",path.name)
        return None
