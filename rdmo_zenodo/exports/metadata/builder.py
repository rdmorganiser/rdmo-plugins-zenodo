import inspect
from typing import Any, Callable

from attr import AttrsInstance, fields
from cattrs import ClassValidationError, transform_error

from rdmo_zenodo.exports.metadata.context import MetadataContext
from rdmo_zenodo.exports.metadata.converter import converter
from rdmo_zenodo.exports.metadata.exceptions import SchemaValidationError
from rdmo_zenodo.exports.metadata.invenio import InvenioMetadataV6, InvenioRecordV6Payload
from rdmo_zenodo.exports.metadata.mappers import INVENIO_FIELD_MAPPER, ZENODO_FIELD_MAPPER
from rdmo_zenodo.exports.metadata.zenodo import ZenodoDepositionPayload, ZenodoMetadata

METADATA_METHODS = {
    "zenodo": (ZENODO_FIELD_MAPPER, ZenodoMetadata, ZenodoDepositionPayload),
    "invenio": (INVENIO_FIELD_MAPPER, InvenioMetadataV6, InvenioRecordV6Payload),
}

def extract_metadata(context: MetadataContext, fields: dict[str, Callable]):
    # 1: extract metadata from rdmo project values
    extracted = {}
    for name, getter in fields.items():
        sig = inspect.signature(getter)
        if len(sig.parameters) == 0:
            value = getter()
        elif len(sig.parameters) == 1:
            value = getter(context)
        else:
            raise ValueError(f"Unsupported getter signature {sig}")
        extracted[name] = value
    return extracted


def validate_schema(metadata_dict: dict[str, Any], schema: AttrsInstance) -> Any:
    # 2: validate metadata dict against attrs schema

    # 2.1 check for unknown  keys
    allowed = {f.name for f in fields(schema)}
    unknown = set(metadata_dict) - allowed
    if unknown:
        raise SchemaValidationError(
            f"Unexpected fields in metadata for {schema.__name__}",
            details=", ".join(sorted(unknown))
        )
    # 2.2 structure from dict and return validated
    try:
        return converter.structure(metadata_dict, schema)
    except ClassValidationError as e:
        raise SchemaValidationError(
            f"Schema validation failed for {schema.__name__}", details=",".join(transform_error(e))
        ) from e
    except (TypeError, ValueError) as e:
        raise SchemaValidationError("Invalid metadata structure", details=str(e)) from e


def serialize_payload(payload_obj: Any) -> dict[str, Any]:
    # convert payload object to JSON-serializable dict
    return converter.unstructure(payload_obj)
