"""
Control Flow Graph (CFG) Builder for Cairo Functions

Constructs control flow graphs from parsed statements for analysis.
"""

from typing import List, Dict, Set, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

from cairo_parser.analysis.statements import (
    Statement,
    StatementType,
    IfStmt,
    ElseStmt,
    MatchStmt,
    ReturnStmt,
)


class CFGNodeType(Enum):
    """Types of CFG nodes."""
    ENTRY = "entry"
    EXIT = "exit"
    STATEMENT = "statement"
    BRANCH = "branch"
    MERGE = "merge"
    LOOP_HEADER = "loop_header"


@dataclass
class CFGNode:
    """
    A node in the Control Flow Graph.

    Represents a program point in the control flow with edges to
    successor and predecessor nodes.
    """
    id: int
    node_type: CFGNodeType
    statement: Optional[Statement] = None
    successors: List[int] = field(default_factory=list)
    predecessors: List[int] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert CFG node to dictionary for serialization."""
        result = {
            'id': self.id,
            'type': self.node_type.value,
            'successors': self.successors,
            'predecessors': self.predecessors,
        }

        if self.statement:
            result['statement'] = self.statement.to_dict()

        return result


@dataclass
class ControlFlowGraph:
    """
    Control Flow Graph for a Cairo function.

    Contains nodes representing program points and edges representing
    control flow between them.
    """
    function_name: str
    nodes: List[CFGNode] = field(default_factory=list)
    entry_node_id: Optional[int] = None
    exit_node_ids: List[int] = field(default_factory=list)

    def get_node(self, node_id: int) -> Optional[CFGNode]:
        """Get node by ID."""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def add_edge(self, from_id: int, to_id: int):
        """Add an edge between two nodes."""
        from_node = self.get_node(from_id)
        to_node = self.get_node(to_id)

        if from_node and to_node:
            if to_id not in from_node.successors:
                from_node.successors.append(to_id)
            if from_id not in to_node.predecessors:
                to_node.predecessors.append(from_id)

    def to_dict(self) -> Dict[str, Any]:
        """Convert CFG to dictionary for serialization."""
        return {
            'function_name': self.function_name,
            'entry_node': self.entry_node_id,
            'exit_nodes': self.exit_node_ids,
            'nodes': [node.to_dict() for node in self.nodes],
        }


class CFGBuilder:
    """
    Builder for Control Flow Graphs.

    Converts a list of statements into a CFG with proper control flow edges.
    """

    def __init__(self):
        """Initialize CFG builder."""
        self.node_counter = 0
        self.cfg: Optional[ControlFlowGraph] = None

    def build(self, function_name: str, statements: List[Statement]) -> ControlFlowGraph:
        """
        Build a CFG from a list of statements.

        Args:
            function_name: Name of the function being analyzed
            statements: List of parsed statements

        Returns:
            ControlFlowGraph object
        """
        self.cfg = ControlFlowGraph(function_name=function_name)
        self.node_counter = 0

        # Create entry node
        entry_node = self._create_node(CFGNodeType.ENTRY)
        self.cfg.entry_node_id = entry_node.id

        # Create exit node
        exit_node = self._create_node(CFGNodeType.EXIT)
        self.cfg.exit_node_ids.append(exit_node.id)

        if not statements:
            # Empty function: entry -> exit
            self.cfg.add_edge(entry_node.id, exit_node.id)
            return self.cfg

        # Build CFG from statements
        current_node_id = entry_node.id
        current_node_id = self._build_sequential(statements, current_node_id, exit_node.id)

        # If last statement doesn't explicitly return, connect to exit
        if current_node_id is not None:
            self.cfg.add_edge(current_node_id, exit_node.id)

        return self.cfg

    def _create_node(self, node_type: CFGNodeType, statement: Optional[Statement] = None) -> CFGNode:
        """Create a new CFG node."""
        node = CFGNode(
            id=self.node_counter,
            node_type=node_type,
            statement=statement
        )
        self.node_counter += 1
        self.cfg.nodes.append(node)
        return node

    def _build_sequential(
        self,
        statements: List[Statement],
        current_id: int,
        exit_id: int,
        start_idx: int = 0
    ) -> Optional[int]:
        """
        Build CFG for sequential statements.

        Args:
            statements: List of statements to process
            current_id: Current node ID to connect from
            exit_id: Exit node ID for returns
            start_idx: Starting index in statements list

        Returns:
            ID of the last node in the sequence, or None if terminated
        """
        i = start_idx
        while i < len(statements):
            stmt = statements[i]

            # Handle control flow statements
            if isinstance(stmt, IfStmt):
                current_id, i = self._build_if(statements, i, current_id, exit_id)
            elif isinstance(stmt, MatchStmt):
                current_id, i = self._build_match(statements, i, current_id, exit_id)
            elif isinstance(stmt, ReturnStmt):
                # Create return node
                return_node = self._create_node(CFGNodeType.STATEMENT, stmt)
                self.cfg.add_edge(current_id, return_node.id)
                self.cfg.add_edge(return_node.id, exit_id)
                # Return statement terminates this path
                return None
            else:
                # Regular statement
                stmt_node = self._create_node(CFGNodeType.STATEMENT, stmt)
                self.cfg.add_edge(current_id, stmt_node.id)
                current_id = stmt_node.id

            i += 1

        return current_id

    def _build_if(
        self,
        statements: List[Statement],
        if_idx: int,
        current_id: int,
        exit_id: int
    ) -> tuple[Optional[int], int]:
        """
        Build CFG for if-else statement.

        Args:
            statements: Full statement list
            if_idx: Index of if statement
            current_id: Current node ID
            exit_id: Exit node ID

        Returns:
            (merge_node_id, next_statement_index)
        """
        if_stmt = statements[if_idx]
        if_depth = if_stmt.block_depth

        # Create branch node for the condition
        branch_node = self._create_node(CFGNodeType.BRANCH, if_stmt)
        self.cfg.add_edge(current_id, branch_node.id)

        # Extract the then-block and else-block
        then_block, else_block, next_idx = self._extract_if_blocks(statements, if_idx)

        # Create merge node (where both branches converge)
        merge_node = self._create_node(CFGNodeType.MERGE)

        # Build then-branch
        if then_block:
            then_last = self._build_sequential(then_block, branch_node.id, exit_id)
            if then_last is not None:
                self.cfg.add_edge(then_last, merge_node.id)
        else:
            # Empty then-block: branch directly to merge
            self.cfg.add_edge(branch_node.id, merge_node.id)

        # Build else-branch (if exists)
        if else_block:
            else_last = self._build_sequential(else_block, branch_node.id, exit_id)
            if else_last is not None:
                self.cfg.add_edge(else_last, merge_node.id)
        else:
            # No else: branch directly to merge
            self.cfg.add_edge(branch_node.id, merge_node.id)

        # Return the index just before the next statement (it gets incremented in the loop)
        return merge_node.id, next_idx - 1

    def _build_match(
        self,
        statements: List[Statement],
        match_idx: int,
        current_id: int,
        exit_id: int
    ) -> tuple[Optional[int], int]:
        """
        Build CFG for match expression.

        Args:
            statements: Full statement list
            match_idx: Index of match statement
            current_id: Current node ID
            exit_id: Exit node ID

        Returns:
            (merge_node_id, next_statement_index)
        """
        match_stmt = statements[match_idx]
        match_depth = match_stmt.block_depth

        # Create branch node for match
        branch_node = self._create_node(CFGNodeType.BRANCH, match_stmt)
        self.cfg.add_edge(current_id, branch_node.id)

        # Create merge node
        merge_node = self._create_node(CFGNodeType.MERGE)

        # Find the end of the match block (when we return to the match's depth level)
        next_idx = match_idx + 1
        for i in range(match_idx + 1, len(statements)):
            if statements[i].block_depth <= match_depth:
                next_idx = i
                break
        else:
            next_idx = len(statements)

        # Extract match body statements
        match_body = statements[match_idx + 1:next_idx]

        if match_body:
            # Simplified: treat match body as sequential for now
            # A full implementation would parse individual arms
            body_last = self._build_sequential(match_body, branch_node.id, exit_id)
            if body_last is not None:
                self.cfg.add_edge(body_last, merge_node.id)
        else:
            self.cfg.add_edge(branch_node.id, merge_node.id)

        return merge_node.id, next_idx - 1

    def _extract_if_blocks(
        self,
        statements: List[Statement],
        if_idx: int
    ) -> tuple[List[Statement], Optional[List[Statement]], int]:
        """
        Extract then-block and else-block from if statement using block depths.

        Returns:
            (then_statements, else_statements, next_index)
        """
        if_stmt = statements[if_idx]
        if_depth = if_stmt.block_depth

        then_block = []
        else_block = None
        else_idx = None

        # Look for statements inside the if block
        i = if_idx + 1
        while i < len(statements):
            stmt = statements[i]

            # Check if we've found an else at the same depth as the if
            if isinstance(stmt, ElseStmt) and stmt.block_depth == if_depth:
                else_idx = i
                break

            # Check if we've exited the if block (back to if's depth or less)
            if stmt.block_depth <= if_depth:
                break

            # This statement is inside the then-block
            then_block.append(stmt)
            i += 1

        # If we found an else, extract the else block
        if else_idx is not None:
            else_block = []
            i = else_idx + 1
            while i < len(statements):
                stmt = statements[i]

                # Check if we've exited the else block
                if stmt.block_depth <= if_depth:
                    break

                else_block.append(stmt)
                i += 1

        return then_block, else_block, i

    def compute_dominators(self) -> Dict[int, Set[int]]:
        """
        Compute dominator sets for each node.

        A node d dominates node n if every path from entry to n goes through d.

        Returns:
            Dictionary mapping node IDs to sets of dominator node IDs
        """
        if not self.cfg or self.cfg.entry_node_id is None:
            return {}

        # Initialize: entry dominates only itself, all others dominated by all nodes
        all_nodes = {node.id for node in self.cfg.nodes}
        dominators = {
            self.cfg.entry_node_id: {self.cfg.entry_node_id}
        }

        for node in self.cfg.nodes:
            if node.id != self.cfg.entry_node_id:
                dominators[node.id] = all_nodes.copy()

        # Iteratively compute dominators
        changed = True
        while changed:
            changed = False
            for node in self.cfg.nodes:
                if node.id == self.cfg.entry_node_id:
                    continue

                # New dominators = {node} ∪ (intersection of predecessors' dominators)
                new_dom = {node.id}

                if node.predecessors:
                    pred_doms = [dominators[pred_id] for pred_id in node.predecessors]
                    if pred_doms:
                        new_dom = new_dom.union(set.intersection(*pred_doms))

                if new_dom != dominators[node.id]:
                    dominators[node.id] = new_dom
                    changed = True

        return dominators

    def find_all_paths(self, max_paths: int = 100) -> List[List[int]]:
        """
        Find all paths from entry to exit nodes.

        Args:
            max_paths: Maximum number of paths to enumerate

        Returns:
            List of paths (each path is a list of node IDs)
        """
        if not self.cfg or self.cfg.entry_node_id is None:
            return []

        paths = []
        self._dfs_paths(
            current_id=self.cfg.entry_node_id,
            current_path=[],
            visited=set(),
            paths=paths,
            max_paths=max_paths
        )

        return paths

    def _dfs_paths(
        self,
        current_id: int,
        current_path: List[int],
        visited: Set[int],
        paths: List[List[int]],
        max_paths: int
    ):
        """DFS helper for path enumeration."""
        if len(paths) >= max_paths:
            return

        # Add current node to path
        current_path = current_path + [current_id]
        visited = visited.copy()
        visited.add(current_id)

        # Check if reached exit
        if current_id in self.cfg.exit_node_ids:
            paths.append(current_path)
            return

        # Explore successors
        current_node = self.cfg.get_node(current_id)
        if current_node:
            for succ_id in current_node.successors:
                # Avoid infinite loops
                if succ_id not in visited:
                    self._dfs_paths(succ_id, current_path, visited, paths, max_paths)
