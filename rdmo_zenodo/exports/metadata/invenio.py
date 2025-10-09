# invenio_v6_models_strict.py
from __future__ import annotations

from typing import Any, Literal

import attrs

from rdmo_zenodo.exports.metadata.utils import is_edtf_l0_date, is_iso_date

# ------------------------- core CV wrappers ------------------------- #

@attrs.define
class ResourceType:
    """metadata.resource_type: requires {'id': '<cv id>'}."""
    id: str

    def __attrs_post_init__(self) -> None:
        if not self.id:
            raise ValueError("resource_type.id must be a non-empty string")

@attrs.define
class Role:
    """Controlled vocabulary wrapper for roles (creators/contributors, dates, etc.)."""
    id: str
    title: dict[str, str] | None = None  # service may add i18n labels

# ------------------------- identifiers & affiliations ------------------------- #

@attrs.define
class GenericIdentifier:
    scheme: str   # e.g. 'orcid', 'isni', 'ror', 'doi', ...
    identifier: str

@attrs.define
class Affiliation:
    id: str | None = None   # CV id (preferred, if known)
    name: str | None = None # free text fallback

    def __attrs_post_init__(self) -> None:
        # One of id or name must be present
        if not (self.id or self.name):
            raise ValueError("affiliation requires either 'id' or 'name'")

# ------------------------- person_or_org & party entries ------------------------- #

PersonOrOrgType = Literal["personal", "organizational"]

@attrs.define
class PersonOrOrg:
    type: PersonOrOrgType
    given_name: str | None = None
    family_name: str | None = None
    name: str | None = None
    identifiers: list[GenericIdentifier] = attrs.field(factory=list)

    def __attrs_post_init__(self) -> None:
        if self.type == "personal":
            if not (self.given_name and self.family_name):
                raise ValueError("personal person_or_org requires given_name and family_name")
            if self.name is not None:
                raise ValueError("personal person_or_org must not set 'name'")
        else:  # organizational
            if not self.name:
                raise ValueError("organizational person_or_org requires 'name'")
            if self.given_name or self.family_name:
                raise ValueError("organizational person_or_org must not set given/family names")

@attrs.define
class Creator:
    person_or_org: PersonOrOrg
    role: Role | None = None               # optional for creators
    affiliations: list[Affiliation] = attrs.field(factory=list)

    def __attrs_post_init__(self) -> None:
        # affiliations only if personal (per docs)
        if self.person_or_org.type == "organizational" and self.affiliations:
            raise ValueError("affiliations are only allowed for personal creators")

@attrs.define
class Contributor:
    person_or_org: PersonOrOrg
    role: Role                                # required for contributors
    affiliations: list[Affiliation] = attrs.field(factory=list)

    def __attrs_post_init__(self) -> None:
        if self.person_or_org.type == "organizational" and self.affiliations:
            raise ValueError("affiliations are only allowed for personal contributors")

# ------------------------- rights, languages, subjects, dates ------------------------- #

@attrs.define
class Rights:
    # Either `id` (CV) or a free-text `title` (localized), but not both.
    id: str | None = None
    title: dict[str, str] | None = None
    description: dict[str, str] | None = None
    link: str | None = None

    def __attrs_post_init__(self) -> None:
        if bool(self.id) == bool(self.title):
            raise ValueError("rights: either 'id' or 'title' must be set, but not both")

@attrs.define
class Language:
    id: str  # ISO-639-3 code, e.g. 'eng', 'dan'

@attrs.define
class Subject:
    id: str | None = None     # CV id
    subject: str | None = None  # free keyword

    def __attrs_post_init__(self) -> None:
        if bool(self.id) == bool(self.subject):
            raise ValueError("subject: set exactly one of 'id' or 'subject'")

@attrs.define
class DateEntry:
    date: str = attrs.field(converter=is_edtf_l0_date)
    type: Role
    description: str | None = None

# ------------------------- alternate/related identifiers ------------------------- #

@attrs.define
class AlternateIdentifier:
    identifier: str
    scheme: str  # CV scheme (doi, isbn, url, ...)

@attrs.define
class RelatedIdentifier:
    identifier: str
    scheme: str                   # CV scheme
    relation_type: Role           # {'id': '<relation id>'}
    resource_type: ResourceType | None = None  # optional

# ------------------------- funding (kept minimal; docs leave room for variations) ------------------------- #

@attrs.define
class FundingRef:
    funder: dict[str, Any] | None = None  # commonly {'id': '<funder id>'}
    award: dict[str, Any] | None = None   # commonly {'id': '<award id>'} or {'number': '...', 'title': {...}}

# ------------------------- access ------------------------- #

@attrs.define
class AccessEmbargo:
    active: bool
    until: str | None = attrs.field(default=None, converter=lambda v: is_iso_date(v) if v else None)
    reason: str | None = None

    def __attrs_post_init__(self) -> None:
        if self.active and not self.until:
            raise ValueError("embargo.until (YYYY-MM-DD) is required when embargo.active is true")

@attrs.define
class AccessBlock:
    record: Literal["public", "restricted"]
    files: Literal["public", "restricted"]
    embargo: AccessEmbargo | None = None

# ------------------------- metadata & top-level payload ------------------------- #

@attrs.define
class MetadataV6:
    resource_type: ResourceType
    title: str
    publication_date: str = attrs.field(converter=is_edtf_l0_date)
    creators: list[Creator] = attrs.field(factory=list)

    description: str | None = None
    additional_descriptions: list[dict[str, Any]] = attrs.field(factory=list)
    additional_titles: list[dict[str, Any]] = attrs.field(factory=list)

    rights: list[Rights] = attrs.field(factory=list)
    contributors: list[Contributor] = attrs.field(factory=list)
    subjects: list[Subject] = attrs.field(factory=list)
    languages: list[Language] = attrs.field(factory=list)
    dates: list[DateEntry] = attrs.field(factory=list)

    version: str | None = None
    publisher: str | None = None

    alternate_identifiers: list[AlternateIdentifier] = attrs.field(factory=list)
    related_identifiers: list[RelatedIdentifier] = attrs.field(factory=list)

    sizes: list[str] = attrs.field(factory=list)
    formats: list[str] = attrs.field(factory=list)
    locations: list[dict[str, Any]] = attrs.field(factory=list)
    funding: list[FundingRef] = attrs.field(factory=list)
    references: list[str] = attrs.field(factory=list)

    def __attrs_post_init__(self) -> None:
        # minimal required fields per docs
        if not self.creators:
            raise ValueError("metadata.creators requires at least one creator")
        if not self.title:
            raise ValueError("metadata.title is required")
        if not self.resource_type or not self.resource_type.id:
            raise ValueError("metadata.resource_type.id is required")

@attrs.define
class RecordV6Payload:
    metadata: MetadataV6
    access: AccessBlock
    files: dict[str, Any] | None = None
    pids: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        d = attrs.asdict(self, recurse=True)
        # drop empties for cleaner payloads
        return {k: v for k, v in d.items() if v not in (None, "", [], {})}
