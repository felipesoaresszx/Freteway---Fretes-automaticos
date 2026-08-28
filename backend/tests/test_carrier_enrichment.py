from pathlib import Path
import pytest

from app.services.enrichment.config import CONFIG
from app.services.enrichment.detectors import BranchDetector, ContactDetector, CoverageDetector, FreightTableDetector, IntegrationDetector
from app.services.enrichment.normalization import cep_in_range, normalize_cep, normalize_cnpj, normalize_state, states_in_text
from app.services.enrichment.ports import CrawledPage

HTML=Path(__file__).parent.joinpath("fixtures/carrier_enrichment.html").read_text(encoding="utf-8")
PAGES=[CrawledPage("https://carrier.example/abrangencia",200,HTML)]

def test_normalization_and_range():
    assert normalize_cnpj("12.345.678/0001-90")=="12345678000190"
    assert normalize_cnpj("123")==None
    assert normalize_cep("01000-000")=="01000000"
    assert cep_in_range("06700-000","01000-000","19999-999")
    assert not cep_in_range("20000-000","01000-000","19999-999")

def test_state_detection():
    assert normalize_state("São Paulo")=="SP"
    assert states_in_text("São Paulo, Paraná, Santa Catarina e Rio Grande do Sul")=={"SP","PR","SC","RS"}

def test_integration_detection():
    kinds={item.kind for item in IntegrationDetector().detect(PAGES)}
    assert {"SSW","API_REST","API_SOAP","WEBSERVICE"} <= kinds

def test_coverage_detection_and_deduplication():
    found=CoverageDetector().detect(PAGES)
    assert {x.value for x in found if x.kind=="STATE"}=={"SP","PR","SC","RS"}
    ranges=[x for x in found if x.kind=="CEP"]
    assert len(ranges)==1 and ranges[0].metadata["cep_start"]=="01000000" and ranges[0].metadata["cep_end"]=="19999999"
    assert len({(x.kind,x.value,x.url) for x in found})==len(found)

def test_freight_table_contact_and_branch_detection():
    tables=FreightTableDetector().detect(PAGES)
    assert any(x.metadata["access"]=="PUBLIC" and x.value.endswith(".xlsx") for x in tables)
    assert any(x.metadata["access"]=="PRIVATE" for x in tables)
    assert {x.kind for x in ContactDetector().detect(PAGES)}=={"EMAIL","PHONE"}
    assert BranchDetector().detect(PAGES)[0].metadata["cnpj"]=="12345678000190"

@pytest.mark.parametrize("score,classification",[(1,"AUTO_APPROVED"),(.9,"AUTO_APPROVED"),(.7,"LIKELY"),(.4,"MANUAL_REVIEW"),(.39,"REJECTED")])
def test_confidence(score,classification): assert CONFIG.classification(score)==classification
