from dataclasses import dataclass

from django.conf import settings

from .base import ZenodoMetadataBuilder
from .model import ZenodoMetadata


@dataclass
class ZenodoMetadataDatasetBuilder(ZenodoMetadataBuilder):

    def build_metadata(self) -> ZenodoMetadata:
        return ZenodoMetadata(
            resource_type={"id": settings.ZENODO_PROVIDER.get("resource_type", "dataset")},
            title=self.title,
            description=self.description,
            rights=self.get_rights_from_uri_paths(self.rights_uri_paths),
            creators=self.get_creators(),
            subjects=self.get_subjects_from_keywords(self.keywords),
            languages=self.get_languages(),
            upload_type=settings.ZENODO_PROVIDER.get("upload_type", "dataset"),
            publisher=settings.ZENODO_PROVIDER.get("publisher"),
            funding=settings.ZENODO_PROVIDER.get("funding")
        )
