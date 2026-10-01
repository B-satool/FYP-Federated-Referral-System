"""Shared utilities used by the central platform and the three source services.

Only cross-service concerns live here (identity verification, the pinned FHIR
subset, and the package/event exchange contracts). Source-specific mappings
stay inside each source service's adapter module.
"""
