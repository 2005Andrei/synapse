from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

from models.attributes import ATTRIBUTES_BY_TYPE, BaseAttributes
from models.types import ClaimStatus, ClaimType, EntityType, Predicate, SourceType


class Entity(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    type: EntityType
    description: str = Field(..., description="Description of entity")
    aliases: list[str] | None = Field(..., description="Aliases of entity")

    attributes: dict[str, Any] = Field(
        default_factory=dict,
        description="Dict of attributes and coresponding value for each entity",
    )

    @model_validator(mode="after")
    def _validate_attributes(self):
        attrs_cls = ATTRIBUTES_BY_TYPE.get(self.type)
        if attrs_cls is not None:
            validated = attrs_cls.model_validate(self.attributes)
            self.attributes = validated.model_dump(mode="json", exclude_unset=True)
        return self

    def typed_attributes(self) -> BaseAttributes | None:
        """for autocompletion"""
        attrs_cls = ATTRIBUTES_BY_TYPE.get(self.type)
        return attrs_cls.model_validate(self.attributes) if attrs_cls else None


class Source(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    type: SourceType
    title: str = Field(..., description="title")
    url: str = Field(..., description="url")
    archived_url: str | None = Field(default=None, description="")
    publisher: str | None = Field(default=None, description="who published it")
    published_at: str | None = Field(default=None, description="YYYY-MM-DD[ HH:MM]")
    content: str = Field(..., description="content")
    language: str = Field(default="ro", description="lang")


class Claim(BaseModel):
    """A statement about entities, always traceable to its sources.

    Entities and sources are referenced by id (same shape the frontend graph
    consumes), so a claim can travel on its own in a graph patch.
    """

    id: UUID = Field(default_factory=uuid4)
    type: ClaimType

    subject_ids: list[UUID]
    predicate: Predicate | str
    claim_text: str = Field(..., description="AI inference connection, summarization")
    reference_ids: list[UUID] = Field(default_factory=list)

    source_ids: list[UUID] = Field(default_factory=list)
    # The passage of the source that supports the claim, word for word. Set on
    # claims a model read out of a text, so a person can check them at a glance.
    quote: str | None = None
    claim_status: ClaimStatus = ClaimStatus.UNVERIFIED
    confidence: float | None = Field(default=None, ge=0, le=1)

    @field_validator("subject_ids", mode="before")
    @classmethod
    def _single_subject(cls, value: Any) -> Any:
        return [value] if isinstance(value, (str, UUID)) else value
