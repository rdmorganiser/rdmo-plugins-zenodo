from typing import Any, Callable

from rdmo_zenodo.exports.metadata.extractors import (
    get_creators_from_context,
    get_description_from_project,
    get_funding_from_settings,
    get_keywords_from_context,
    get_language_from_settings,
    get_license_id_from_context,
    get_publication_date_from_today,
    get_publication_type_from_settings,
    get_publisher_from_settings,
    get_resource_type_from_settings_and_context,
    get_subjects_from_keywords_and_context,
    get_title_from_context,
    get_upload_type_from_settings,
)

FieldGetter = Callable[[Any], Any]

ZENODO_FIELD_MAPPER: dict[str, FieldGetter] = {
    # required fields
    "upload_type": get_upload_type_from_settings,
    "publication_type": get_publication_type_from_settings,
    "resource_type": get_resource_type_from_settings_and_context,
    "title": get_title_from_context,
    "publication_date": get_publication_date_from_today,
    "creators": get_creators_from_context,
    "description": get_description_from_project,

    # optional metadata fields
    "funding": get_funding_from_settings,
    "keywords": get_keywords_from_context,
    "languages": get_language_from_settings,
    "license": get_license_id_from_context,
    "publisher": get_publisher_from_settings,
}
INVENIO_FIELD_MAPPER: dict[str, FieldGetter] = {
    # required fields
    "resource_type": get_resource_type_from_settings_and_context,
    "title": get_title_from_context,
    "publication_date": get_publication_date_from_today,
    "creators": get_creators_from_context,
    "description": get_description_from_project,

    # optional metadata fields
    "funding": get_funding_from_settings,
    "subjects": get_subjects_from_keywords_and_context,
    "languages": get_language_from_settings,
    "rights": get_license_id_from_context,
    "publisher": get_publisher_from_settings,
}
