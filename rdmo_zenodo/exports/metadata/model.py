from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ZenodoMetadata:
    resource_type: dict[str, str]
    title: str
    description: str
    creators: list[dict[str, dict]]
    upload_type: Optional[str] = None
    rights: Optional[list[dict[str, str]]] = None
    subjects: Optional[list[dict[str, str]]] = field(default_factory=list)
    languages: Optional[list[dict[str, str]]] = None
    publisher: Optional[str] = None
    funding: Optional[str] = None
    publication_date: Optional[str] = None

    def to_dict(self, filter_empty: Optional[bool] = False) -> dict[str, dict]:
        """Return dict suitable for POST to Zenodo."""
        metadata = {
            "resource_type": self.resource_type,
            "title": self.title,
            "description": self.description,
            "creators": self.creators,
            "upload_type": self.upload_type,
            "rights": self.rights,
            "subjects": self.subjects,
            "languages": self.languages,
            "publisher": self.publisher,
            "funding": self.funding,
            "publication_date": self.publication_date,
        }
        if filter_empty:
            return self.filter_empty(metadata)

        return metadata

    def filter_empty(self, metadata: dict[str, any]) -> dict[str, any]:
        return {k: v for k, v in metadata.items() if v not in [None, '', [], {}]}
