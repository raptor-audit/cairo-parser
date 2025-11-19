"""
Statement Parser for Cairo Functions

Parses Cairo function bodies into structured statement representations
for control flow and data flow analysis.
"""

import re
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum


class StatementType(Enum):
    """Types of statements in Cairo code."""
    ASSIGNMENT = "assignment"
    IF = "if"
    ELSE = "else"
    MATCH = "match"
    LOOP = "loop"
    RETURN = "return"
    ASSERT = "assert"
    CALL = "call"
    STORAGE_READ = "storage_read"
    STORAGE_WRITE = "storage_write"
    LET_BINDING = "let_binding"
    EXPRESSION = "expression"
    COMMENT = "comment"
    EMPTY = "empty"


@dataclass
class Statement:
    """Base class for all statement types."""
    stmt_type: StatementType
    line: int
    raw_text: str
    block_depth: int  # Nesting level of braces - no default to avoid inheritance issues

    def to_dict(self) -> Dict[str, Any]:
        """Convert statement to dictionary for serialization."""
        return {
            'type': self.stmt_type.value,
            'line': self.line,
            'raw_text': self.raw_text,
            'block_depth': self.block_depth
        }


@dataclass
class AssignmentStmt(Statement):
    """Variable assignment: x = expr;"""
    variable: str
    expression: str

    def __init__(self, variable: str, expression: str, line: int, raw_text: str, block_depth: int = 0):
        super().__init__(StatementType.ASSIGNMENT, line, raw_text, block_depth)
        self.variable = variable
        self.expression = expression

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d['variable'] = self.variable
        d['expression'] = self.expression
        return d


@dataclass
class LetBindingStmt(Statement):
    """Let binding: let x = expr; or let mut x = expr;"""
    variable: str
    expression: str
    is_mutable: bool

    def __init__(self, variable: str, expression: str, is_mutable: bool, line: int, raw_text: str, block_depth: int = 0):
        super().__init__(StatementType.LET_BINDING, line, raw_text, block_depth)
        self.variable = variable
        self.expression = expression
        self.is_mutable = is_mutable

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d['variable'] = self.variable
        d['expression'] = self.expression
        d['is_mutable'] = self.is_mutable
        return d


@dataclass
class IfStmt(Statement):
    """If statement: if condition { ... }"""
    condition: str
    has_else: bool = False

    def __init__(self, condition: str, line: int, raw_text: str, has_else: bool = False, block_depth: int = 0):
        super().__init__(StatementType.IF, line, raw_text, block_depth)
        self.condition = condition
        self.has_else = has_else

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d['condition'] = self.condition
        d['has_else'] = self.has_else
        return d


@dataclass
class ElseStmt(Statement):
    """Else statement: else { ... } or else if ..."""
    is_else_if: bool = False
    condition: Optional[str] = None

    def __init__(self, line: int, raw_text: str, is_else_if: bool = False, condition: Optional[str] = None, block_depth: int = 0):
        super().__init__(StatementType.ELSE, line, raw_text, block_depth)
        self.is_else_if = is_else_if
        self.condition = condition

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d['is_else_if'] = self.is_else_if
        if self.condition:
            d['condition'] = self.condition
        return d


@dataclass
class MatchStmt(Statement):
    """Match expression: match expr { pattern => result, ... }"""
    expression: str
    arms: List[Dict[str, str]] = field(default_factory=list)

    def __init__(self, expression: str, line: int, raw_text: str, arms: Optional[List[Dict[str, str]]] = None, block_depth: int = 0):
        super().__init__(StatementType.MATCH, line, raw_text, block_depth)
        self.expression = expression
        self.arms = arms or []

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d['expression'] = self.expression
        d['arms'] = self.arms
        return d


@dataclass
class ReturnStmt(Statement):
    """Return statement: return expr;"""
    expression: Optional[str]

    def __init__(self, expression: Optional[str], line: int, raw_text: str, block_depth: int = 0):
        super().__init__(StatementType.RETURN, line, raw_text, block_depth)
        self.expression = expression

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        if self.expression:
            d['expression'] = self.expression
        return d


@dataclass
class CallStmt(Statement):
    """Function call: function(args)"""
    function_name: str
    arguments: List[str]
    is_external: bool = False

    def __init__(self, function_name: str, arguments: List[str], line: int, raw_text: str, is_external: bool = False, block_depth: int = 0):
        super().__init__(StatementType.CALL, line, raw_text, block_depth)
        self.function_name = function_name
        self.arguments = arguments
        self.is_external = is_external

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d['function_name'] = self.function_name
        d['arguments'] = self.arguments
        d['is_external'] = self.is_external
        return d


@dataclass
class StorageReadStmt(Statement):
    """Storage read: self.storage_var.read()"""
    storage_var: str

    def __init__(self, storage_var: str, line: int, raw_text: str, block_depth: int = 0):
        super().__init__(StatementType.STORAGE_READ, line, raw_text, block_depth)
        self.storage_var = storage_var

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d['storage_var'] = self.storage_var
        return d


@dataclass
class StorageWriteStmt(Statement):
    """Storage write: self.storage_var.write(value)"""
    storage_var: str
    value: str

    def __init__(self, storage_var: str, value: str, line: int, raw_text: str, block_depth: int = 0):
        super().__init__(StatementType.STORAGE_WRITE, line, raw_text, block_depth)
        self.storage_var = storage_var
        self.value = value

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d['storage_var'] = self.storage_var
        d['value'] = self.value
        return d


@dataclass
class AssertStmt(Statement):
    """Assert statement: assert(condition, 'message') or assert!(condition)"""
    condition: str
    message: Optional[str] = None

    def __init__(self, condition: str, line: int, raw_text: str, message: Optional[str] = None, block_depth: int = 0):
        super().__init__(StatementType.ASSERT, line, raw_text, block_depth)
        self.condition = condition
        self.message = message

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d['condition'] = self.condition
        if self.message:
            d['message'] = self.message
        return d


class StatementParser:
    """
    Parser for Cairo function statements.

    Uses regex patterns to parse function bodies into structured statements
    for control flow and dataflow analysis.
    """

    # Regex patterns for Cairo statements
    PATTERNS = {
        'let_binding': r'let\s+(mut\s+)?(\w+)\s*=\s*([^;]+);',
        'assignment': r'(\w+)\s*=\s*([^;]+);',
        'if': r'if\s+([^{]+)\s*\{',
        'else': r'\}\s*else\s*\{',
        'else_if': r'\}\s*else\s+if\s+([^{]+)\s*\{',
        'match': r'match\s+([^{]+)\s*\{',
        'match_arm': r'([^=>]+)\s*=>\s*([^,}]+)',
        'return': r'return\s+([^;]+);|return;',
        'assert': r'assert[!]?\s*\(([^)]+)\)',
        'storage_read': r'self\.(\w+)\.read\(\)',
        'storage_write': r'self\.(\w+)\.write\(([^)]+)\)',
        'function_call': r'(\w+)\s*\(([^)]*)\)',
        'loop': r'loop\s*\{',
        'comment': r'//.*$',
        'block_start': r'\{',
        'block_end': r'\}',
    }

    def __init__(self):
        """Initialize the statement parser."""
        self.compiled_patterns = {
            name: re.compile(pattern)
            for name, pattern in self.PATTERNS.items()
        }

    def parse(self, function_body: str, start_line: int = 1) -> List[Statement]:
        """
        Parse function body into list of statements with block depth tracking.

        Args:
            function_body: Raw function body text
            start_line: Starting line number (for accurate line tracking)

        Returns:
            List of Statement objects with block_depth set
        """
        statements = []
        lines = function_body.split('\n')
        current_depth = 0

        for i, line in enumerate(lines):
            line_num = start_line + i

            # Track opening braces to determine current depth
            # We need to track depth BEFORE parsing the line content
            line_depth = current_depth

            # Count braces in this line
            open_count = line.count('{')
            close_count = line.count('}')

            stmt = self._parse_line(line, line_num)
            if stmt:
                # Set the block depth for control flow statements
                if isinstance(stmt, (IfStmt, ElseStmt, MatchStmt)):
                    stmt.block_depth = current_depth
                else:
                    # Regular statements use current depth after opening braces
                    stmt.block_depth = current_depth + (1 if '{' in line else 0)
                statements.append(stmt)

            # Update depth AFTER processing the line
            current_depth += open_count - close_count

        return statements

    def parse_with_blocks(self, function_body: str, start_line: int = 1) -> tuple[List[Statement], List[int]]:
        """
        Parse function body with block depth tracking.

        Args:
            function_body: Raw function body text
            start_line: Starting line number

        Returns:
            Tuple of (statements, depths) where depths[i] is the brace depth for statements[i]
        """
        statements = []
        depths = []
        lines = function_body.split('\n')
        current_depth = 0

        for i, line in enumerate(lines):
            line_num = start_line + i

            # Update depth based on braces BEFORE this line
            for char in line:
                if char == '{':
                    current_depth += 1
                elif char == '}':
                    current_depth -= 1

            stmt = self._parse_line(line, line_num)
            if stmt:
                # Record depth at which this statement appears
                # Adjust depth for control flow statements (they introduce a new block)
                if isinstance(stmt, (IfStmt, ElseStmt, MatchStmt)):
                    depths.append(current_depth - 1)
                else:
                    depths.append(current_depth)
                statements.append(stmt)

        return statements, depths

    def _parse_line(self, line: str, line_num: int) -> Optional[Statement]:
        """
        Parse a single line into a statement.

        Args:
            line: Source code line
            line_num: Line number

        Returns:
            Statement object or None
        """
        stripped = line.strip()

        # Skip empty lines and comments
        if not stripped:
            return None

        if stripped.startswith('//'):
            return None

        # Check for storage read/write first (more specific)
        if 'self.' in stripped:
            storage_write_match = self.compiled_patterns['storage_write'].search(stripped)
            if storage_write_match:
                return StorageWriteStmt(
                    storage_var=storage_write_match.group(1),
                    value=storage_write_match.group(2),
                    line=line_num,
                    raw_text=stripped
                )

            storage_read_match = self.compiled_patterns['storage_read'].search(stripped)
            if storage_read_match:
                return StorageReadStmt(
                    storage_var=storage_read_match.group(1),
                    line=line_num,
                    raw_text=stripped
                )

        # Check for control flow statements
        if_match = self.compiled_patterns['if'].search(stripped)
        if if_match:
            return IfStmt(
                condition=if_match.group(1).strip(),
                line=line_num,
                raw_text=stripped
            )

        else_if_match = self.compiled_patterns['else_if'].search(stripped)
        if else_if_match:
            return ElseStmt(
                line=line_num,
                raw_text=stripped,
                is_else_if=True,
                condition=else_if_match.group(1).strip()
            )

        else_match = self.compiled_patterns['else'].search(stripped)
        if else_match:
            return ElseStmt(
                line=line_num,
                raw_text=stripped
            )

        match_match = self.compiled_patterns['match'].search(stripped)
        if match_match:
            return MatchStmt(
                expression=match_match.group(1).strip(),
                line=line_num,
                raw_text=stripped
            )

        # Check for return statement
        return_match = self.compiled_patterns['return'].search(stripped)
        if return_match:
            expr = return_match.group(1) if return_match.group(1) else None
            return ReturnStmt(
                expression=expr,
                line=line_num,
                raw_text=stripped
            )

        # Check for assert
        assert_match = self.compiled_patterns['assert'].search(stripped)
        if assert_match:
            return AssertStmt(
                condition=assert_match.group(1),
                line=line_num,
                raw_text=stripped
            )

        # Check for let binding
        let_match = self.compiled_patterns['let_binding'].search(stripped)
        if let_match:
            is_mut = let_match.group(1) is not None
            return LetBindingStmt(
                variable=let_match.group(2),
                expression=let_match.group(3).strip(),
                is_mutable=is_mut,
                line=line_num,
                raw_text=stripped
            )

        # Check for assignment
        assignment_match = self.compiled_patterns['assignment'].search(stripped)
        if assignment_match:
            return AssignmentStmt(
                variable=assignment_match.group(1),
                expression=assignment_match.group(2).strip(),
                line=line_num,
                raw_text=stripped
            )

        # Check for function call
        call_match = self.compiled_patterns['function_call'].search(stripped)
        if call_match:
            func_name = call_match.group(1)
            args_str = call_match.group(2)
            args = [arg.strip() for arg in args_str.split(',') if arg.strip()]

            # Simple heuristic: external calls often have dispatcher pattern
            is_external = 'dispatcher' in stripped.lower() or '::' in stripped

            return CallStmt(
                function_name=func_name,
                arguments=args,
                line=line_num,
                raw_text=stripped,
                is_external=is_external
            )

        # If no specific pattern matched, return None
        return None

    def extract_variables_used(self, statement: Statement) -> List[str]:
        """
        Extract all variable names used in a statement.

        Args:
            statement: Statement to analyze

        Returns:
            List of variable names used
        """
        variables = []

        if isinstance(statement, (AssignmentStmt, LetBindingStmt)):
            # Extract variables from expression
            variables.extend(self._extract_vars_from_expr(statement.expression))
        elif isinstance(statement, IfStmt):
            variables.extend(self._extract_vars_from_expr(statement.condition))
        elif isinstance(statement, ReturnStmt) and statement.expression:
            variables.extend(self._extract_vars_from_expr(statement.expression))
        elif isinstance(statement, CallStmt):
            for arg in statement.arguments:
                variables.extend(self._extract_vars_from_expr(arg))
        elif isinstance(statement, StorageWriteStmt):
            variables.extend(self._extract_vars_from_expr(statement.value))

        return variables

    def extract_variables_defined(self, statement: Statement) -> List[str]:
        """
        Extract all variable names defined in a statement.

        Args:
            statement: Statement to analyze

        Returns:
            List of variable names defined
        """
        if isinstance(statement, LetBindingStmt):
            return [statement.variable]
        elif isinstance(statement, AssignmentStmt):
            return [statement.variable]

        return []

    def _extract_vars_from_expr(self, expression: str) -> List[str]:
        """
        Extract variable names from an expression.

        Simple regex-based extraction of identifiers.
        """
        # Match identifiers (variable names)
        var_pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b'
        matches = re.findall(var_pattern, expression)

        # Filter out keywords and literals
        keywords = {'let', 'mut', 'if', 'else', 'match', 'return', 'true', 'false', 'self'}
        variables = [m for m in matches if m not in keywords]

        return variables
