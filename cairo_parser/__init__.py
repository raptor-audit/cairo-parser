"""
Cairo Parser Package

Assembler-style Cairo parser with GOT/PLT symbol resolution.
No compiler required - uses regex pattern matching for both Cairo 0 and Cairo 1.

Includes control flow and dataflow analysis capabilities.
"""

__version__ = "0.2.0"

from cairo_parser.parser import (
    CairoParser,
    ContractInfo,
    FunctionInfo,
    StorageVarInfo,
    EventInfo,
    ImportInfo
)

from cairo_parser.analysis import (
    # Analyzer
    CairoAnalyzer,
    AnalysisResult,

    # CFG
    ControlFlowGraph,
    CFGNode,
    CFGBuilder,

    # Dataflow
    DataflowAnalyzer,
    DefUseChain,
    StorageAccess,
    ExternalCall,

    # Statements
    Statement,
    StatementParser,
    AssignmentStmt,
    LetBindingStmt,
    IfStmt,
    ElseStmt,
    MatchStmt,
    ReturnStmt,
    CallStmt,
    StorageReadStmt,
    StorageWriteStmt,
)

__all__ = [
    # Parser
    "CairoParser",
    "ContractInfo",
    "FunctionInfo",
    "StorageVarInfo",
    "EventInfo",
    "ImportInfo",

    # Analyzer
    "CairoAnalyzer",
    "AnalysisResult",

    # CFG
    "ControlFlowGraph",
    "CFGNode",
    "CFGBuilder",

    # Dataflow
    "DataflowAnalyzer",
    "DefUseChain",
    "StorageAccess",
    "ExternalCall",

    # Statements
    "Statement",
    "StatementParser",
    "AssignmentStmt",
    "LetBindingStmt",
    "IfStmt",
    "ElseStmt",
    "MatchStmt",
    "ReturnStmt",
    "CallStmt",
    "StorageReadStmt",
    "StorageWriteStmt",

    # Metadata
    "__version__"
]
