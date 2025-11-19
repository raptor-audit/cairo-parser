# Cairo Parser Plugin

Assembler-style Cairo smart contract parser with GOT/PLT symbol resolution.

## Overview

Cairo Parser uses a **three-pass assembler-style approach** to parse Cairo contracts:

1. **Pass 1 (Build Symbol Table)**: Parse all `.cairo` files and build global symbol table (like GOT - Global Offset Table)
2. **Pass 2 (Link Symbols)**: Resolve imports by looking up the symbol table (like assembler linking)
3. **Pass 3 (Create Stubs)**: Create stubs only for truly external dependencies (like PLT - Procedure Linkage Table)

## Key Features

- ✅ **No compiler required** - uses regex pattern matching
- ✅ **Multi-directory support** - parse multiple source directories at once
- ✅ **Assembler-style linking** - resolves local imports automatically
- ✅ **Smart stubbing** - stubs only external dependencies (stdlib, runtime)
- ✅ **Cairo 0 & 1 support** - handles both syntax versions
- ✅ **Test file exclusion** - automatically skips test files
- ✅ **Control Flow Analysis** - builds control flow graphs (CFG) for functions
- ✅ **Dataflow Analysis** - tracks def-use chains, storage access, and external calls
- ✅ **Security Analysis** - detects uninitialized variables and unused definitions

## Usage

### As Library

```python
from pathlib import Path
from parser import CairoParser

# Initialize parser
parser = CairoParser()

# Parse multiple directories (assembler-style)
contracts = parser.parse_directories([
    Path('contracts/'),
    Path('lib/'),
    Path('deps/')
])

for name, contract in contracts.items():
    print(f"Contract: {name}")
    print(f"  Functions: {len(contract.functions)}")
    print(f"  Storage: {len(contract.storage_vars)}")
    print(f"  Events: {len(contract.events)}")

    # Check import resolution
    for imp in contract.imports:
        status = "✓ Resolved" if imp.resolved else "✗ Stubbed"
        print(f"  Import [{status}]: {imp.module_path}")

# Get stub report
stub_report = parser.get_stub_report()
print(f"\nTotal stubs created: {stub_report['total_stubs']}")
print(f"Total resolved: {stub_report['total_resolved']}")
for module in stub_report['stubbed_modules']:
    print(f"  - {module}")
```

### As CLI

**Parse single directory:**
```bash
python -m cairo_parser contracts/
```

**Parse multiple directories (assembler-style):**
```bash
python -m cairo_parser contracts/ lib/ deps/
```

**JSON output with stub report:**
```bash
python -m cairo_parser contracts/ --format json --stub-report -o output.json
```

**Fail on missing imports (no stubbing):**
```bash
python -m cairo_parser contracts/ --no-stub
```

**Control Flow and Dataflow Analysis:**
```bash
# Perform analysis and save results
python -m cairo_parser contracts/ --analyze --analysis-output analysis.json

# Show analysis warnings in summary output
python -m cairo_parser contracts/ --analyze --show-warnings

# Full analysis with both parser and analysis output
python -m cairo_parser contracts/ --analyze \
  --format json -o contracts.json \
  --analysis-output analysis.json \
  --analysis-format yaml
```

### Via Raptor

```bash
# Parse Cairo contracts
raptor parse-cairo src/

# Multiple directories
raptor parse-cairo contracts/ lib/ --stub-report

# JSON output
raptor parse-cairo src/ --format json -o contracts.json
```

## How It Works

### Assembler-Style Three-Pass Parsing

```
Input: contracts/ lib/ deps/

Pass 1: Parse all files → Build Symbol Table (GOT)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
contracts/positions.cairo       → positions::Positions
lib/components/upgradeable.cairo → components::upgradeable
deps/math/delta.cairo           → math::delta

Symbol Table: 659 symbols registered

Pass 2: Resolve imports from Symbol Table
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
use crate::components::upgradeable  → ✓ Found in symbol table
use crate::math::delta              → ✓ Found in symbol table
use core::array                     → ✗ Not in symbol table

Resolved: 42 imports

Pass 3: Stub external dependencies (PLT)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
core::array         → Create stub (Cairo stdlib)
starknet::storage   → Create stub (Starknet runtime)

Stubbed: 16 external modules

Result: All local imports resolved, only external deps stubbed
```

### Module Path Resolution

Files are registered using their path relative to `src/`:

```
starknet-contracts/src/components/upgradeable.cairo
                    └─→ components::upgradeable

starknet-contracts/src/math/delta.cairo
                    └─→ math::delta
```

Imports like `use crate::components::upgradeable` resolve to the symbol table entry for `components::upgradeable`.

### Test File Exclusion

Parser automatically skips:
- Files matching: `test_*.cairo`, `*_test.cairo`, `tests.cairo`
- Files in directories: `tests/`, `test/`

## Data Structures

### ContractInfo

```python
@dataclass
class ContractInfo:
    name: str
    file_path: str
    contract_type: str  # 'contract', 'interface', 'module', 'stub'
    functions: List[FunctionInfo]
    storage_vars: List[StorageVarInfo]
    events: List[EventInfo]
    imports: List[ImportInfo]

    # Stubbing metadata
    stub_modules: Dict[str, ContractInfo]
    unresolved_calls: Set[str]
    unresolved_types: Set[str]

    # Parsing status
    parse_errors: List[str]
    parse_warnings: List[str]
```

### FunctionInfo

```python
@dataclass
class FunctionInfo:
    name: str
    visibility: str  # 'external', 'view', 'internal'
    parameters: List[Dict[str, str]]
    returns: List[Dict[str, str]]
    decorators: List[str]
    line: int
    is_stub: bool  # True if from stubbed module
```

### ImportInfo

```python
@dataclass
class ImportInfo:
    module_path: str
    symbols: List[str]  # Imported symbols
    line: int
    resolved: bool  # Whether import was found in symbol table
    stub_created: bool  # Whether stub was created
```

## Output Formats

### Summary (Default)

```
============================================================
Cairo Parser Results
============================================================
Total Files: 51
Total Contracts: 11

CONTRACT: Positions
  File: starknet-contracts/src/positions.cairo
  Functions (48):
    - constructor (internal)
    - mint (internal)
    - withdraw (internal)
  Storage Variables (6):
    - core: ICoreDispatcher
    - nft: IOwnedNFTDispatcher
  Imports (26):
    [✓] crate::components::upgradeable
    [✓] crate::math::delta
    [✗ STUBBED] core::array
    [✗ STUBBED] starknet::storage

Stub Report
============================================================
Total Stubs: 16
Total Resolved: 42
Stubbed Modules:
  - core::array
  - core::cmp
  - starknet::storage
  - starknet
```

### JSON

```json
{
  "metadata": {
    "total_files": 51,
    "total_contracts": 11,
    "stubbing_enabled": true
  },
  "contracts": {
    "Positions": {
      "name": "Positions",
      "file_path": "starknet-contracts/src/positions.cairo",
      "contract_type": "contract",
      "functions": [...],
      "imports": [
        {
          "module_path": "crate::components::upgradeable",
          "resolved": true,
          "stub_created": false
        },
        {
          "module_path": "core::array",
          "resolved": false,
          "stub_created": true
        }
      ]
    }
  },
  "stub_report": {
    "total_stubs": 16,
    "total_resolved": 42,
    "total_symbols": 659,
    "stubbed_modules": ["core::array", "starknet::storage", ...]
  }
}
```

## Cairo Language Support

### Supported Constructs

- **Contracts**: `#[starknet::contract] mod ContractName`
- **Interfaces**: `#[starknet::interface] trait IContract`
- **Components**: `#[starknet::component] pub mod Component`
- **Functions**: `fn function_name(params) -> ReturnType`
- **Storage**: `#[storage] struct Storage`
- **Events**: `#[event] enum/struct EventName`
- **Imports**: `use module::path::{Symbol1, Symbol2};`

### Cairo Version Support

- **Cairo 1.0+**: ✓ Full support
- **Cairo 0**: ✓ Basic support (regex-based parsing)

## Typical Results

Parsing a real-world Cairo project:

```
[Pass 1/3] Parsing 51 files from 1 directory...
[Pass 1/3] Symbol table built: 659 symbols
[Pass 2/3] Resolving imports from symbol table...
[Pass 3/3] Creating stubs for external dependencies...
[Done] Resolved: 42, Stubbed: 16
```

**Analysis:**
- **72% resolution rate** - 42 out of 58 total imports resolved locally
- **Only 16 stubs** - Just external dependencies (Cairo stdlib, Starknet runtime)
- **659 symbols** - All contracts, modules, functions registered

**Stubbed modules (expected):**
- `core::array`, `core::cmp`, `core::traits` (Cairo standard library)
- `starknet::storage`, `starknet::get_contract_address` (Starknet runtime)
- `super` (relative imports)

## Advanced Usage

### Disable Stubbing

```python
# Fail on any unresolved imports
contracts = parser.parse_directories([Path('src/')], stub_missing=False)
```

### Single File Parsing (Legacy)

```python
# Parse one file at a time (old behavior, not recommended)
contracts = parser.parse_file(Path('contract.cairo'))
```

### Access Stub Information

```python
contracts = parser.parse_directories([Path('src/')])

for name, contract in contracts.items():
    # Check if contract has stubbed dependencies
    if contract.stub_modules:
        print(f"{name} has {len(contract.stub_modules)} stubbed dependencies")

    # Check individual imports
    for imp in contract.imports:
        if not imp.resolved:
            print(f"Stubbed: {imp.module_path}")
```

### Control Flow and Dataflow Analysis

The parser includes a powerful static analysis engine that performs:
- **Control Flow Graph (CFG)** construction
- **Def-Use chain** analysis
- **Storage access** tracking
- **External call** detection
- **Uninitialized variable** detection
- **Dead code** detection

**Basic Analysis:**
```python
from cairo_parser import CairoParser, CairoAnalyzer

# Parse contracts
parser = CairoParser()
contracts = parser.parse_directories([Path('contracts/')])

# Analyze contracts
analyzer = CairoAnalyzer()
results = analyzer.analyze_contracts(contracts)

# Get summary statistics
summary = analyzer.get_summary_stats(results)
print(f"Analyzed {summary['functions_with_body']} functions")
print(f"Found {summary['total_warnings']} warnings")
print(f"Storage reads: {summary['total_storage_reads']}")
print(f"Storage writes: {summary['total_storage_writes']}")
print(f"External calls: {summary['total_external_calls']}")
```

**Detailed Function Analysis:**
```python
# Analyze specific function
for result in results:
    for func in result.functions:
        if func.has_body:
            # Access CFG
            cfg = func.cfg
            print(f"Function {func.function_name}:")
            print(f"  CFG nodes: {len(cfg['nodes'])}")
            print(f"  Entry: {cfg['entry_node']}")
            print(f"  Exits: {cfg['exit_nodes']}")

            # Access dataflow results
            dataflow = func.dataflow
            print(f"  Def-use chains: {len(dataflow['def_use_chains'])}")
            print(f"  Storage accesses: {len(dataflow['storage_accesses'])}")
            print(f"  External calls: {len(dataflow['external_calls'])}")

            # Check warnings
            for warning in func.warnings:
                print(f"  Warning: {warning['message']}")
```

**CFG Visualization:**
```python
from cairo_parser.analysis import CFGBuilder, StatementParser

# Parse function body
stmt_parser = StatementParser()
statements = stmt_parser.parse(function.body_text, function.body_start_line)

# Build CFG
cfg_builder = CFGBuilder()
cfg = cfg_builder.build(function.name, statements)

# Access CFG nodes and edges
for node in cfg.nodes:
    print(f"Node {node.id} ({node.node_type.value}):")
    if node.statement:
        print(f"  Statement: {node.statement.raw_text}")
    print(f"  Successors: {node.successors}")
    print(f"  Predecessors: {node.predecessors}")

# Compute dominators
dominators = cfg_builder.compute_dominators()
for node_id, dom_set in dominators.items():
    print(f"Node {node_id} dominated by: {dom_set}")

# Find all execution paths
paths = cfg_builder.find_all_paths(max_paths=100)
print(f"Found {len(paths)} execution paths")
```

**Dataflow Analysis:**
```python
from cairo_parser.analysis import DataflowAnalyzer

# Create dataflow analyzer
dataflow_analyzer = DataflowAnalyzer(cfg)

# Analyze def-use chains
def_use_chains = dataflow_analyzer.analyze_def_use_chains()
for chain in def_use_chains:
    var = chain['variable']
    defs = chain['definitions']
    uses = chain['uses']
    print(f"Variable '{var}': defined at nodes {defs}, used at nodes {uses}")

# Track storage access
storage_accesses = dataflow_analyzer.analyze_storage_access()
for access in storage_accesses:
    print(f"{access['access_type'].upper()}: {access['storage_var']} at line {access['line']}")

# Find external calls
external_calls = dataflow_analyzer.analyze_external_calls()
for call in external_calls:
    print(f"External call: {call['function_name']}({', '.join(call['arguments'])})")

# Detect potential issues
uninit_vars = dataflow_analyzer.find_uninitialized_variables()
for warning in uninit_vars:
    print(f"Warning: {warning['message']} at line {warning['line']}")

unused_defs = dataflow_analyzer.find_unused_definitions()
for warning in unused_defs:
    print(f"Warning: {warning['message']}")
```

**Saving Analysis Results:**
```python
from cairo_parser.analysis.serialization import save_analysis

# Save as JSON
save_analysis(
    [r.to_dict() for r in results],
    Path('analysis.json'),
    format='json',
    pretty=True
)

# Save as YAML
save_analysis(
    [r.to_dict() for r in results],
    Path('analysis.yaml'),
    format='yaml'
)
```

### Integration with Analysis Tools

```python
# Parse with stubbing
contracts = parser.parse_directories([Path('contracts/')])

# Run analysis (even with stubs)
analyzer = CairoAnalyzer()
for name, contract in contracts.items():
    if not contract.is_stub:
        result = analyzer.analyze_contract(contract)

        for func_result in result.functions:
            if func_result.has_body:
                # Analyze real functions
                print(f"Analyzing {func_result.function_name}")
                # ... use CFG and dataflow results
            else:
                # Skip stubbed or bodyless functions
                print(f"Skipping {func_result.function_name} (no body)")
```

## Key Advantages

- ✅ **No external dependencies** - just Python stdlib + regex
- ✅ **Assembler-style linking** - resolves symbols across all files first
- ✅ **High resolution rate** - typically 70%+ local imports resolved
- ✅ **Smart stubbing** - only external dependencies stubbed
- ✅ **Multi-directory support** - parse entire dependency trees
- ✅ **Fast** - no compiler overhead

## Best Practices

1. **Parse from project root**: Include all source directories
2. **Use multiple directories**: `python -m cairo_parser contracts/ lib/ deps/`
3. **Check stub report**: Use `--stub-report` to see what's external
4. **Expect external stubs**: Cairo stdlib and Starknet runtime will always be stubbed

## Files

- `parser.py` - Core Cairo parser with GOT/PLT symbol resolution
- `analysis/` - Control flow and dataflow analysis modules
  - `analyzer.py` - Main analysis orchestrator
  - `cfg.py` - Control flow graph builder
  - `dataflow.py` - Dataflow analysis (def-use chains, storage tracking)
  - `statements.py` - Statement parser for function bodies
  - `serialization.py` - JSON/YAML output support
- `install.py` - Plugin installation and registration
- `__init__.py` - Package initialization
- `__main__.py` - CLI interface

## Requirements

- Python 3.8+
- Optional: pyyaml (for YAML output)

## License

[GPL-3.0](LICENSE)