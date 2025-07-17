"""
Configuration management system for the Insight Engine application.

This package provides comprehensive configuration management with:
- Environment-specific settings
- Configuration validation
- Startup health checks
- Secret management integration
"""

from .validation import (
    ConfigurationValidator,
    validate_configuration_at_startup,
    get_configuration_summary,
    check_required_environment_variables,
    validate_external_service_connectivity,
)

# Note: settings is imported from the parent config module when needed
# to avoid circular imports

__all__ = [
    "ConfigurationValidator",
    "validate_configuration_at_startup",
    "get_configuration_summary",
    "check_required_environment_variables",
    "validate_external_service_connectivity",
]