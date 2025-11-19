"""
Dataflow Analysis for Cairo Functions

Performs dataflow analysis including:
- Variable def-use chain analysis
- Storage access tracking
- External call identification
"""

from typing import List, Dict, Set, Optional, Any
from dataclasses import dataclass, field

from cairo_parser.analysis.cfg import ControlFlowGraph, CFGNode
from cairo_parser.analysis.statements import (
    Statement,
    AssignmentStmt,
    LetBindingStmt,
    CallStmt,
    StorageReadStmt,
    StorageWriteStmt,
    StatementParser,
)


@dataclass
class DefUseChain:
    """
    Definition-Use chain for a variable.

    Tracks where a variable is defined and where it's used.
    """
    variable: str
    definitions: List[int] = field(default_factory=list)  # Node IDs where variable is defined
    uses: List[int] = field(default_factory=list)  # Node IDs where variable is used

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'variable': self.variable,
            'definitions': self.definitions,
            'uses': self.uses,
        }


@dataclass
class StorageAccess:
    """
    Storage variable access (read or write).

    Tracks access to contract storage variables.
    """
    storage_var: str
    access_type: str  # 'read' or 'write'
    node_id: int
    line: int
    value: Optional[str] = None  # For writes, the value being written

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            'storage_var': self.storage_var,
            'access_type': self.access_type,
            'node_id': self.node_id,
            'line': self.line,
        }
        if self.value:
            result['value'] = self.value
        return result


@dataclass
class ExternalCall:
    """
    External function call.

    Tracks calls to external contracts or functions.
    """
    function_name: str
    arguments: List[str]
    node_id: int
    line: int
    is_external: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'function_name': self.function_name,
            'arguments': self.arguments,
            'node_id': self.node_id,
            'line': self.line,
            'is_external': self.is_external,
        }


class DataflowAnalyzer:
    """
    Analyzer for dataflow properties of Cairo functions.

    Performs analysis over a control flow graph to extract dataflow information.
    """

    def __init__(self, cfg: ControlFlowGraph):
        """
        Initialize dataflow analyzer.

        Args:
            cfg: Control flow graph to analyze
        """
        self.cfg = cfg
        self.statement_parser = StatementParser()

    def analyze_all(self) -> Dict[str, Any]:
        """
        Perform all dataflow analyses.

        Returns:
            Dictionary containing all analysis results
        """
        return {
            'def_use_chains': self.analyze_def_use_chains(),
            'storage_accesses': self.analyze_storage_access(),
            'external_calls': self.analyze_external_calls(),
        }

    def analyze_def_use_chains(self) -> List[Dict[str, Any]]:
        """
        Analyze variable definitions and uses.

        Returns:
            List of DefUseChain objects serialized as dicts
        """
        # Track definitions and uses per variable
        var_defs: Dict[str, List[int]] = {}
        var_uses: Dict[str, List[int]] = {}

        for node in self.cfg.nodes:
            if node.statement:
                # Extract defined variables
                defined_vars = self.statement_parser.extract_variables_defined(node.statement)
                for var in defined_vars:
                    if var not in var_defs:
                        var_defs[var] = []
                    var_defs[var].append(node.id)

                # Extract used variables
                used_vars = self.statement_parser.extract_variables_used(node.statement)
                for var in used_vars:
                    if var not in var_uses:
                        var_uses[var] = []
                    var_uses[var].append(node.id)

        # Build def-use chains
        all_vars = set(var_defs.keys()) | set(var_uses.keys())
        chains = []

        for var in sorted(all_vars):
            chain = DefUseChain(
                variable=var,
                definitions=var_defs.get(var, []),
                uses=var_uses.get(var, [])
            )
            chains.append(chain.to_dict())

        return chains

    def analyze_storage_access(self) -> List[Dict[str, Any]]:
        """
        Analyze storage variable accesses.

        Returns:
            List of StorageAccess objects serialized as dicts
        """
        accesses = []

        for node in self.cfg.nodes:
            if not node.statement:
                continue

            stmt = node.statement

            if isinstance(stmt, StorageReadStmt):
                access = StorageAccess(
                    storage_var=stmt.storage_var,
                    access_type='read',
                    node_id=node.id,
                    line=stmt.line
                )
                accesses.append(access.to_dict())

            elif isinstance(stmt, StorageWriteStmt):
                access = StorageAccess(
                    storage_var=stmt.storage_var,
                    access_type='write',
                    node_id=node.id,
                    line=stmt.line,
                    value=stmt.value
                )
                accesses.append(access.to_dict())

        return accesses

    def analyze_external_calls(self) -> List[Dict[str, Any]]:
        """
        Identify external function calls.

        Returns:
            List of ExternalCall objects serialized as dicts
        """
        calls = []

        for node in self.cfg.nodes:
            if not node.statement:
                continue

            stmt = node.statement

            if isinstance(stmt, CallStmt):
                call = ExternalCall(
                    function_name=stmt.function_name,
                    arguments=stmt.arguments,
                    node_id=node.id,
                    line=stmt.line,
                    is_external=stmt.is_external
                )
                calls.append(call.to_dict())

        return calls

    def compute_reaching_definitions(self) -> Dict[int, Set[tuple[str, int]]]:
        """
        Compute reaching definitions for each node.

        A definition d reaches a node n if there exists a path from d to n
        along which d is not killed (overwritten).

        Returns:
            Dictionary mapping node IDs to sets of (variable, def_node_id) pairs
        """
        # Initialize reaching definitions
        reaching_in: Dict[int, Set[tuple[str, int]]] = {}
        reaching_out: Dict[int, Set[tuple[str, int]]] = {}

        for node in self.cfg.nodes:
            reaching_in[node.id] = set()
            reaching_out[node.id] = set()

        # Iterative dataflow analysis (forward)
        changed = True
        iterations = 0
        max_iterations = 100

        while changed and iterations < max_iterations:
            changed = False
            iterations += 1

            for node in self.cfg.nodes:
                # Reaching_in[n] = Union of Reaching_out[p] for all predecessors p
                new_in = set()
                for pred_id in node.predecessors:
                    new_in = new_in.union(reaching_out.get(pred_id, set()))

                if new_in != reaching_in[node.id]:
                    reaching_in[node.id] = new_in
                    changed = True

                # Reaching_out[n] = Gen[n] ∪ (Reaching_in[n] - Kill[n])
                gen_set = self._gen_definitions(node)
                kill_set = self._kill_definitions(node, reaching_in[node.id])

                new_out = gen_set.union(reaching_in[node.id] - kill_set)

                if new_out != reaching_out[node.id]:
                    reaching_out[node.id] = new_out
                    changed = True

        return reaching_in

    def _gen_definitions(self, node: CFGNode) -> Set[tuple[str, int]]:
        """
        Compute GEN set for a node (new definitions generated).

        Args:
            node: CFG node

        Returns:
            Set of (variable, node_id) pairs
        """
        if not node.statement:
            return set()

        defined_vars = self.statement_parser.extract_variables_defined(node.statement)
        return {(var, node.id) for var in defined_vars}

    def _kill_definitions(
        self,
        node: CFGNode,
        reaching_defs: Set[tuple[str, int]]
    ) -> Set[tuple[str, int]]:
        """
        Compute KILL set for a node (definitions killed/overwritten).

        Args:
            node: CFG node
            reaching_defs: Reaching definitions at this node

        Returns:
            Set of (variable, node_id) pairs that are killed
        """
        if not node.statement:
            return set()

        # Variables defined at this node kill previous definitions
        defined_vars = self.statement_parser.extract_variables_defined(node.statement)

        killed = set()
        for var, def_node_id in reaching_defs:
            if var in defined_vars and def_node_id != node.id:
                killed.add((var, def_node_id))

        return killed

    def find_uninitialized_variables(self) -> List[Dict[str, Any]]:
        """
        Find variables that may be used before being defined.

        Returns:
            List of warnings about potentially uninitialized variables
        """
        warnings = []
        reaching_defs = self.compute_reaching_definitions()

        for node in self.cfg.nodes:
            if not node.statement:
                continue

            used_vars = self.statement_parser.extract_variables_used(node.statement)

            for var in used_vars:
                # Check if this variable has any reaching definition
                has_definition = any(
                    def_var == var
                    for def_var, _ in reaching_defs.get(node.id, set())
                )

                if not has_definition:
                    warnings.append({
                        'variable': var,
                        'node_id': node.id,
                        'line': node.statement.line,
                        'message': f"Variable '{var}' may be used before initialization"
                    })

        return warnings

    def find_unused_definitions(self) -> List[Dict[str, Any]]:
        """
        Find variable definitions that are never used.

        Returns:
            List of warnings about unused definitions
        """
        warnings = []
        def_use_chains = self.analyze_def_use_chains()

        for chain in def_use_chains:
            if chain['definitions'] and not chain['uses']:
                warnings.append({
                    'variable': chain['variable'],
                    'definition_nodes': chain['definitions'],
                    'message': f"Variable '{chain['variable']}' is defined but never used"
                })

        return warnings
