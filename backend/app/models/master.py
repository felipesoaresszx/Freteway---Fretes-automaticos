import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import MasterBase


def _uuid() -> str:
    return str(uuid.uuid4())


class Tenant(MasterBase):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    codigo_login: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    access_code_hash: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True, index=True)
    nome: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str | None] = mapped_column(String(80), unique=True, nullable=True)
    razao_social: Mapped[str | None] = mapped_column(String(255), nullable=True)
    schema_name: Mapped[str] = mapped_column(String(63), unique=True)
    connection_string: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status_assinatura: Mapped[str] = mapped_column(String(30), default="ativa", index=True)
    sankhya_api_key_hash: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True, index=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    empresas: Mapped[list["TenantEmpresa"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    theme: Mapped["CompanyTheme | None"] = relationship(back_populates="tenant", cascade="all, delete-orphan", uselist=False)


class CompanyTheme(MasterBase):
    __tablename__ = "company_themes"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    subtitle: Mapped[str] = mapped_column(String(160), default="Gestão de Fretes")
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    icon_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    favicon_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    primary_color: Mapped[str] = mapped_column(String(7), default="#2563EB")
    secondary_color: Mapped[str] = mapped_column(String(7), default="#111827")
    accent_color: Mapped[str] = mapped_column(String(7), default="#3B82F6")
    background_color: Mapped[str] = mapped_column(String(7), default="#0F1115")
    surface_color: Mapped[str] = mapped_column(String(7), default="#171A1F")
    text_color: Mapped[str] = mapped_column(String(7), default="#F8FAFC")
    muted_text_color: Mapped[str] = mapped_column(String(7), default="#94A3B8")
    border_color: Mapped[str] = mapped_column(String(7), default="#303642")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant: Mapped[Tenant] = relationship(back_populates="theme")


class CompanyIdentificationAttempt(MasterBase):
    __tablename__ = "company_identification_attempts"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    tenant_id: Mapped[str | None] = mapped_column(ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True, index=True)
    code_fingerprint: Mapped[str] = mapped_column(String(16), index=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True, index=True)
    device: Mapped[str | None] = mapped_column(Text, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    reason: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class TenantEmpresa(MasterBase):
    __tablename__ = "tenant_empresas"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    codigo_empresa_sankhya: Mapped[str] = mapped_column(String(80), index=True)
    razao_social: Mapped[str] = mapped_column(String(255))
    cnpj: Mapped[str] = mapped_column(String(14), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    tenant: Mapped[Tenant] = relationship(back_populates="empresas")
