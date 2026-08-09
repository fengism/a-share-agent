"""Stable contracts shared by configuration encryption components."""

GLOBAL_CONFIG_SCOPE_ID = 0


class ConfigEncryptionError(RuntimeError):
    pass


__all__ = ["ConfigEncryptionError", "GLOBAL_CONFIG_SCOPE_ID"]
