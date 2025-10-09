from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone

from rdmo_zenodo.exports.metadata.context import MetadataContext

RIGHTS_URI_OPTIONS = {
    "dataset_license_types/71": "cc-by-4.0",
    "dataset_license_types/73": "cc-by-nc-4.0",
    "dataset_license_types/74": "cc-by-nd-4.0",
    "dataset_license_types/75": "cc-by-sa-4.0",
    "dataset_license_types/cc0": "cc-zero",
}

DEFAULT_SUBJECTS = ["Data Management Plan", "DMP"]


def get_title_from_project(context: MetadataContext) -> str:
    if context.project.title:
        return f"Data Management Plan for project {context.project.title}."
    return "Data Management Plan."

def get_title_from_dataset(context: MetadataContext) -> str:
    if context.set_index is None:
        return "Dataset"
    title = context.get_text("project/dataset/title", set_index=context.set_index)
    if title:
        return title
    dataset_id = context.get_text("project/dataset/id", set_index=context.set_index)
    if dataset_id:
        return dataset_id
    index = (int(context.set_index) + 1) if isinstance(context.set_index, int) else 1
    return f"Dataset #{index}"

def get_title_from_snapshot(context: MetadataContext) -> str:
    title = get_title_from_project(context)
    if context.snapshot and context.snapshot.title:
        title += f" - {context.snapshot.title}"
    return title

def get_title_from_context(context: MetadataContext) -> str:
    title = ""
    if context.snapshot:
        title = get_title_from_snapshot(context)
    if context.set_index is not None:
        dataset_title = get_title_from_dataset(context)
        if title:
            title += f" - {dataset_title}"
        else:
            return dataset_title
    return title

def get_description_from_project(context: MetadataContext) -> str:
    desc = get_title_from_project(context)
    if context.snapshot is not None:
        if context.snapshot.description:
            desc += "\n"
            desc += context.snapshot.description
    if context.set_index is not None:
        desc += "\n"
        desc += get_title_from_dataset(context)
    if context.view and context.export_format:
        desc += "\n"
        desc += f"Exported to {context.export_format} with the {context.view.title} view."

    return desc

# === from settings === #

def get_access_right_from_settings(_,) -> str:
    return settings.ZENODO_PROVIDER.get("access_right", "open")

def get_upload_type_from_settings() -> str:
    return settings.ZENODO_PROVIDER.get("upload_type", "dataset")

def get_publication_type_from_settings() -> str | None:
    if settings.ZENODO_PROVIDER.get("upload_type") == "publication":
        return settings.ZENODO_PROVIDER.get("publication_type", "datamanagementplan")
    return None

def get_resource_type_from_settings_and_context(context) -> dict[str, str]:
    default = "publication-datamanagementplan"
    if context.set_index is not None:
        default = "dataset"
    return settings.ZENODO_PROVIDER.get("resource_type", default)

def get_language_from_settings() -> str | None:
    if language := settings.ZENODO_PROVIDER.get("language"):
        return language
    return None

def get_publisher_from_settings() -> str | None:
    return settings.ZENODO_PROVIDER.get("publisher")

def get_funding_from_settings() -> str | None:
    return settings.ZENODO_PROVIDER.get("funding")

def get_publication_date_from_today() -> str:
    return timezone.localdate().isoformat()

# === users === #

def get_orcid_from_user(user: Any) -> str | None:
    try:
        return user.socialaccount_set.get(provider="orcid")
    except (ObjectDoesNotExist, AttributeError):
        return None

def get_invenio_creator_from_user(user):
    orcid = get_orcid_from_user(user)
    identifiers = [{"scheme": "orcid", "identifier": orcid.uid}] if orcid else []
    return {
        "person_or_org": {
            "family_name": user.last_name,
            "given_name": user.first_name,
            "identifiers": identifiers,
            "type": "personal",
        }
    }

def get_zenodo_creator_from_user(user):
    orcid = get_orcid_from_user(user)
    return {
        "name": f"{user.last_name}, {user.first_name}".strip(),
        "orcid": orcid.uid if orcid else None,
        "affiliation": None,
    }

def get_creators_from_context(context: MetadataContext) -> list[dict[str, Any]]:
    creators = []
    if context.zenodo_backend_type == "zenodo":
        get_creator = get_invenio_creator_from_user
    elif context.zenodo_backend_type == "invenio":
        get_creator = get_invenio_creator_from_user
    else:
        raise ValueError(f"Unsupported backend type: {context.zenodo_backend_type}")
    for user in context.project_members:
        creators.append(get_creator(user))
    return creators

# === licenses, subjects, keywords ===

def get_license_id_from_context(context: MetadataContext) -> list[dict[str, str]]:
    set_index = context.set_index if context.set_index is not None else 0
    values = context.get_values("project/dataset/sharing/conditions", set_index=set_index)
    for v in values:
        if v.option and (license_id := RIGHTS_URI_OPTIONS.get(v.option.uri_path)):
            return [{"id": license_id}]
        if v.option.additional_input == "text" and v.text:
            return [{"id": v.text}]
    return []

def get_keywords_from_context(context: MetadataContext) -> list[str]:
    keywords = [v.text for v in context.get_values("project/research_question/keywords") if v.text]
    return DEFAULT_SUBJECTS + keywords

def get_subjects_from_keywords_and_context(context: MetadataContext) -> list[dict[str, str]]:
    return [{"subject": s} for s in get_keywords_from_context(context)]
