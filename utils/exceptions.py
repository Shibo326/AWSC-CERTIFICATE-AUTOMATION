"""Custom exception classes for CertFlow."""


class CertificateGenerationError(Exception):
    """Base exception for certificate generation errors."""

    pass


class TemplateLoadError(ValueError):
    """Raised when a template cannot be loaded or is corrupted."""

    pass


class FontLoadError(ValueError):
    """Raised when a font file is invalid or cannot be loaded."""

    pass


class TextOverflowError(ValueError):
    """Raised when rendered text exceeds template bounds."""

    pass


class ConfigurationError(Exception):
    """Raised when required configuration (credentials) is missing."""

    pass


class AuthenticationError(Exception):
    """Raised when SMTP authentication fails."""

    pass
