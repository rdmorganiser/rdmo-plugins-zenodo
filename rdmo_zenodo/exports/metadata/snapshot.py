from dataclasses import dataclass
from typing import Optional

from django.conf import settings
from django.utils import timezone

from .base import ZenodoMetadataBuilder
from .model import ZenodoMetadata


@dataclass
class ZenodoMetadataSnapshotBuilder(ZenodoMetadataBuilder):

    publication_date: Optional[str] = None

    def build_metadata(self) -> ZenodoMetadata:
        return ZenodoMetadata(
            resource_type={"id": "publication-datamanagementplan"},
            title=self.title,
            description=self.description,
            rights=self.get_rights_from_uri_paths(self.rights_uri_paths),
            creators=self.get_creators(),
            subjects=self.get_subjects_from_keywords(self.keywords),
            languages=self.get_languages(),
            upload_type=settings.ZENODO_PROVIDER.get("upload_type", "publication-datamanagementplan"),
            publisher=settings.ZENODO_PROVIDER.get("publisher"),
            funding=settings.ZENODO_PROVIDER.get("funding"),
            publication_date=self.publication_date or timezone.localdate().isoformat(),
        )
