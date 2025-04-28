from typing import Any, Dict, List

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone

from rdmo.projects.exports import Export


class ZenodoMetadataExport(Export):

    rights_uri_options = {
        'dataset_license_types/71': 'cc-by-4.0',
        'dataset_license_types/73': 'cc-by-nc-4.0',
        'dataset_license_types/74': 'cc-by-nd-4.0',
        'dataset_license_types/75': 'cc-by-sa-4.0',
        'dataset_license_types/cc0': 'cc-zero'
    }
    default_resource_type = 'publication-datamanagementplan'
    default_subjects = ['Data Management Plan', 'DMP']

    def __init__(self, project=None, snapshot=None, set_index=None):
        self.project = project
        self.snapshot = snapshot
        self.set_index = set_index
        # Retrieve settings once at initialization
        self.zenodo_settings = settings.ZENODO_PROVIDER

    def build_metadata(self) -> Dict[str, Any]:
        """Build the metadata dictionary for Zenodo export, excluding empty fields."""
        metadata = {
            'resource_type': self._get_resource_type(),
            'creators': self._get_creators() if self._should_add_project_members() else [],
            'title': self._get_title(),
            'description': self._get_description(),
            'rights': self._get_rights(),
            'languages': self._get_languages(),
            'publisher': self._get_publisher(),
            'funding': self._get_funding(),
            'upload_type': self.zenodo_settings.get('upload_type', 'dataset'),
            'publication_date': timezone.localdate().isoformat(),
            'subjects': self._get_subjects(),
        }
        # Filter out empty values
        return {
            'metadata': self._filter_empty_values(metadata)
        }

    def _filter_empty_values(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Remove empty values from the metadata dictionary."""
        return {k: v for k, v in metadata.items() if v not in [None, '', [], {}]}

    def _get_resource_type(self) -> Dict[str, str]:
        """Retrieve the resource type from settings or use default."""
        resource_type = self.zenodo_settings.get('resource_type', self.default_resource_type)
        if self.snapshot is None and self.set_index is not None:
            resource_type = 'dataset'
        return {'id': resource_type}

    def _get_creators(self) -> List[Dict[str, Any]]:
        """Build the list of creators from project members."""
        creators = []
        for user in self.project.user.all():
            creators.append({
                'person_or_org': {
                    'family_name': user.last_name,
                    'given_name': user.first_name,
                    'type': 'personal',
                    'identifiers': self._get_identifiers(user)
                }
            })
        return creators

    def _get_identifiers(self, user) -> List[Dict[str, str]]:
        """Retrieve ORCID identifier if available for the user."""
        try:
            orcid = user.socialaccount_set.get(provider='orcid')
            return [{'scheme': 'orcid', 'identifier': orcid.uid}]
        except (ObjectDoesNotExist, AttributeError):
            return []

    def _should_add_project_members(self) -> bool:
        """Determine if project members should be added as creators."""
        return self.zenodo_settings.get('add_project_members', False)

    def _get_title(self) -> str:
        """Construct the title for the metadata."""
        title_from_snapshot = f"{self.project.title} - Snapshot: {self.snapshot.title}" if self.snapshot else None
        return (
            title_from_snapshot or
            self.get_text('project/dataset/title', set_index=self.set_index) or
            self.get_text('project/dataset/id', set_index=self.set_index) or
            f'Dataset #{self.set_index + 1}'
        )

    def _get_description(self) -> str:
        """Construct the description for the metadata."""
        description = f"Data Management Plan for project {self.project.title}."
        if self.snapshot is not None:
            description += f" {self.snapshot.description}"
        if self.set_index is not None:
            dataset_title = self.get_text('project/dataset/title', set_index=self.set_index)
            if dataset_title:
                description += f" {dataset_title}"
        return description

    def _get_rights(self) -> List[Dict[str, str]]:
        """Retrieve the rights/license information from project metadata."""
        for rights in self.get_values('project/dataset/sharing/conditions', set_index=self.set_index):
            if rights.option:
                return [{'id': self.rights_uri_options.get(rights.option.uri_path)}]
        return []

    def _get_languages(self) -> List[Dict[str, str]]:
        """Retrieve the language setting from configuration."""
        language = self.zenodo_settings.get('language')
        return [{'id': language}] if language else []

    def _get_publisher(self) -> str:
        """Retrieve the publisher setting from configuration."""
        return self.zenodo_settings.get('publisher')

    def _get_funding(self) -> str:
        """Retrieve the funding information from configuration."""
        return self.zenodo_settings.get('funding')

    def _get_subjects(self) -> List[Dict[str, str]]:
        """Retrieve and construct the subjects for the metadata."""
        # Default subjects
        subjects = [{'subject': i} for i in self.default_subjects]
        # Add project-specific keywords
        keywords = self.get_values('project/research_question/keywords')
        subjects.extend({'subject': keyword.text} for keyword in keywords)
        return subjects
