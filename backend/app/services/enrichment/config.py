from dataclasses import dataclass, field


@dataclass(frozen=True)
class EnrichmentConfig:
    source_scores: dict[str, float] = field(default_factory=lambda: {
        "ANTT": 1.0, "OFFICIAL_DOCUMENTATION": 1.0, "OFFICIAL_WEBSITE": .95,
        "PDF": .95, "PORTAL": .95, "BUSINESS_DIRECTORY": .50,
        "SEARCH_ENGINE": .40, "INFERRED": .25, "MANUAL": 1.0,
    })
    validity_days: dict[str, int] = field(default_factory=lambda: {
        "website": 90, "integration": 30, "coverage": 30, "freight_table": 30, "branch": 90,
    })
    completion_weights: dict[str, int] = field(default_factory=lambda: {
        "website": 15, "coverage": 25, "integration": 25,
        "freight_table": 15, "branch": 10, "contact": 10,
    })
    crawl_timeout: float = 10.0
    crawl_max_pages: int = 30
    crawl_max_depth: int = 2
    crawl_rate_limit_seconds: float = .25

    def classification(self, score: float) -> str:
        if score >= .90: return "AUTO_APPROVED"
        if score >= .70: return "LIKELY"
        if score >= .40: return "MANUAL_REVIEW"
        return "REJECTED"


CONFIG = EnrichmentConfig()
