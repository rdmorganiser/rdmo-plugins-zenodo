from dataclasses import dataclass, field
from typing import Any

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist

from .model import ZenodoMetadata

RIGHTS_URI_OPTIONS = {
    'dataset_license_types/71': 'cc-by-4.0',
    'dataset_license_types/73': 'cc-by-nc-4.0',
    'dataset_license_types/74': 'cc-by-nd-4.0',
    'dataset_license_types/75': 'cc-by-sa-4.0',
    'dataset_license_types/cc0': 'cc-zero'
}
DEFAULT_SUBJECTS = ['Data Management Plan', 'DMP']


@dataclass
class ZenodoMetadataBuilder:
    title: str
    description: str
    rights_uri_paths: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    project_users: list[Any] = field(default_factory=list)

    def get_creators(self) -> list[dict[str, dict]]:
        if not settings.ZENODO_PROVIDER.get('add_project_members'):
            return []

        creators = []
        for user in self.project_users:
            person = {
                "family_name": user.last_name,
                "given_name": user.first_name,
                "identifiers": self.get_user_identifiers(user),
                "type": "personal"
            }
            creators.append({"person_or_org": person})
        return creators

    @staticmethod
    def get_user_identifiers(user) -> list[dict[str, str]]:
        # there may also be other providers that have uids in extra_data
        try:
            orcid = user.socialaccount_set.get(provider="orcid")
        except (ObjectDoesNotExist, AttributeError):
            return []
        else:
            return [{"scheme": "orcid", "identifier": orcid.uid}]

    @staticmethod
    def get_rights_from_uri_paths(rights_options) -> list[dict[str, str]]:
        for uri_path in rights_options:
            license_id = RIGHTS_URI_OPTIONS.get(uri_path)
            if license_id:
                return [{"id": license_id}]
        return []

    @staticmethod
    def get_subjects_from_keywords(keywords) -> list[dict[str, str]]:
        subjects = [{"subject": s} for s in DEFAULT_SUBJECTS]
        for keyword in keywords:
            subjects.append({"subject": keyword})
        return subjects

    @staticmethod
    def get_languages() -> list[dict[str, str]]:
        language = settings.ZENODO_PROVIDER.get("language")
        if language:
            return [{"id": language}]
        else:
            return []

    def build_metadata(self) -> ZenodoMetadata:
        raise NotImplementedError()

    def to_post_data(self, filter_empty=False):
        return {'metadata': self.build_metadata().to_dict(filter_empty=filter_empty)}
