from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class IntegrationType(str, Enum):
    API = "API"
    TABLE = "TABLE"
    HYBRID = "HYBRID"
    MANUAL = "MANUAL"
    RPA = "RPA"


class FreightQuoteRequest(BaseModel):
    origin_zipcode: str = Field(min_length=8, max_length=9)
    destination_zipcode: str = Field(min_length=8, max_length=9)
    weight_kg: Decimal = Field(gt=0)
    volumes: int = Field(default=1, ge=1)
    total_value: Decimal = Field(ge=0)
    cubage_m3: Decimal | None = Field(default=None, ge=0)
    products: list[dict[str, Any]] | None = None


class FreightQuoteResult(BaseModel):
    carrier_id: str
    carrier_name: str
    service_id: str | None = None
    service_name: str
    price: Decimal
    delivery_days: int | None = None
    source: str
    external_service_code: str | None = None
    metadata: dict[str, Any] | None = None


class CarrierCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    legal_name: str = Field(min_length=2, max_length=255)
    trade_name: str | None = Field(default=None, max_length=120)
    cnpj: str | None = Field(default=None, max_length=14)
    code: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,79}$")
    website: str | None = None
    logo_url: str | None = None
    phone: str | None = None
    email: str | None = None
    active: bool = True
    notes: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().lower()


class CarrierUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    legal_name: str | None = Field(default=None, min_length=2, max_length=255)
    trade_name: str | None = None
    cnpj: str | None = None
    code: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9_-]{1,79}$")
    website: str | None = None
    logo_url: str | None = None
    phone: str | None = None
    email: str | None = None
    active: bool | None = None
    notes: str | None = None
    metadata: dict[str, Any] | None = None


class CarrierOut(CarrierCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime
    updated_at: datetime


class CarrierServiceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    code: str = Field(min_length=1, max_length=80)
    external_code: str | None = None
    description: str | None = None
    service_type: str | None = None
    active: bool = True


class CarrierServiceUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    external_code: str | None = None
    description: str | None = None
    service_type: str | None = None
    active: bool | None = None


class CarrierServiceOut(CarrierServiceCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    carrier_id: str
    created_at: datetime
    updated_at: datetime


class IntegrationCreate(BaseModel):
    integration_type: IntegrationType
    adapter_code: str | None = None
    active: bool = True
    priority: int = Field(default=100, ge=0)
    configuration: dict[str, Any] = Field(default_factory=dict)

    @field_validator("adapter_code")
    @classmethod
    def normalize_adapter(cls, value: str | None) -> str | None:
        return value.strip().lower() if value else None


class IntegrationUpdate(BaseModel):
    integration_type: IntegrationType | None = None
    adapter_code: str | None = None
    active: bool | None = None
    priority: int | None = Field(default=None, ge=0)
    configuration: dict[str, Any] | None = None


class IntegrationOut(IntegrationCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    carrier_id: str
    status: str
    credential_keys: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class CredentialInput(BaseModel):
    credentials: dict[str, str]


class CredentialOut(BaseModel):
    configured: bool
    keys: list[str]
    masked: dict[str, str]


class ValidationResult(BaseModel):
    success: bool
    message: str
