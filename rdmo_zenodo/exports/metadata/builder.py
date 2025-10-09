import inspect
from typing import Callable

from cattr import structure

from rdmo_zenodo.exports.metadata.context import MetadataContext
from rdmo_zenodo.exports.metadata.converter import converter
from rdmo_zenodo.exports.metadata.exceptions import ExtractionError, SchemaValidationError
from rdmo_zenodo.exports.metadata.invenio import MetadataV6, RecordV6Payload
from rdmo_zenodo.exports.metadata.mapper_invenio import INVENIO_FIELD_MAPPER
from rdmo_zenodo.exports.metadata.mapper_zenodo import ZENODO_FIELD_MAPPER
from rdmo_zenodo.exports.metadata.zenodo import ZenodoDepositionPayload, ZenodoMetadata


def call_extractors_on_field_mapping(context: MetadataContext, fields: dict[str, Callable]):
    extracted = {}
    for name, getter in fields.items():
        # if the callable expects arguments, pass context; else call it directly
        try:
            sig = inspect.signature(getter)
            if len(sig.parameters) == 0:
                value = getter()
            else:
                value = getter(context)
        except (TypeError, ValueError):
            value = getter(context)
        if value not in (None, "", [], {}):
            extracted[name] = value
    return extracted


def build_payload(context, backend: str):
    if backend == "zenodo":
        mapper, schema, payload_cls = (
            ZENODO_FIELD_MAPPER, ZenodoMetadata, ZenodoDepositionPayload
        )
    elif backend == "invenio":
        mapper, schema, payload_cls = (
            INVENIO_FIELD_MAPPER, MetadataV6, RecordV6Payload
        )
    else:
        raise ValueError(f"Unknown backend: {backend}")
    try:
        metadata_dict = call_extractors_on_field_mapping(context, mapper)
    except (TypeError, ValueError) as e:
        raise ExtractionError("Failed to extract data from RDMO project", details=str(e)) from e

    try:
        metadata_obj = structure(metadata_dict, schema)
    except (TypeError, ValueError) as e:
        raise SchemaValidationError("Schema validation failed", e) from e

    payload_obj = payload_cls(metadata=metadata_obj)
    payload = converter.unstructure(payload_obj)
    return payload
