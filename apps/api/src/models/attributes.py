from typing import Annotated, Any, Optional
from models.types import EntityType, OrganizationType
from pydantic import BaseModel, Field, ConfigDict, model_validator
from enum import Enum


class BaseAttributes(BaseModel):
    model_config = ConfigDict(extra="allow")


class CompanyAttributes(BaseModel):
    organization_type: OrganizationType = OrganizationType.COMPANY
    legal_form: str | None = None
    jurisdiction: str | None = None
    cui: str | None = None
    registration_number: str | None = None
    incorporation_date: str | None = None
    status: str | None = None
    industry: list[str] = Field(default_factory=list)
    revenue: float | None = None
    currency: str | None = None


class PersonAttributes(BaseModel):
    date_of_birth: str | None = None
    nationality: str | None = None
    occupations: list[str] | None = Field(default_factory=list)
    public_roles: list[str] | None = Field(default_factory=list)


ATTRIBUTES_BY_TYPE: dict[EntityType, type[BaseAttributes]] = {
    EntityType.COMPANY: CompanyAttributes,
    EntityType.PERSON: PersonAttributes,
}
