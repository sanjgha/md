"""Scanner registry for discovering and managing scanner instances."""

from typing import Dict, Optional
from src.scanner.base import Scanner


class ScannerRegistry:
    """Registry for discovering and loading scanners."""

    def __init__(self):
        """Initialize empty registry."""
        self._scanners: Dict[str, Scanner] = {}

    def register(self, name: str, scanner: Scanner) -> None:
        """Register a scanner under a name."""
        self._scanners[name] = scanner

    def get(self, name: str) -> Optional[Scanner]:
        """Retrieve a scanner by name."""
        return self._scanners.get(name)

    def list(self) -> Dict[str, Scanner]:
        """Return all registered scanners."""
        return dict(self._scanners)
