# rdmo_zenodo/exports/metadata/mapper_zenodo.py
from __future__ import annotations

from typing import Any, Callable

from rdmo_zenodo.exports.metadata.extractors import (
    get_creators_from_context,
    get_description_from_project,
    get_keywords_from_context,
    get_language_from_settings,
    get_license_id_from_context,
    get_publication_date_from_today,
    get_publication_type_from_settings,
    get_publisher_from_settings,
    get_title_from_context,
    get_upload_type_from_settings,
)

FieldGetter = Callable[[Any], Any]

ZENODO_FIELD_MAPPER: dict[str, FieldGetter] = {
    # core required metadata
    "upload_type": get_upload_type_from_settings,
    "publication_type": get_publication_type_from_settings,
    "publication_date": get_publication_date_from_today,
    "title": get_title_from_context,
    "description": get_description_from_project,
    "creators": get_creators_from_context,

    # optional fields and extras
    "keywords": get_keywords_from_context,
    "language": get_language_from_settings,
    "license": get_license_id_from_context,
    "publisher": get_publisher_from_settings,
}
