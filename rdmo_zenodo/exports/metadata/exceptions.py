
class MetadataBuildError(Exception):
    """Base class for errors raised during metadata composition."""

    def __init__(self, message: str, field: str | None = None, details: str | None = None):
        self.field = field
        self.details = details
        super().__init__(message)

    def __str__(self):
        if self.details:
            return f'{self.field}: {self.details}'
        else:
            return f'{self.field}'

class SchemaValidationError(MetadataBuildError):
    """Raised when schema (attrs) validation fails."""

class ExtractionError(MetadataBuildError):
    """Raised when an extractor or mapper fails."""
