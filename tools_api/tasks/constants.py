"""Shared literals for Invoke task modules.

Mirrors ``app.inventory.names.DEFAULT_INVENTORY_NAME`` without importing ``app``
(Invoke may load task modules before the project root is on ``sys.path``).
"""

DEFAULT_INVENTORY_NAME = "_default"
