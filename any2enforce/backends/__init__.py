"""Backend package. v0.1 ships the EnforceScript emitter only."""

from .enforce import EnforceBackend

BACKENDS = {"enforce": EnforceBackend}
