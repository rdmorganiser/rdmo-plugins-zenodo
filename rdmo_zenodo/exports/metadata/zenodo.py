# References, https://zenodraft.github.io/metadata-schema-zenodo/latest/schema.json
# https://developers.zenodo.org/#depositions
from __future__ import annotations

from typing import Any, Literal

import attrs

from rdmo_zenodo.exports.metadata.utils import is_iso_date

UploadType = Literal[
    "dataset", "image", "publication", "poster", "presentation",
    "software", "lesson", "physicalobject", "other"
]

PublicationType = Literal[
    "annotationcollection", "book", "section", "conferencepaper", "datamanagementplan",
    "article", "patent", "preprint", "deliverable", "milestone",
    "proposal", "report", "softwaredocumentation", "taxonomictreatment",
    "technicalnote", "thesis", "workingpaper", "other"
]

ImageType = Literal["figure", "plot", "drawing", "diagram", "photo", "other"]

AccessRight = Literal["open", "embargoed", "restricted", "closed"]

ContributorType = Literal[
    "ContactPerson", "DataCollector", "DataCurator", "DataManager",
    "Distributor", "Editor", "HostingInstitution", "Producer",
    "ProjectLeader", "ProjectManager", "ProjectMember", "RegistrationAgency",
    "RegistrationAuthority", "RelatedPerson", "ResearchGroup", "RightsHolder",
    "Sponsor", "Supervisor", "WorkPackageLeader", "Other", "Annotator"
]


@attrs.define
class Creator:
    name: str  # in the format Family name, Given names
    affiliation: str | None = None
    orcid: str | None = None
    gnd : str | None = None

    def __attrs_post_init__(self) -> None:
        if not self.name:
            raise ValueError("creator.name is required")

@attrs.define
class Contributor:
    name: str
    type: ContributorType
    affiliation: str | None = None
    orcid: str | None = None
    gnd: str | None = None

@attrs.define
class Identifier:
    identifier: str
    relation: str | None = None   # e.g. "isSupplementTo"
    scheme: str | None = None     # "doi", "url", etc.
    resource_type: str | None = None

@attrs.define
class Grant:
    id: str                        # e.g. "10.13039/501100000780::101122483"

@attrs.define
class Community:
    identifier: str                # e.g. "zenodo-community-id"

@attrs.define
class RelatedIdentifier:
    identifier: str
    relation: str
    scheme: str | None = None
    resource_type: str | None = None


@attrs.define
class ZenodoMetadata:
    upload_type: UploadType
    title: str
    description: str
    publication_date: str = attrs.field(converter=is_iso_date)
    publication_type: str | None = None
    creators: list[Creator] = attrs.field(factory=list)
    contributors: list[Contributor] = attrs.field(factory=list)
    keywords: list[str] = attrs.field(factory=list)
    language: str | None = None            # ISO 639-1 code
    related_identifiers: list[RelatedIdentifier] = attrs.field(factory=list)
    alternate_identifiers: list[Identifier] = attrs.field(factory=list)
    grants: list[Grant] = attrs.field(factory=list)
    references: list[str] = attrs.field(factory=list)
    notes: str | None = None
    communities: list[Community] = attrs.field(factory=list)
    access_right: AccessRight = "open"
    license: str | None = None             # any SPDX ID or custom name
    embargo_date: str | None = attrs.field(default=None, converter=lambda v: is_iso_date(v) if v else None)
    access_conditions: str | None = None
    publisher: str | None = None
    version: str | None = None

    def __attrs_post_init__(self) -> None:
        # upload type dependent constraints
        if self.upload_type == "publication" and not self.publication_type:
            raise ValueError("publication_type required when upload_type='publication'")

        # access_right constraints
        if self.access_right in {"open", "embargoed"} and not self.license:
            raise ValueError("license required when access_right is open or embargoed")
        if self.access_right == "embargoed" and not self.embargo_date:
            raise ValueError("embargo_date required when access_right='embargoed'")
        if self.access_right == "restricted" and not self.access_conditions:
            raise ValueError("access_conditions required when access_right='restricted'")

        # required minimal fields
        if not self.creators:
            raise ValueError("At least one creator required")
        if not self.title or not self.description:
            raise ValueError("Both title and description are required")

@attrs.define
class ZenodoDepositionPayload:
    metadata: ZenodoMetadata

    def to_dict(self) -> dict[str, Any]:
        d = attrs.asdict(self, recurse=True)
        # remove empties
        return {k: v for k, v in d.items() if v not in (None, "", [], {})}
