"""
Cairo Control Flow and Data Flow Analysis Module

Provides CFG building and dataflow analysis capabilities for Cairo smart contracts.
"""

from cairo_parser.analysis.statements import (
    Statement,
    AssignmentStmt,
    LetBindingStmt,
    IfStmt,
    ElseStmt,
    MatchStmt,
    ReturnStmt,
    CallStmt,
    StorageReadStmt,
    StorageWriteStmt,
    AssertStmt,
    StatementParser,
)

from cairo_parser.analysis.cfg import (
    CFGNode,
    ControlFlowGraph,
    CFGBuilder,
)

from cairo_parser.analysis.dataflow import (
    DefUseChain,
    StorageAccess,
    ExternalCall,
    DataflowAnalyzer,
)

from cairo_parser.analysis.analyzer import (
    CairoAnalyzer,
    AnalysisResult,
)

__all__ = [
    # Statements
    'Statement',
    'AssignmentStmt',
    'LetBindingStmt',
    'IfStmt',
    'ElseStmt',
    'MatchStmt',
    'ReturnStmt',
    'CallStmt',
    'StorageReadStmt',
    'StorageWriteStmt',
    'AssertStmt',
    'StatementParser',

    # CFG
    'CFGNode',
    'ControlFlowGraph',
    'CFGBuilder',

    # Dataflow
    'DefUseChain',
    'StorageAccess',
    'ExternalCall',
    'DataflowAnalyzer',

    # Main analyzer
    'CairoAnalyzer',
    'AnalysisResult',
]
