from typing import Annotated, Any, Optional
from models.attributes import ATTRIBUTES_BY_TYPE, BaseAttributes
from models.types import ClaimStatus, ClaimType, EntityType, Predicate, SourceType
from pydantic import BaseModel, Field, ConfigDict, model_validator
from enum import Enum

from uuid import UUID, uuid4, uuid6


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
    archived_url: str = Field(..., description="")
    content: str = Field(..., description="content")
    language: str = Field(..., description="lang")


class Claim(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    type: ClaimType

    subject: Entity | list[Entity]
    predicate: Predicate | str
    claim_text: str = Field(..., description="AI inference connection, summarization")
    references: list[Entity] | None

    source: list[Source]
    claim_status: ClaimStatus = ClaimStatus.UNVERIFIED
    confidence: float = Field(..., default=None, ge=0, le=1)
