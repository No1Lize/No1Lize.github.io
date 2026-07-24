import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class CoreMixin:
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(300), index=True)
    aliases: Mapped[list[str]] = mapped_column(JSON, default=list)
    summary: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="active")
    data_confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1)


class Source(Base):
    __tablename__ = "sources"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(240))
    source_type: Mapped[str] = mapped_column(String(40))
    base_url: Mapped[str] = mapped_column(Text, unique=True)
    access_method: Mapped[str] = mapped_column(String(30))
    reliability_level: Mapped[int] = mapped_column(Integer)
    update_frequency: Mapped[str] = mapped_column(String(40))
    terms_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    robots_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    requires_api_key: Mapped[bool] = mapped_column(Boolean, default=False)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)


class Sector(CoreMixin, Base):
    __tablename__ = "sectors"
    heat_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    heat_formula_version: Mapped[str | None] = mapped_column(String(30))
    completeness: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)


class Subsector(CoreMixin, Base):
    __tablename__ = "subsectors"
    sector_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sectors.id", ondelete="CASCADE"))


class Company(CoreMixin, Base):
    __tablename__ = "companies"
    english_name: Mapped[str | None] = mapped_column(String(300))
    region: Mapped[str] = mapped_column(String(60), index=True)
    headquarters: Mapped[str | None] = mapped_column(String(180))
    founded_year: Mapped[int | None] = mapped_column(Integer)
    sector_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sectors.id"))
    website: Mapped[str | None] = mapped_column(Text)
    stage: Mapped[str | None] = mapped_column(String(80))


class Person(CoreMixin, Base):
    __tablename__ = "people"
    english_name: Mapped[str | None] = mapped_column(String(300))
    role: Mapped[str | None] = mapped_column(String(300))


class Institution(CoreMixin, Base):
    __tablename__ = "institutions"
    english_name: Mapped[str | None] = mapped_column(String(300))
    region: Mapped[str] = mapped_column(String(60), index=True)
    institution_type: Mapped[str | None] = mapped_column(String(120))
    website: Mapped[str | None] = mapped_column(Text)


class FundingRound(Base):
    __tablename__ = "funding_rounds"
    __table_args__ = (UniqueConstraint("company_id", "round_type", "announced_at", "amount"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    round_type: Mapped[str] = mapped_column(String(80))
    announced_at: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    currency: Mapped[str | None] = mapped_column(String(12))
    valuation: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    is_official: Mapped[bool] = mapped_column(Boolean, default=False)
    source_ids: Mapped[list[str]] = mapped_column(JSON, default=list)


class Investment(Base):
    __tablename__ = "investments"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("institutions.id"))
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    funding_round_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("funding_rounds.id"))
    role: Mapped[str | None] = mapped_column(String(50))


class Fund(CoreMixin, Base):
    __tablename__ = "funds"
    institution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("institutions.id"))
    vintage_year: Mapped[int | None] = mapped_column(Integer)


class IpoCompany(CoreMixin, Base):
    __tablename__ = "ipo_companies"
    company_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("companies.id"))
    market: Mapped[str] = mapped_column(String(40), index=True)
    ticker: Mapped[str | None] = mapped_column(String(40), index=True)
    current_stage: Mapped[str] = mapped_column(String(120))


class IpoEvent(Base):
    __tablename__ = "ipo_events"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ipo_company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ipo_companies.id"))
    event_at: Mapped[date] = mapped_column(Date)
    market_stage: Mapped[str] = mapped_column(String(120))
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("source_documents.id")
    )


class FinancialMetric(Base):
    __tablename__ = "financial_metrics"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ipo_company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ipo_companies.id"))
    metric_name: Mapped[str] = mapped_column(String(120))
    value: Mapped[Decimal] = mapped_column(Numeric(26, 4))
    currency: Mapped[str | None] = mapped_column(String(12))
    unit: Mapped[str | None] = mapped_column(String(30))
    period: Mapped[str] = mapped_column(String(60))
    consolidation_scope: Mapped[str | None] = mapped_column(String(80))
    source_page: Mapped[str | None] = mapped_column(String(40))


class NewsItem(CoreMixin, Base):
    __tablename__ = "news_items"
    event_type: Mapped[str] = mapped_column(String(60), index=True)
    region: Mapped[str] = mapped_column(String(60), index=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    canonical_url: Mapped[str] = mapped_column(Text, unique=True)
    content_fingerprint: Mapped[str | None] = mapped_column(String(128), index=True)
    importance: Mapped[int] = mapped_column(Integer, default=0)


class Report(CoreMixin, Base):
    __tablename__ = "reports"
    report_type: Mapped[str] = mapped_column(String(80))
    markdown_path: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Concept(CoreMixin, Base):
    __tablename__ = "concepts"
    person_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("people.id"))


class Quote(Base):
    __tablename__ = "quotes"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    person_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("people.id"))
    text: Mapped[str] = mapped_column(Text)
    context_summary: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[date | None] = mapped_column(Date)
    source_document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_documents.id"))
    verification_status: Mapped[str] = mapped_column(String(40), default="verified")


class Publication(CoreMixin, Base):
    __tablename__ = "publications"
    person_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("people.id"))
    content_type: Mapped[str] = mapped_column(String(60))
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("source_documents.id")
    )


class EntityRelation(Base):
    __tablename__ = "entity_relations"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject_type: Mapped[str] = mapped_column(String(60))
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    predicate: Mapped[str] = mapped_column(String(80))
    object_type: Mapped[str] = mapped_column(String(60))
    object_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    source_ids: Mapped[list[str]] = mapped_column(JSON, default=list)


class SourceDocument(Base):
    __tablename__ = "source_documents"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"))
    canonical_url: Mapped[str] = mapped_column(Text, unique=True)
    title: Mapped[str] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    content_hash: Mapped[str] = mapped_column(String(128))
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


class Citation(Base):
    __tablename__ = "citations"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    field_name: Mapped[str] = mapped_column(String(120))
    source_document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_documents.id"))
    locator: Mapped[str | None] = mapped_column(String(240))


class SyncJob(Base):
    __tablename__ = "sync_jobs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    schedule: Mapped[str] = mapped_column(String(120))
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)


class SyncJobRun(Base):
    __tablename__ = "sync_job_runs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sync_job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sync_jobs.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(String(40), default="running")
    scanned: Mapped[int] = mapped_column(Integer, default=0)
    created: Mapped[int] = mapped_column(Integer, default=0)
    updated: Mapped[int] = mapped_column(Integer, default=0)
    skipped: Mapped[int] = mapped_column(Integer, default=0)
    conflicts: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[int] = mapped_column(Integer, default=0)
    error_detail: Mapped[dict[str, object] | None] = mapped_column(JSON)


class DataConflict(Base):
    __tablename__ = "data_conflicts"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    field_name: Mapped[str] = mapped_column(String(120))
    candidate_values: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    resolution: Mapped[dict[str, object] | None] = mapped_column(JSON)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DataRevision(Base):
    __tablename__ = "data_revisions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    revision_type: Mapped[str] = mapped_column(String(60))
    before_value: Mapped[dict[str, object] | None] = mapped_column(JSON)
    after_value: Mapped[dict[str, object]] = mapped_column(JSON)
    reason: Mapped[str] = mapped_column(Text)
    source_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
