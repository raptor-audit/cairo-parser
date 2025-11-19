"""
Cairo Parser CLI

Parse Cairo smart contracts from the command line with dependency stubbing.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List

# Import parser
from cairo_parser.parser import CairoParser, ContractInfo

# Import analyzer
from cairo_parser.analysis.analyzer import CairoAnalyzer
from cairo_parser.analysis.serialization import (
    save_analysis,
    format_summary_text,
    format_warnings_text,
)


def find_cairo_files(paths: List[str]) -> List[Path]:
    """Find all Cairo files in given paths, excluding test files."""
    cairo_files = []

    for path_str in paths:
        path = Path(path_str)

        if not path.exists():
            print(f"Warning: Path not found: {path}", file=sys.stderr)
            continue

        if path.is_file():
            if path.suffix == '.cairo':
                # Skip test files
                if _is_test_file(path):
                    continue
                cairo_files.append(path)
            else:
                print(f"Warning: Not a Cairo file: {path}", file=sys.stderr)
        elif path.is_dir():
            # Recursively find .cairo files, excluding tests
            for cairo_file in path.rglob('*.cairo'):
                if not _is_test_file(cairo_file):
                    cairo_files.append(cairo_file)

    return cairo_files


def _is_test_file(file_path: Path) -> bool:
    """Check if a file is a test file."""
    name = file_path.name
    parts = file_path.parts

    # Check filename patterns
    if name.startswith('test_') or name.endswith('_test.cairo') or name == 'tests.cairo':
        return True

    # Check if in tests/ directory
    if 'tests' in parts or 'test' in parts:
        return True

    return False


def format_contract_summary(contract: ContractInfo) -> str:
    """Format contract info as readable summary."""
    lines = []
    lines.append(f"\n{contract.contract_type.upper()}: {contract.name}")
    lines.append(f"  File: {contract.file_path}")

    if contract.functions:
        lines.append(f"  Functions ({len(contract.functions)}):")
        for func in contract.functions:
            stub_marker = " [STUB]" if func.is_stub else ""
            lines.append(f"    - {func.name} ({func.visibility}){stub_marker}")

    if contract.storage_vars:
        lines.append(f"  Storage Variables ({len(contract.storage_vars)}):")
        for var in contract.storage_vars:
            stub_marker = " [STUB]" if var.is_stub else ""
            lines.append(f"    - {var.name}: {var.var_type}{stub_marker}")

    if contract.events:
        lines.append(f"  Events ({len(contract.events)}):")
        for event in contract.events:
            stub_marker = " [STUB]" if event.is_stub else ""
            lines.append(f"    - {event.name}{stub_marker}")

    if contract.imports:
        lines.append(f"  Imports ({len(contract.imports)}):")
        for imp in contract.imports:
            status = "✓" if imp.resolved else "✗ STUBBED"
            symbols_str = f" {{{', '.join(imp.symbols)}}}" if imp.symbols else ""
            lines.append(f"    [{status}] {imp.module_path}{symbols_str}")

    if contract.stub_modules:
        lines.append(f"  Stub Modules Created ({len(contract.stub_modules)}):")
        for stub_name in contract.stub_modules.keys():
            lines.append(f"    - {stub_name}")

    if contract.parse_warnings:
        lines.append(f"  Warnings:")
        for warning in contract.parse_warnings:
            lines.append(f"    ⚠ {warning}")

    if contract.parse_errors:
        lines.append(f"  Errors:")
        for error in contract.parse_errors:
            lines.append(f"    ✗ {error}")

    return '\n'.join(lines)


def contract_to_dict(contract: ContractInfo) -> dict:
    """Convert ContractInfo to dictionary for JSON serialization."""
    return {
        'name': contract.name,
        'file_path': contract.file_path,
        'contract_type': contract.contract_type,
        'functions': [
            {
                'name': f.name,
                'visibility': f.visibility,
                'parameters': f.parameters,
                'returns': f.returns,
                'decorators': f.decorators,
                'line': f.line,
                'is_stub': f.is_stub,
            }
            for f in contract.functions
        ],
        'storage_vars': [
            {
                'name': v.name,
                'type': v.var_type,
                'line': v.line,
                'is_stub': v.is_stub,
            }
            for v in contract.storage_vars
        ],
        'events': [
            {
                'name': e.name,
                'fields': e.fields,
                'line': e.line,
                'is_stub': e.is_stub,
            }
            for e in contract.events
        ],
        'imports': [
            {
                'module_path': i.module_path,
                'symbols': i.symbols,
                'line': i.line,
                'resolved': i.resolved,
                'stub_created': i.stub_created,
            }
            for i in contract.imports
        ],
        'unresolved_calls': list(contract.unresolved_calls),
        'unresolved_types': list(contract.unresolved_types),
        'parse_warnings': contract.parse_warnings,
        'parse_errors': contract.parse_errors,
    }


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Parse Cairo smart contracts with dependency stubbing',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Parse a single file:
    python -m cairo_parser contract.cairo

  Parse entire directory:
    python -m cairo_parser src/

  Output to JSON file:
    python -m cairo_parser src/ --format json -o output.json

  Get stub report:
    python -m cairo_parser src/ --stub-report

  Fail on missing imports (no stubbing):
    python -m cairo_parser src/ --no-stub
        """
    )

    parser.add_argument('paths', nargs='+', help='Cairo files or directories to parse')
    parser.add_argument('--format', choices=['json', 'yaml', 'summary'],
                        default='summary', help='Output format (default: summary)')
    parser.add_argument('-o', '--output', help='Output file (default: stdout)')
    parser.add_argument('--no-stub', action='store_true',
                        help='Fail on missing imports instead of creating stubs')
    parser.add_argument('--stub-report', action='store_true',
                        help='Include detailed stub report in output')
    parser.add_argument('--quiet', action='store_true', help='Suppress progress messages')

    # Analysis options
    parser.add_argument('--analyze', action='store_true',
                        help='Perform control flow and dataflow analysis')
    parser.add_argument('--analysis-output', help='Output file for analysis results (JSON/YAML)')
    parser.add_argument('--analysis-format', choices=['json', 'yaml'],
                        default='json', help='Analysis output format (default: json)')
    parser.add_argument('--show-warnings', action='store_true',
                        help='Display analysis warnings in summary output')

    args = parser.parse_args()

    # Find Cairo files
    cairo_files = find_cairo_files(args.paths)

    # Separate into files and directories
    input_files = [Path(p) for p in args.paths if Path(p).is_file()]
    input_dirs = [Path(p) for p in args.paths if Path(p).is_dir()]

    # Initialize parser
    cairo_parser = CairoParser()

    # Determine parsing strategy
    stub_missing = not args.no_stub

    if input_dirs:
        # Use assembler-style multi-directory parsing
        all_contracts = cairo_parser.parse_directories(input_dirs, stub_missing=stub_missing)

        # Also parse individual files if provided
        if input_files:
            for file_path in input_files:
                try:
                    contracts = cairo_parser.parse_file(file_path, stub_missing=stub_missing)
                    all_contracts.update(contracts)
                except Exception as e:
                    print(f"Error parsing {file_path}: {e}", file=sys.stderr)
                    if args.no_stub:
                        return 1

    else:
        # No directories, just parse files individually (old behavior)
        if not cairo_files:
            print("Error: No Cairo files found", file=sys.stderr)
            return 1

        if not args.quiet:
            print(f"Found {len(cairo_files)} Cairo file(s)")

        all_contracts = {}
        for file_path in cairo_files:
            if not args.quiet:
                print(f"Parsing {file_path}...")

            try:
                contracts = cairo_parser.parse_file(file_path, stub_missing=stub_missing)
                all_contracts.update(contracts)

                if not args.quiet:
                    print(f"  Found {len(contracts)} contract(s)")

            except Exception as e:
                print(f"Error parsing {file_path}: {e}", file=sys.stderr)
                if args.no_stub:
                    return 1
                continue

    # Perform CFG and dataflow analysis if requested
    analysis_results = None
    if args.analyze:
        if not args.quiet:
            print(f"\n[Analysis] Performing control flow and dataflow analysis...")

        analyzer = CairoAnalyzer()
        analysis_results = analyzer.analyze_contracts(all_contracts)

        if not args.quiet:
            summary = analyzer.get_summary_stats(analysis_results)
            print(f"[Analysis] Analyzed {summary['functions_with_body']} functions")
            print(f"[Analysis] Found {summary['total_warnings']} warnings")

        # Save analysis results if output file specified
        if args.analysis_output:
            output_path = Path(args.analysis_output)
            save_analysis(
                [r.to_dict() for r in analysis_results],
                output_path,
                format=args.analysis_format
            )
            if not args.quiet:
                print(f"[Analysis] Results written to {args.analysis_output}")

    # Generate output
    if args.format == 'summary':
        output_lines = []
        output_lines.append(f"\n{'='*60}")
        output_lines.append(f"Cairo Parser Results")
        output_lines.append(f"{'='*60}")
        output_lines.append(f"Total Files: {len(cairo_files)}")
        output_lines.append(f"Total Contracts: {len(all_contracts)}")

        for contract in all_contracts.values():
            output_lines.append(format_contract_summary(contract))

        if args.stub_report:
            stub_report = cairo_parser.get_stub_report()
            output_lines.append(f"\n{'='*60}")
            output_lines.append(f"Stub Report")
            output_lines.append(f"{'='*60}")
            output_lines.append(f"Total Stubs: {stub_report['total_stubs']}")
            if stub_report['stubbed_modules']:
                output_lines.append(f"Stubbed Modules:")
                for module in stub_report['stubbed_modules']:
                    output_lines.append(f"  - {module}")

        # Add analysis warnings if requested
        if args.show_warnings and analysis_results:
            output_lines.append(f"\n{'='*60}")
            output_lines.append(f"Analysis Warnings")
            output_lines.append(f"{'='*60}")
            warnings_text = format_warnings_text([r.to_dict() for r in analysis_results])
            output_lines.append(warnings_text)

            # Add summary stats
            analyzer = CairoAnalyzer()
            summary = analyzer.get_summary_stats(analysis_results)
            output_lines.append(f"\n{format_summary_text(summary)}")

        output = '\n'.join(output_lines)

    elif args.format == 'json':
        output_data = {
            'metadata': {
                'total_files': len(cairo_files),
                'total_contracts': len(all_contracts),
                'stubbing_enabled': stub_missing,
            },
            'contracts': {
                name: contract_to_dict(contract)
                for name, contract in all_contracts.items()
            }
        }

        if args.stub_report:
            output_data['stub_report'] = cairo_parser.get_stub_report()

        # Add analysis results if available
        if analysis_results:
            output_data['analysis'] = [r.to_dict() for r in analysis_results]
            analyzer = CairoAnalyzer()
            output_data['analysis_summary'] = analyzer.get_summary_stats(analysis_results)

        output = json.dumps(output_data, indent=2)

    elif args.format == 'yaml':
        try:
            import yaml
        except ImportError:
            print("Error: YAML format requires pyyaml: pip install pyyaml", file=sys.stderr)
            return 1

        output_data = {
            'metadata': {
                'total_files': len(cairo_files),
                'total_contracts': len(all_contracts),
                'stubbing_enabled': stub_missing,
            },
            'contracts': {
                name: contract_to_dict(contract)
                for name, contract in all_contracts.items()
            }
        }

        if args.stub_report:
            output_data['stub_report'] = cairo_parser.get_stub_report()

        # Add analysis results if available
        if analysis_results:
            output_data['analysis'] = [r.to_dict() for r in analysis_results]
            analyzer = CairoAnalyzer()
            output_data['analysis_summary'] = analyzer.get_summary_stats(analysis_results)

        output = yaml.dump(output_data, default_flow_style=False, sort_keys=False)

    # Write output
    if args.output:
        Path(args.output).write_text(output)
        if not args.quiet:
            print(f"\nOutput written to {args.output}")
    else:
        print(output)

    return 0


if __name__ == '__main__':
    sys.exit(main())
