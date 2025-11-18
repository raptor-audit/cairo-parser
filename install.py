"""
Installation script for Cairo Parser plugin.

Provides structured Cairo code parsing with stubbing for missing dependencies.
"""

import subprocess
import sys
from pathlib import Path

TOOL_INFO = {
    "name": "cairo-parser",
    "description": "Cairo smart contract parser with assembler-style GOT/PLT symbol resolution (regex-based, no compiler required)",
    "version": "0.1.2",
    "type": "library-cli",
    "provides": ["CairoParser", "ContractInfo", "FunctionInfo", "StorageVarInfo", "EventInfo"],
    "cli_command": "python -m cairo_parser",
    "cli_usage": "python -m cairo_parser <path> [options]",
}

DEPENDENCIES = {
    "required": [],
    "optional": {
        "pyyaml": "YAML output format",
    }
}


def install(install_dir: Path = None) -> bool:
    """
    Install the cairo-parser plugin.

    Args:
        install_dir: Optional directory to install plugin

    Returns:
        True if installation successful
    """
    if install_dir is None:
        install_dir = Path(__file__).parent

    print(f"[cairo-parser] Installing to {install_dir}")

    try:

        # Install optional dependencies
        for package, feature in DEPENDENCIES["optional"].items():
            try:
                subprocess.run(
                    [sys.executable, '-m', 'pip', 'install', package],
                    check=True,
                    capture_output=True
                )
                print(f"[cairo-parser] ✓ Installed {package} ({feature})")
            except subprocess.CalledProcessError:
                print(f"[cairo-parser] ⚠ Optional: {package} ({feature})")

        print(f"[cairo-parser] Installation complete")

        return True

    except Exception as e:
        print(f"[cairo-parser] Installation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def check() -> dict:
    """
    Check installation status.

    Returns:
        Dict mapping component names to installation status
    """
    status = {
        "core": True,  # Always available (pure Python)
        "cairo_lang": False,
        "yaml_support": False,
    }

    # Check cairo-lang support (for Cairo 0 AST parsing)
    try:
        import starkware.cairo.lang.compiler.parser
        status["cairo_lang"] = True
    except ImportError:
        pass

    # Check YAML support
    try:
        import yaml
        status["yaml_support"] = True
    except ImportError:
        pass

    return status


def register_commands(subparsers):
    """
    Register CLI commands with raptor.

    Args:
        subparsers: argparse subparsers object

    Returns:
        Dict mapping command names to handler functions
    """
    # Add 'raptor parse-cairo' command
    parse_parser = subparsers.add_parser(
        'parse-cairo',
        help='Parse Cairo contracts',
        description='Parse Cairo contracts and extract structured information with dependency stubbing'
    )

    parse_parser.add_argument('paths', nargs='+', help='Cairo files or directories')
    parse_parser.add_argument('--format', choices=['json', 'yaml', 'summary'], default='json')
    parse_parser.add_argument('-o', '--output', help='Output file')
    parse_parser.add_argument('--no-stub', action='store_true', help='Fail on missing imports instead of stubbing')
    parse_parser.add_argument('--stub-report', action='store_true', help='Include stub report in output')
    parse_parser.add_argument('--quiet', action='store_true', help='Suppress progress messages')

    def parse_cairo_handler(args):
        """Handle 'raptor parse-cairo' command."""
        # Import and run the CLI module
        plugin_dir = Path(__file__).parent
        sys.path.insert(0, str(plugin_dir))

        try:
            # Load the __main__.py file as a module
            import importlib.util
            main_file = plugin_dir / '__main__.py'

            spec = importlib.util.spec_from_file_location("cairo_parser_main", main_file)
            parser_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(parser_module)

            # Build new argv for the parser
            saved_argv = sys.argv
            sys.argv = ['cairo_parser'] + args.paths

            if args.format != 'json':
                sys.argv.extend(['--format', args.format])
            if args.output:
                sys.argv.extend(['--output', args.output])
            if args.no_stub:
                sys.argv.append('--no-stub')
            if args.stub_report:
                sys.argv.append('--stub-report')
            if args.quiet:
                sys.argv.append('--quiet')

            result = parser_module.main()

            # Restore argv
            sys.argv = saved_argv

            return result
        except Exception as e:
            print(f"Error running Cairo parser: {e}")
            import traceback
            traceback.print_exc()
            return 1

    return {'parse-cairo': parse_cairo_handler}


def uninstall(install_dir: Path) -> bool:
    """Uninstall the plugin."""
    print(f"[cairo-parser] Uninstalling from {install_dir}")
    return True


if __name__ == "__main__":
    # For testing
    print("Cairo Parser Plugin")
    print(f"Version: {TOOL_INFO['version']}")
    print(f"Type: {TOOL_INFO['type']}")
    print()
    print("Checking installation...")
    status = check()
    for component, installed in status.items():
        symbol = "✓" if installed else "✗"
        print(f"  {symbol} {component}")
