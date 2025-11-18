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

### Integration with Analysis Tools

```python
# Parse with stubbing
contracts = parser.parse_directories([Path('contracts/')])

# Run analysis (even with stubs)
for name, contract in contracts.items():
    for func in contract.functions:
        if func.is_stub:
            # Handle stubbed functions differently
            print(f"Skipping analysis of stubbed function: {func.name}")
        else:
            # Analyze real functions
            analyze_function(func)
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
- `install.py` - Plugin installation and registration
- `__init__.py` - Package initialization
- `__main__.py` - CLI interface

## Requirements

- Python 3.8+
- Optional: pyyaml (for YAML output)

## License

[GPL-3.0](LICENSE)