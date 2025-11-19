"""
Cairo Parser with GOT/PLT-style Symbol Resolution

Parses Cairo smart contracts with assembler-style multi-pass linking:
- Pass 1: Parse all files, build symbol table (GOT)
- Pass 2: Resolve imports from symbol table
- Pass 3: Create stubs for external dependencies (PLT)

Works for both Cairo 0 and Cairo 1 using regex pattern matching.
"""

import re
from typing import Dict, List, Set, Optional, Any
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class FunctionInfo:
    """Information about a Cairo function."""
    name: str
    visibility: str  # 'external', 'view', 'internal'
    parameters: List[Dict[str, str]]
    returns: List[Dict[str, str]]
    decorators: List[str]
    line: int
    is_stub: bool = False  # From stubbed module

    # Function body for control flow and dataflow analysis
    body_start_line: Optional[int] = None
    body_end_line: Optional[int] = None
    body_text: Optional[str] = None  # Raw function body as string


@dataclass
class StorageVarInfo:
    """Information about a Cairo storage variable."""
    name: str
    var_type: str
    line: int
    is_stub: bool = False


@dataclass
class EventInfo:
    """Information about a Cairo event."""
    name: str
    fields: List[Dict[str, str]]
    line: int
    is_stub: bool = False


@dataclass
class ImportInfo:
    """Information about an import statement."""
    module_path: str
    symbols: List[str]  # Specific symbols imported, or [] for wildcard
    line: int
    resolved: bool = False  # Whether the import was found
    stub_created: bool = False


@dataclass
class ContractInfo:
    """Complete information about a Cairo contract/module."""
    name: str
    file_path: str
    contract_type: str  # 'contract', 'interface', 'module'
    functions: List[FunctionInfo] = field(default_factory=list)
    storage_vars: List[StorageVarInfo] = field(default_factory=list)
    events: List[EventInfo] = field(default_factory=list)
    imports: List[ImportInfo] = field(default_factory=list)
    impl_blocks: List[str] = field(default_factory=list)

    # Stubbing metadata
    unresolved_calls: Set[str] = field(default_factory=set)  # Calls to missing functions
    unresolved_types: Set[str] = field(default_factory=set)  # References to missing types
    stub_modules: Dict[str, 'ContractInfo'] = field(default_factory=dict)  # Created stubs

    # Parsing metadata
    parse_errors: List[str] = field(default_factory=list)
    parse_warnings: List[str] = field(default_factory=list)


class CairoParser:
    """
    Cairo parser with GOT/PLT-style symbol resolution and stubbing.

    Parses Cairo 0 and Cairo 1 contracts using regex pattern matching.
    Instead of failing on missing imports, creates stub representations
    similar to unresolved symbols in assembly object files.
    """

    def __init__(self):
        """
        Initialize Cairo parser.

        Uses regex parsing for both Cairo 0 and Cairo 1.
        Includes GOT/PLT-style symbol resolution for stubbing.
        """
        # Symbol registry: Maps symbol names to their definitions (like GOT)
        self.symbol_registry: Dict[str, ContractInfo] = {}

        # Stub registry: Unresolved imports (like PLT stubs)
        self.stub_registry: Dict[str, ContractInfo] = {}

        # Resolution map: Track which stubs got resolved
        self.resolved_imports: Dict[str, str] = {}  # import_path -> file_path

        # Parsed files cache: Avoid reparsing
        self.parsed_files: Dict[str, Dict[str, ContractInfo]] = {}


    def parse_file(self, file_path: Path, stub_missing: bool = True, _recursive: bool = False) -> Dict[str, ContractInfo]:
        """
        Parse a single Cairo file with GOT/PLT-style symbol resolution.

        For parsing multiple files/directories, use parse_directories() instead.

        Process:
        1. Parse the file and extract contracts/symbols
        2. Register symbols in global symbol table (like GOT)
        3. For each import, try to find and parse the file
        4. Create stubs for unresolved imports (like PLT)
        5. Resolve stubs when definitions are found

        Args:
            file_path: Path to Cairo file
            stub_missing: If True, create stubs for missing imports
            _recursive: Internal flag to track recursive parsing

        Returns:
            Dictionary mapping contract/module names to ContractInfo
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Cairo file not found: {file_path}")

        # Check cache to avoid reparsing
        file_key = str(file_path.resolve())
        if file_key in self.parsed_files:
            return self.parsed_files[file_key]

        # Read source code
        source_code = file_path.read_text()

        # Detect Cairo version
        cairo_version = self._detect_cairo_version(source_code)

        # First pass: Extract imports
        imports = self._extract_imports(source_code, cairo_version)

        # Parse the file (regex parsing works for both Cairo 0 and 1)
        contracts = self._parse_cairo1_regex(source_code, file_path)

        # Register symbols in global registry (GOT-style)
        for contract_name, contract in contracts.items():
            symbol_key = f"{file_path.stem}::{contract_name}"
            self.symbol_registry[symbol_key] = contract
            # Also register by contract name alone
            self.symbol_registry[contract_name] = contract

        # Cache parsed result
        self.parsed_files[file_key] = contracts

        # Second pass: Try to resolve imports (lazy linking)
        if stub_missing:
            self._resolve_imports_recursive(imports, file_path)

        # Add import information to contracts
        for contract in contracts.values():
            contract.imports = imports
            contract.stub_modules = self.stub_registry.copy()

        return contracts

    def parse_directories(self, directories: List[Path], stub_missing: bool = True) -> Dict[str, ContractInfo]:
        """
        Parse all Cairo files in directories using assembler-style two-pass linking.

        Pass 1: Parse all .cairo files and build symbol table (like assembler collecting symbols)
        Pass 2: Resolve imports from symbol table (like assembler linking)
        Pass 3: Stub anything not found (external dependencies)

        Args:
            directories: List of directories containing Cairo files
            stub_missing: If True, create stubs for unresolved symbols

        Returns:
            Dictionary mapping contract names to ContractInfo
        """
        # Ensure we have Path objects
        directories = [Path(d) for d in directories]

        # Validate directories
        for directory in directories:
            if not directory.exists():
                raise FileNotFoundError(f"Directory not found: {directory}")
            if not directory.is_dir():
                raise ValueError(f"Not a directory: {directory}")

        # Find all Cairo files (excluding tests)
        cairo_files = self._find_all_cairo_files(directories)

        # PASS 1: Parse all files and build symbol table
        print(f"[Pass 1/3] Parsing {len(cairo_files)} files from {len(directories)} director{'y' if len(directories)==1 else 'ies'}...")
        for cairo_file in cairo_files:
            try:
                self._parse_and_register(cairo_file)
            except Exception as e:
                print(f"Warning: Failed to parse {cairo_file}: {e}")

        print(f"[Pass 1/3] Symbol table built: {len(self.symbol_registry)} symbols")

        # PASS 2: Resolve all imports from symbol table
        print(f"[Pass 2/3] Resolving imports from symbol table...")
        for file_path, contracts in self.parsed_files.items():
            for contract in contracts.values():
                self._resolve_imports_from_symbol_table(contract.imports)

        # PASS 3: Create stubs for unresolved external dependencies
        if stub_missing:
            print(f"[Pass 3/3] Creating stubs for external dependencies...")
            self._create_stubs_for_unresolved()

        # Collect all contracts
        all_contracts = {}
        for contracts in self.parsed_files.values():
            all_contracts.update(contracts)

        # Update stub information in each contract
        for contract in all_contracts.values():
            contract.stub_modules = self.stub_registry.copy()

        resolved = len(self.resolved_imports)
        stubbed = len(self.stub_registry)
        print(f"[Done] Resolved: {resolved}, Stubbed: {stubbed}")

        return all_contracts

    def _find_all_cairo_files(self, directories: List[Path]) -> List[Path]:
        """Find all .cairo files in directories, excluding tests."""
        cairo_files = []
        for directory in directories:
            for cairo_file in directory.rglob('*.cairo'):
                # Skip test files
                name = cairo_file.name
                parts = cairo_file.parts

                if name.startswith('test_') or name.endswith('_test.cairo') or name == 'tests.cairo':
                    continue
                if 'tests' in parts or 'test' in parts:
                    continue

                cairo_files.append(cairo_file)

        return cairo_files

    def _parse_and_register(self, file_path: Path):
        """Parse a file and register its symbols (Pass 1)."""
        # Check cache
        file_key = str(file_path.resolve())
        if file_key in self.parsed_files:
            return

        # Read and parse
        source_code = file_path.read_text()
        cairo_version = self._detect_cairo_version(source_code)

        # Extract imports first
        imports = self._extract_imports(source_code, cairo_version)

        # Parse (regex parsing works for both Cairo 0 and 1)
        contracts = self._parse_cairo1_regex(source_code, file_path)

        # Compute module path relative to src/
        module_path = self._compute_module_path(file_path)

        # Register the module path itself (even if no contracts)
        # This allows imports like "crate::components::upgradeable" to resolve
        if module_path:
            file_stem = file_path.stem
            # Create a placeholder "module" entry
            module_info = ContractInfo(
                name=file_stem,
                file_path=str(file_path),
                contract_type='module',
                functions=[],
                storage_vars=[],
                events=[],
                imports=imports,
                unresolved_calls=set(),
                unresolved_types=set(),
                parse_warnings=[],
                parse_errors=[],
                stub_modules={}
            )
            # Register module by its path
            self.symbol_registry[module_path] = module_info
            self.symbol_registry[file_stem] = module_info

        # Register symbols in GOT
        for contract_name, contract in contracts.items():
            # Register by simple file name
            file_stem = file_path.stem
            self.symbol_registry[f"{file_stem}::{contract_name}"] = contract
            self.symbol_registry[contract_name] = contract

            # Register by module path (e.g., components::upgradeable)
            if module_path:
                self.symbol_registry[f"{module_path}::{contract_name}"] = contract
                self.symbol_registry[module_path] = contract

            # Register all functions as symbols
            for func in contract.functions:
                self.symbol_registry[f"{file_stem}::{func.name}"] = contract
                if module_path:
                    self.symbol_registry[f"{module_path}::{func.name}"] = contract

            # Register imported symbols
            for symbol in contract.functions:
                self.symbol_registry[symbol.name] = contract

            # Store imports for later resolution
            contract.imports = imports

        # Cache
        self.parsed_files[file_key] = contracts

    def _compute_module_path(self, file_path: Path) -> Optional[str]:
        """
        Compute the module path for a file relative to src/ directory.

        Example:
          starknet-contracts/src/components/upgradeable.cairo
          -> components::upgradeable
        """
        # Find src/ in the path
        parts = list(file_path.parts)

        try:
            src_index = parts.index('src')
            # Get parts after src/
            module_parts = parts[src_index + 1:]
            # Remove .cairo extension from last part
            if module_parts:
                module_parts[-1] = Path(module_parts[-1]).stem
            # Join with ::
            return '::'.join(module_parts)
        except (ValueError, IndexError):
            return None

    def _resolve_imports_from_symbol_table(self, imports: List[ImportInfo]):
        """Resolve imports by looking up symbol table (Pass 2)."""
        for imp in imports:
            # Skip already resolved
            if imp.resolved:
                continue

            # Try to find in symbol table
            module_path = imp.module_path

            # Check various forms of the module path
            found = False

            # Try exact module path
            if module_path in self.symbol_registry:
                imp.resolved = True
                imp.stub_created = False
                self.resolved_imports[module_path] = "<symbol_table>"
                found = True
                continue

            # Try each imported symbol
            for symbol in imp.symbols:
                if symbol in self.symbol_registry:
                    imp.resolved = True
                    imp.stub_created = False
                    self.resolved_imports[module_path] = "<symbol_table>"
                    found = True
                    break

            # Try stripping 'crate::' prefix and matching
            if module_path.startswith('crate::'):
                stripped = module_path.replace('crate::', '')
                if stripped in self.symbol_registry:
                    imp.resolved = True
                    imp.stub_created = False
                    self.resolved_imports[module_path] = "<symbol_table>"
                    found = True
                    continue

                # Try matching individual path components
                parts = stripped.split('::')
                for i in range(len(parts)):
                    partial = '::'.join(parts[:i+1])
                    if partial in self.symbol_registry:
                        imp.resolved = True
                        imp.stub_created = False
                        self.resolved_imports[module_path] = "<symbol_table>"
                        found = True
                        break

    def _create_stubs_for_unresolved(self):
        """Create stubs for all unresolved imports (Pass 3)."""
        # Collect all unresolved imports from all parsed files
        unresolved = set()

        for contracts in self.parsed_files.values():
            for contract in contracts.values():
                for imp in contract.imports:
                    if not imp.resolved and imp.module_path not in self.stub_registry:
                        unresolved.add(imp.module_path)
                        # Create stub
                        stub = self._create_stub_module(imp)
                        self.stub_registry[imp.module_path] = stub
                        imp.stub_created = True

    def _detect_cairo_version(self, source_code: str) -> int:
        """
        Detect Cairo version from source code.

        Cairo 0 indicators:
        - @storage_var, @view, @external decorators
        - func keyword
        - felt type (not felt252)

        Cairo 1 indicators:
        - #[starknet::contract], #[storage], #[event] attributes
        - fn keyword
        - felt252 type
        - use statements

        Returns:
            0 for Cairo 0, 1 for Cairo 1
        """
        # Strong Cairo 1 indicators
        if any(pattern in source_code for pattern in [
            '#[starknet::contract]',
            '#[starknet::interface]',
            '#[storage]',
            'felt252',
            'fn ',
        ]):
            return 1

        # Strong Cairo 0 indicators
        if any(pattern in source_code for pattern in [
            '@storage_var',
            '@external',
            '@view',
            'func ',
        ]):
            return 0

        # Default to Cairo 1 (modern)
        return 1

    def _extract_imports(self, source_code: str, cairo_version: int) -> List[ImportInfo]:
        """
        Extract import statements from Cairo source code.

        Cairo 0: from module import Item
        Cairo 1: use module::submodule::Item;
        """
        imports = []

        if cairo_version == 0:
            # Cairo 0: from module import Item
            pattern = r'from\s+([\w.]+)\s+import\s+([^\n]+)'
            for match in re.finditer(pattern, source_code):
                module_path = match.group(1)
                symbols_str = match.group(2).strip()
                # Handle "import *" or "import Item1, Item2"
                if symbols_str == '*':
                    symbols = []
                else:
                    symbols = [s.strip() for s in symbols_str.split(',')]

                imports.append(ImportInfo(
                    module_path=module_path,
                    symbols=symbols,
                    line=source_code[:match.start()].count('\n') + 1
                ))
        else:
            # Cairo 1: use module::{Item1, Item2};
            import_patterns = [
                r'use\s+([\w:]+)::\{([^}]+)\};',  # use module::{Item1, Item2};
                r'use\s+([\w:]+);',                 # use module::Item; or use module;
            ]

            for line_num, line in enumerate(source_code.split('\n'), 1):
                line = line.strip()
                if not line.startswith('use '):
                    continue

                # Try pattern with braces first
                match = re.match(import_patterns[0], line)
                if match:
                    module_path = match.group(1)
                    symbols = [s.strip() for s in match.group(2).split(',')]
                    imports.append(ImportInfo(
                        module_path=module_path,
                        symbols=symbols,
                        line=line_num
                    ))
                    continue

                # Try simple import
                match = re.match(import_patterns[1], line)
                if match:
                    module_path = match.group(1)
                    # Check if last component looks like a type/function
                    parts = module_path.split('::')
                    if len(parts) > 1 and parts[-1][0].isupper():
                        # Likely importing specific item
                        symbols = [parts[-1]]
                        module_path = '::'.join(parts[:-1])
                    else:
                        # Importing whole module
                        symbols = []

                    imports.append(ImportInfo(
                        module_path=module_path,
                        symbols=symbols,
                        line=line_num
                    ))

        return imports

    def _resolve_imports_recursive(self, imports: List[ImportInfo], base_path: Path):
        """
        Resolve imports recursively using GOT/PLT-style lazy linking.

        Process:
        1. For each import, try to find the source file
        2. If found, recursively parse it (adds to symbol registry)
        3. If not found, create PLT-style stub
        4. After all files parsed, resolve stubs from symbol registry (GOT lookup)
        """
        base_dir = base_path.parent

        for imp in imports:
            # Check if already resolved
            if imp.module_path in self.resolved_imports:
                imp.resolved = True
                imp.stub_created = False
                continue

            # Try to find the source file
            module_file = self._find_module_file(imp.module_path, base_dir)

            if module_file and module_file.exists():
                # Found the file - recursively parse it (lazy linking)
                try:
                    self.parse_file(module_file, stub_missing=True, _recursive=True)
                    imp.resolved = True
                    imp.stub_created = False
                    self.resolved_imports[imp.module_path] = str(module_file)
                except Exception as e:
                    # If parsing fails, create stub
                    imp.resolved = False
                    imp.stub_created = True
                    if imp.module_path not in self.stub_registry:
                        stub = self._create_stub_module(imp)
                        self.stub_registry[imp.module_path] = stub
            else:
                # File not found - check if symbol exists in registry (GOT lookup)
                symbol_found = self._try_resolve_from_registry(imp)

                if not symbol_found:
                    # Create PLT-style stub for unresolved import
                    imp.resolved = False
                    imp.stub_created = True
                    if imp.module_path not in self.stub_registry:
                        stub = self._create_stub_module(imp)
                        self.stub_registry[imp.module_path] = stub

    def _try_resolve_from_registry(self, import_info: ImportInfo) -> bool:
        """
        Try to resolve import from symbol registry (GOT-style lookup).

        Returns:
            True if resolved, False if still needs stub
        """
        # Try exact module path match
        if import_info.module_path in self.symbol_registry:
            import_info.resolved = True
            import_info.stub_created = False
            return True

        # Try matching imported symbols
        for symbol in import_info.symbols:
            if symbol in self.symbol_registry:
                import_info.resolved = True
                import_info.stub_created = False
                return True

        return False

    def _find_module_file(self, module_path: str, base_dir: Path) -> Optional[Path]:
        """
        Try to find the source file for a module.

        Cairo module resolution handles both modules and symbols:
        - crate::module::submodule -> <project_root>/src/module/submodule.cairo
        - crate::module::function -> <project_root>/src/module.cairo (function is inside)
        - module::submodule -> src/module/submodule.cairo
        - module -> src/module.cairo or src/module/lib.cairo
        """
        parts = module_path.split('::')

        # Handle crate:: prefix (relative to project root)
        if parts[0] == 'crate':
            # Remove 'crate' prefix
            parts = parts[1:]
            # Find project root (directory containing src/)
            project_root = base_dir
            while project_root.parent != project_root:
                if (project_root / 'src').exists():
                    break
                project_root = project_root.parent

            # Try different possible file locations from project root
            # First try exact path
            candidates = [
                project_root / 'src' / Path('/'.join(parts)).with_suffix('.cairo'),
                project_root / 'src' / Path('/'.join(parts)) / 'lib.cairo',
            ]

            # If not found, try stripping last component (might be a function/type name)
            if len(parts) > 1:
                parent_parts = parts[:-1]
                candidates.extend([
                    project_root / 'src' / Path('/'.join(parent_parts)).with_suffix('.cairo'),
                    project_root / 'src' / Path('/'.join(parent_parts)) / 'lib.cairo',
                ])
        else:
            # Regular module path
            candidates = [
                base_dir / 'src' / Path('/'.join(parts)).with_suffix('.cairo'),
                base_dir / 'src' / Path('/'.join(parts)) / 'lib.cairo',
                base_dir / Path('/'.join(parts)).with_suffix('.cairo'),
            ]

            # If not found, try stripping last component
            if len(parts) > 1:
                parent_parts = parts[:-1]
                candidates.extend([
                    base_dir / 'src' / Path('/'.join(parent_parts)).with_suffix('.cairo'),
                    base_dir / 'src' / Path('/'.join(parent_parts)) / 'lib.cairo',
                    base_dir / Path('/'.join(parent_parts)).with_suffix('.cairo'),
                ])

        for candidate in candidates:
            if candidate.exists():
                return candidate

        return None

    def _create_stub_module(self, import_info: ImportInfo) -> ContractInfo:
        """
        Create a stub module for an unresolved import.

        The stub acts like an unresolved symbol in assembly - we know it exists
        and what it's called, but not its actual implementation.
        """
        stub = ContractInfo(
            name=import_info.module_path.split('::')[-1],
            file_path=f"<stub:{import_info.module_path}>",
            contract_type='stub'
        )

        # Create stub functions for imported symbols
        for symbol in import_info.symbols:
            stub.functions.append(FunctionInfo(
                name=symbol,
                visibility='external',  # Assume external
                parameters=[],  # Unknown
                returns=[],  # Unknown
                decorators=['stub'],
                line=0,
                is_stub=True
            ))

        stub.parse_warnings.append(
            f"Stub created for missing module: {import_info.module_path}"
        )

        return stub


    def _parse_cairo1_regex(self, source_code: str, file_path: Path) -> Dict[str, ContractInfo]:
        """
        Parse Cairo source code using regex patterns.

        Works for both Cairo 0 and Cairo 1 syntax.
        Extracts contracts, functions, storage, events, and imports using
        source-level pattern matching.
        """
        contracts = {}
        current_contract = None
        in_contract_decorator = False

        lines = source_code.split('\n')

        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()

            # Contract/interface/module declaration
            if '#[starknet::contract]' in stripped or '#[starknet::interface]' in stripped:
                in_contract_decorator = True
                contract_type = 'interface' if 'interface' in stripped else 'contract'

                # Look for mod declaration in next few lines
                for next_line_num in range(line_num, min(line_num + 5, len(lines))):
                    next_line = lines[next_line_num].strip()
                    # Match: mod Name, pub mod Name, etc.
                    if 'mod ' in next_line:
                        match = re.search(r'mod\s+(\w+)', next_line)
                        if match:
                            contract_name = match.group(1)
                            current_contract = ContractInfo(
                                name=contract_name,
                                file_path=str(file_path),
                                contract_type=contract_type
                            )
                            contracts[contract_name] = current_contract
                            in_contract_decorator = False
                            break

            # Storage struct
            elif current_contract and '#[storage]' in stripped:
                # Storage variables follow in next struct
                for next_line_num in range(line_num, min(line_num + 50, len(lines))):
                    next_line = lines[next_line_num].strip()

                    # Find struct Storage
                    if 'struct Storage' in next_line:
                        # Parse storage variables inside
                        brace_count = 0
                        for storage_line_num in range(next_line_num, min(next_line_num + 100, len(lines))):
                            storage_line = lines[storage_line_num].strip()

                            if '{' in storage_line:
                                brace_count += storage_line.count('{')
                            if '}' in storage_line:
                                brace_count -= storage_line.count('}')

                            # Parse storage variable: name: Type
                            if ':' in storage_line and brace_count > 0:
                                var_match = re.match(r'(\w+)\s*:\s*([^,]+)', storage_line)
                                if var_match:
                                    var_name = var_match.group(1)
                                    var_type = var_match.group(2).strip().rstrip(',')
                                    current_contract.storage_vars.append(StorageVarInfo(
                                        name=var_name,
                                        var_type=var_type,
                                        line=storage_line_num + 1
                                    ))

                            if brace_count == 0 and '}' in storage_line:
                                break
                        break

            # Functions (more robust matching)
            elif current_contract and 'fn ' in stripped:
                func_info = self._parse_function(stripped, line_num)
                if func_info:
                    # Extract function body for control flow analysis
                    body_text, body_start, body_end = self._extract_function_body(lines, line_num)
                    if body_text is not None:
                        func_info.body_text = body_text
                        func_info.body_start_line = body_start
                        func_info.body_end_line = body_end
                    current_contract.functions.append(func_info)

            # Events
            elif current_contract and '#[event]' in stripped:
                # Event follows
                for next_line_num in range(line_num, min(line_num + 10, len(lines))):
                    next_line = lines[next_line_num].strip()
                    if next_line.startswith('enum ') or next_line.startswith('struct '):
                        event_info = self._parse_event(next_line, next_line_num + 1)
                        if event_info:
                            current_contract.events.append(event_info)
                        break

        return contracts

    def _extract_function_body(self, source_lines: List[str], start_line: int) -> tuple[Optional[str], Optional[int], Optional[int]]:
        """
        Extract function body from source code using brace matching.

        Args:
            source_lines: List of all source code lines
            start_line: Line number where function declaration starts (1-indexed)

        Returns:
            Tuple of (body_text, body_start_line, body_end_line)
            Returns (None, None, None) if body cannot be extracted
        """
        if start_line < 1 or start_line > len(source_lines):
            return None, None, None

        brace_count = 0
        body_lines = []
        body_start = None
        body_end = None
        found_opening_brace = False

        # Start from the function declaration line
        for i in range(start_line - 1, len(source_lines)):
            line = source_lines[i]

            # Track braces
            for char in line:
                if char == '{':
                    if not found_opening_brace:
                        found_opening_brace = True
                        body_start = i + 1  # 1-indexed
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1

            # Collect body lines after finding opening brace
            if found_opening_brace:
                body_lines.append(line)

            # Check if we've closed the function body
            if found_opening_brace and brace_count == 0:
                body_end = i + 1  # 1-indexed
                break

        # Return None if we never found a complete body
        if not found_opening_brace or body_end is None:
            return None, None, None

        # Join the body lines
        body_text = '\n'.join(body_lines)

        return body_text, body_start, body_end

    def _parse_function(self, line: str, line_num: int) -> Optional[FunctionInfo]:
        """Parse a Cairo function declaration."""
        # Pattern: fn function_name(params) -> return_type
        # Handle multi-line params by just looking for fn NAME
        match = re.search(r'fn\s+(\w+)', line)
        if not match:
            return None

        func_name = match.group(1)

        # Try to extract params and return type (might span multiple lines)
        params_match = re.search(r'\(([^)]*)\)', line)
        params_str = params_match.group(1) if params_match else ""

        returns_match = re.search(r'->\s*([^{;]+)', line)
        returns_str = returns_match.group(1) if returns_match else None

        # Determine visibility from context
        visibility = 'internal'
        decorators = []

        # Check for visibility modifiers
        if '#[external' in line or 'external(v' in line:
            visibility = 'external'
            decorators.append('external')
        elif '#[view' in line:
            visibility = 'view'
            decorators.append('view')
        elif 'pub fn' in line or 'pub(crate) fn' in line:
            visibility = 'internal'  # pub is still internal to contract
            decorators.append('pub')

        # Parse parameters
        parameters = []
        if params_str.strip():
            for param in params_str.split(','):
                param = param.strip()
                if ':' in param:
                    # Handle ref/mut modifiers
                    param = param.replace('ref ', '').replace('mut ', '')
                    param_parts = param.split(':', 1)
                    if len(param_parts) == 2:
                        parameters.append({
                            'name': param_parts[0].strip(),
                            'type': param_parts[1].strip()
                        })

        # Parse return type
        returns = []
        if returns_str:
            returns.append({'type': returns_str.strip()})

        return FunctionInfo(
            name=func_name,
            visibility=visibility,
            parameters=parameters,
            returns=returns,
            decorators=decorators,
            line=line_num
        )

    def _parse_event(self, line: str, line_num: int) -> Optional[EventInfo]:
        """Parse a Cairo event declaration."""
        # Pattern: struct EventName or enum EventName
        match = re.match(r'(?:struct|enum)\s+(\w+)', line)
        if not match:
            return None

        event_name = match.group(1)

        return EventInfo(
            name=event_name,
            fields=[],  # Would need to parse the full struct/enum
            line=line_num
        )

    def get_stub_report(self) -> Dict[str, Any]:
        """
        Get report of all stubbed modules and symbol resolution.

        Returns:
            Dictionary with stub statistics, resolved imports, and symbol registry
        """
        return {
            'total_stubs': len(self.stub_registry),
            'total_resolved': len(self.resolved_imports),
            'total_symbols': len(self.symbol_registry),
            'stubbed_modules': list(self.stub_registry.keys()),
            'resolved_modules': list(self.resolved_imports.keys()),
            'stubs': {
                name: {
                    'file_path': stub.file_path,
                    'functions': len(stub.functions),
                    'warnings': stub.parse_warnings
                }
                for name, stub in self.stub_registry.items()
            },
            'resolved': {
                module: file_path
                for module, file_path in self.resolved_imports.items()
            }
        }
