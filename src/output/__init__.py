"""Output handlers package for emitting scan results and alerts."""

from src.output.base import OutputHandler, Alert
from src.output.cli import CLIOutputHandler
from src.output.logger import LogFileOutputHandler
from src.output.composite import CompositeOutputHandler
from src.scanner.base import ScanResult  # re-export for convenience

__all__ = [
    "OutputHandler",
    "ScanResult",
    "Alert",
    "CLIOutputHandler",
    "LogFileOutputHandler",
    "CompositeOutputHandler",
]
