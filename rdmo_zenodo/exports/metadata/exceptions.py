
class MetadataBuildError(Exception):
    """Base class for errors raised during metadata composition."""

    def __init__(self, message: str, details: str | None = None):
        self.details = details
        self.message = message
        super().__init__(message)

    def __str__(self):
        if self.details:
            return f'{self.message}: {self.details}'
        else:
            return f'{self.message}'

class SchemaValidationError(MetadataBuildError):
    """Raised when schema (attrs) validation fails."""

class ExtractionError(MetadataBuildError):
    """Raised when an extractor or mapper fails."""
