"""
Cairo Parser Package

Assembler-style Cairo parser with GOT/PLT symbol resolution.
No compiler required - uses regex pattern matching for both Cairo 0 and Cairo 1.
"""

__version__ = "0.1.1"

from cairo_parser.parser import (
    CairoParser,
    ContractInfo,
    FunctionInfo,
    StorageVarInfo,
    EventInfo,
    ImportInfo
)

__all__ = [
    "CairoParser",
    "ContractInfo",
    "FunctionInfo",
    "StorageVarInfo",
    "EventInfo",
    "ImportInfo",
    "__version__"
]
