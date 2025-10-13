# https://inveniordm.docs.cern.ch/reference/metadata/#metadata
# https://github.com/inveniosoftware/invenio-rdm-records/tree/master/invenio_rdm_records/records/jsonschemas/records

from __future__ import annotations

from typing import Any, Literal

import attrs

from rdmo_zenodo.exports.metadata.utils import is_edtf_l0_date, is_iso_date

ISO639_1 = str
ISO639_3 = str  # ISO-639-3
IdentifierSchemes = Literal[
    'ark', 'arxiv', 'ads', 'bibcode', 'crossreffunderid', 'doi', 'ean13',
    'eissn', 'grid', 'handle', 'igsn', 'isbn', 'issn', 'istc', 'lissn',
    'lsid', 'pmid', 'purl', 'upc', 'url', 'urn', 'w3id', 'other'
]


@attrs.define
class ResourceType:
    id: str

    @classmethod
    def from_string(cls, value: str) -> ResourceType:
        return cls(id=value)

    def __attrs_post_init__(self) -> None:
        if not self.id:
            raise ValueError("resource_type.id must be a non-empty string")

@attrs.define
class Creator:
    person_or_org: PersonalPersonOrOrg | OrganizationalPersonOrOrg
    role: Role | None = None               # optional for creators
    affiliations: list[Affiliation] = attrs.field(factory=list)

    def __attrs_post_init__(self) -> None:
        if (
                isinstance(self.person_or_org, OrganizationalPersonOrOrg)
                and self.affiliations
        ):
            raise ValueError("affiliations are only allowed for personal creators")

@attrs.define
class Role:
    id: str

@attrs.define
class Affiliation:
    id: str | None = None   # CV id (preferred, if known)
    name: str | None = None # free text fallback

    def __attrs_post_init__(self) -> None:
        # One of id or name must be present
        if not (self.id or self.name):
            raise ValueError("affiliation requires either 'id' or 'name'")


@attrs.define
class PersonalPersonOrOrg:
    given_name: str
    family_name: str
    type: Literal["personal"] = "personal"
    identifiers: list[CreatorIdentifier] = attrs.field(factory=list)

    def __attrs_post_init__(self) -> None:
        if not (self.given_name and self.family_name):
            raise ValueError("personal requires given_name and family_name")

@attrs.define
class OrganizationalPersonOrOrg:
    name: str
    type: Literal["organizational"] = "organizational"
    identifiers: list[AffiliationIdentifier] = attrs.field(factory=list)

    def __attrs_post_init__(self) -> None:
        if not self.name:
            raise ValueError("organizational requires 'name'")

@attrs.define
class CreatorIdentifier:
    scheme: Literal['orcid', 'gnd', 'isni', 'ror']
    identifier: str

@attrs.define
class AffiliationIdentifier:
    scheme: Literal['isni', 'ror']
    identifier: str

@attrs.define
class AdditionTitles:
    title: str
    type: AdditionTitleType
    lang: AdditionalLang | None = None

@attrs.define
class AdditionalLang:
    id: ISO639_3

@attrs.define
class AdditionTitleType:
    id: Literal["alternative-title", "subtitle", "translated-title", "other"]
    title: dict[ISO639_1, str]

@attrs.define
class AdditionalDescriptions:
    description: str  # free-text
    type: AdditionTitleType
    lang: AdditionalLang | None = None

@attrs.define
class AdditionDescriptionType:
    id: Literal["abstract", "methods", "series-information", "table-of-contents", "technical-info", "other"]
    title: dict[ISO639_1, str]

@attrs.define
class Rights:
    id: str | None = None  # CV
    title: dict[ISO639_1, str] | None = None  # Localized human readable title
    description: dict[ISO639_1, str] | None = None  # Localized license description text
    link: str | None = None

    def __attrs_post_init__(self) -> None:
        if bool(self.id) and bool(self.title):
            raise ValueError("rights: either 'id' or 'title' must be set, but not both")

@attrs.define
class Contributor:
    person_or_org: PersonalPersonOrOrg | OrganizationalPersonOrOrg
    role: Role  # required for contributors
    affiliations: list[Affiliation] = attrs.field(factory=list)

    def __attrs_post_init__(self) -> None:
        if self.person_or_org.type == "organizational" and self.affiliations:
            raise ValueError("affiliations are only allowed for personal contributors")

@attrs.define
class Subject:
    id: str | None = None     # CV id
    subject: str | None = None  # free keyword

    def __attrs_post_init__(self) -> None:
        if self.id and self.subject:
            raise ValueError("subject: set exactly one of 'id' or 'subject'")

@attrs.define
class Language:
    id: ISO639_3  # ISO-639-3 code, e.g. 'eng', 'dan'

    @classmethod
    def from_string(cls, value: str) -> Language:
        if len(value) != 3:
            raise ValueError("language must be 3 characters long (ISO639-3)")
        return cls(id=value)

@attrs.define
class Date:
    date: str = attrs.field(converter=is_edtf_l0_date)
    type: DateRole
    description: str | None = None

@attrs.define
class DateRole:
    id: Literal[
        'accepted', 'available', 'collected', 'copyrighted', 'created', 'issued',
        'other', 'submitted', 'updated', 'valid', 'withdrawn'
    ]
    title: dict[ISO639_1, str] = None  # only id needed on the REST API

@attrs.define
class AlternateIdentifier:
    identifier: str
    scheme: str  # CV scheme (doi, isbn, url, ...)

@attrs.define
class RelatedIdentifier:
    identifier: str
    scheme: IdentifierSchemes
    relation_type: RelationType
    resource_type: RelatedIdentifierResourceType | None = None

@attrs.define
class RelationType:
    id: str  # CV
    title: dict[ISO639_1, str] | None = None

@attrs.define
class RelatedIdentifierResourceType:
    id: str
    title: dict[ISO639_1, str]

@attrs.define
class FundingRef:
    funder: Funder
    award: Award | None = None

@attrs.define
class Funder:
    id: str | None = None   # from CV
    name: str | None = None  # free-text

    def __attrs_post_init__(self):
        if self.id and self.name:
            raise ValueError("funder: one of 'id' or 'name' must be set")

@attrs.define
class Award:
    id: str | None = None
    title: dict[ISO639_1,str] | None = None
    number: str | None = None
    identifiers: list[AwardIdentifier] | None = None

    def __attrs_post_init__(self):
        has_id = bool(self.id)
        has_fallback = bool(self.title and self.number)
        if not (has_id or has_fallback):
            raise ValueError("award: one of 'id' or ('title' and 'number') must be set")

@attrs.define
class AwardIdentifier:
    scheme: IdentifierSchemes
    identifier: str

@attrs.define
class References:
    reference: str
    scheme: IdentifierSchemes | None = None
    identifier: str | None = None

@attrs.define
class InvenioMetadataV6:
    resource_type: ResourceType
    title: str
    publication_date: str = attrs.field(converter=is_edtf_l0_date)
    creators: list[Creator] = attrs.field(factory=list)

    additional_titles: list[AdditionTitles] = attrs.field(factory=list)
    description: str | None = None  # may use certain HTML tags
    additional_descriptions: list[AdditionalDescriptions] = attrs.field(factory=list)

    rights: list[Rights] = attrs.field(factory=list)
    copyright: str | None = None  # free-text
    contributors: list[Contributor] = attrs.field(factory=list)
    subjects: list[Subject] = attrs.field(factory=list)
    languages: list[Language] = attrs.field(factory=list)
    dates: list[Date] = attrs.field(factory=list)

    version: str | None = None  # eg. semantic versioning
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
class Access:
    record: Literal["public", "restricted"] = "public"
    files: Literal["public", "restricted"] = "public"
    embargo: AccessEmbargo | None = None

@attrs.define
class AccessEmbargo:
    active: bool
    until: str | None = attrs.field(default=None, converter=lambda v: is_iso_date(v) if v else None)
    reason: str | None = None

    def __attrs_post_init__(self) -> None:
        if self.active and not self.until:
            raise ValueError("embargo.until (YYYY-MM-DD) is required when embargo.active is true")

@attrs.define
class FilesOptions:
    enabled: bool   # should (and can) files be attached to this record or not.
    default_preview: str | None = None
    order: list[str] = attrs.field(factory=list)

@attrs.define
class ExternalPID:
    doi: DOI | None = None

@attrs.define
class DOI:
    identifier: str
    provider: str
    client: str | None = None

@attrs.define
class InvenioRecordV6Payload:
    metadata: InvenioMetadataV6
    access: Access = attrs.field(factory=Access)
    files: FilesOptions | None = None
    pids: ExternalPID | None = None
    custom_fields: dict | None = None

    def to_dict(self) -> dict[str, Any]:
        d = attrs.asdict(self, recurse=True)
        # drop empties for cleaner payloads
        return {k: v for k, v in d.items() if v not in (None, "", [], {})}
