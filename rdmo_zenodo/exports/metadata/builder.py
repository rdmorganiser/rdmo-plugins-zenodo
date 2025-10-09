import inspect
from typing import Any, Callable

from attr import AttrsInstance, fields
from cattrs import ClassValidationError, transform_error

from rdmo_zenodo.exports.metadata.context import MetadataContext
from rdmo_zenodo.exports.metadata.converter import converter
from rdmo_zenodo.exports.metadata.exceptions import SchemaValidationError
from rdmo_zenodo.exports.metadata.invenio import MetadataV6, RecordV6Payload
from rdmo_zenodo.exports.metadata.mapper_invenio import INVENIO_FIELD_MAPPER
from rdmo_zenodo.exports.metadata.mapper_zenodo import ZENODO_FIELD_MAPPER
from rdmo_zenodo.exports.metadata.zenodo import ZenodoDepositionPayload, ZenodoMetadata

BACKENDS = {
    "zenodo": (ZENODO_FIELD_MAPPER, ZenodoMetadata, ZenodoDepositionPayload),
    "invenio": (INVENIO_FIELD_MAPPER, MetadataV6, RecordV6Payload),
}

def extract_metadata(context: MetadataContext, fields: dict[str, Callable]):
    # 1: extract metadata from rdmo project values
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
            "Schema validation failed", details=",".join(transform_error(e))
        ) from e
    except (TypeError, ValueError) as e:
        raise SchemaValidationError("Invalid metadata structure", details=str(e)) from e


def build_payload_object(metadata_obj: Any, payload_cls: type) -> Any:
    # 3: build payload dataclass instance
    return payload_cls(metadata=metadata_obj)


def serialize_payload(payload_obj: Any) -> dict[str, Any]:
    # 4: convert payload object to JSON-serializable dict
    return converter.unstructure(payload_obj)


def build_payload(context: MetadataContext, backend: str) -> dict[str, Any]:
    # main entrypoint: run the extraction → validation → serialization pipeline
    try:
        mapper, schema, payload_cls = BACKENDS[backend]
    except KeyError:
        raise ValueError(f"Unknown backend: {backend!r}") from None

    metadata_dict = extract_metadata(context, mapper)
    metadata_obj = validate_schema(metadata_dict, schema)
    payload_obj = build_payload_object(metadata_obj, payload_cls)
    return serialize_payload(payload_obj)
