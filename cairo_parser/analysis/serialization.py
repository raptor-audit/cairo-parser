"""
Serialization Support for Analysis Results

Converts analysis results to JSON and YAML formats for output.
"""

import json
from typing import Any, Dict, List
from pathlib import Path

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


def serialize_to_json(data: Any, pretty: bool = True) -> str:
    """
    Serialize data to JSON string.

    Args:
        data: Data to serialize (should have to_dict() method or be dict)
        pretty: Whether to pretty-print the JSON

    Returns:
        JSON string
    """
    # Convert to dict if it has a to_dict method
    if hasattr(data, 'to_dict'):
        data = data.to_dict()
    elif isinstance(data, list):
        data = [item.to_dict() if hasattr(item, 'to_dict') else item for item in data]

    if pretty:
        return json.dumps(data, indent=2, sort_keys=False)
    else:
        return json.dumps(data)


def serialize_to_yaml(data: Any) -> str:
    """
    Serialize data to YAML string.

    Args:
        data: Data to serialize (should have to_dict() method or be dict)

    Returns:
        YAML string

    Raises:
        ImportError: If PyYAML is not installed
    """
    if not YAML_AVAILABLE:
        raise ImportError(
            "PyYAML is not installed. Install it with: pip install pyyaml"
        )

    # Convert to dict if it has a to_dict method
    if hasattr(data, 'to_dict'):
        data = data.to_dict()
    elif isinstance(data, list):
        data = [item.to_dict() if hasattr(item, 'to_dict') else item for item in data]

    return yaml.dump(data, default_flow_style=False, sort_keys=False)


def save_analysis_json(data: Any, output_path: Path, pretty: bool = True) -> None:
    """
    Save analysis results to JSON file.

    Args:
        data: Analysis results to save
        output_path: Path to output file
        pretty: Whether to pretty-print
    """
    json_str = serialize_to_json(data, pretty=pretty)
    output_path.write_text(json_str)


def save_analysis_yaml(data: Any, output_path: Path) -> None:
    """
    Save analysis results to YAML file.

    Args:
        data: Analysis results to save
        output_path: Path to output file

    Raises:
        ImportError: If PyYAML is not installed
    """
    yaml_str = serialize_to_yaml(data)
    output_path.write_text(yaml_str)


def save_analysis(
    data: Any,
    output_path: Path,
    format: str = 'json',
    pretty: bool = True
) -> None:
    """
    Save analysis results in the specified format.

    Args:
        data: Analysis results to save
        output_path: Path to output file
        format: Output format ('json' or 'yaml')
        pretty: Whether to pretty-print (JSON only)

    Raises:
        ValueError: If format is not supported
        ImportError: If YAML format requested but PyYAML not installed
    """
    format = format.lower()

    if format == 'json':
        save_analysis_json(data, output_path, pretty=pretty)
    elif format == 'yaml' or format == 'yml':
        save_analysis_yaml(data, output_path)
    else:
        raise ValueError(f"Unsupported format: {format}. Use 'json' or 'yaml'")


def format_summary_text(summary: Dict[str, Any]) -> str:
    """
    Format summary statistics as human-readable text.

    Args:
        summary: Summary statistics dictionary

    Returns:
        Formatted text string
    """
    lines = [
        "=" * 60,
        "Cairo Contract Analysis Summary",
        "=" * 60,
        "",
        f"Contracts analyzed: {summary.get('total_contracts', 0)}",
        f"Total functions: {summary.get('total_functions', 0)}",
        f"  - With body: {summary.get('functions_with_body', 0)}",
        f"  - Without body: {summary.get('functions_without_body', 0)}",
        "",
        "Analysis Results:",
        f"  - Total warnings: {summary.get('total_warnings', 0)}",
        f"  - Total errors: {summary.get('total_errors', 0)}",
        "",
        "Storage Access:",
        f"  - Storage reads: {summary.get('total_storage_reads', 0)}",
        f"  - Storage writes: {summary.get('total_storage_writes', 0)}",
        "",
        "External Calls:",
        f"  - Total external calls: {summary.get('total_external_calls', 0)}",
        "=" * 60,
    ]

    return '\n'.join(lines)


def format_warnings_text(results: List[Dict[str, Any]]) -> str:
    """
    Format warnings as human-readable text.

    Args:
        results: List of analysis results

    Returns:
        Formatted warning text
    """
    lines = []

    for result in results:
        contract_name = result.get('contract', 'Unknown')
        functions = result.get('functions', [])

        for func in functions:
            func_name = func.get('function_name', 'unknown')
            warnings = func.get('warnings', [])

            if warnings:
                lines.append(f"\n{contract_name}::{func_name}:")
                for warning in warnings:
                    warn_type = warning.get('type', 'unknown')
                    message = warning.get('message', '')
                    line_num = warning.get('line', '')

                    if line_num:
                        lines.append(f"  Line {line_num}: [{warn_type}] {message}")
                    else:
                        lines.append(f"  [{warn_type}] {message}")

    if not lines:
        return "No warnings found."

    return '\n'.join(lines)
