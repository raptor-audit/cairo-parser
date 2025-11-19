"""
Main Cairo Analyzer

Orchestrates control flow and dataflow analysis for Cairo contracts.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path

from cairo_parser.parser import ContractInfo, FunctionInfo
from cairo_parser.analysis.statements import StatementParser
from cairo_parser.analysis.cfg import CFGBuilder, ControlFlowGraph
from cairo_parser.analysis.dataflow import DataflowAnalyzer


@dataclass
class FunctionAnalysisResult:
    """Analysis results for a single function."""
    function_name: str
    has_body: bool
    cfg: Optional[Dict[str, Any]] = None
    dataflow: Optional[Dict[str, Any]] = None
    warnings: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            'function_name': self.function_name,
            'has_body': self.has_body,
        }

        if self.cfg:
            result['cfg'] = self.cfg

        if self.dataflow:
            result['dataflow'] = self.dataflow

        if self.warnings:
            result['warnings'] = self.warnings

        if self.errors:
            result['errors'] = self.errors

        return result


@dataclass
class AnalysisResult:
    """Complete analysis results for a contract."""
    contract_name: str
    file_path: str
    functions: List[FunctionAnalysisResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'contract': self.contract_name,
            'file_path': self.file_path,
            'functions': [func.to_dict() for func in self.functions],
        }


class CairoAnalyzer:
    """
    Main analyzer for Cairo contracts.

    Orchestrates statement parsing, CFG building, and dataflow analysis.
    """

    def __init__(self):
        """Initialize the analyzer."""
        self.statement_parser = StatementParser()
        self.cfg_builder = CFGBuilder()

    def analyze_contract(self, contract: ContractInfo) -> AnalysisResult:
        """
        Analyze a Cairo contract.

        Args:
            contract: Parsed contract information

        Returns:
            AnalysisResult containing CFG and dataflow analysis
        """
        result = AnalysisResult(
            contract_name=contract.name,
            file_path=contract.file_path
        )

        # Analyze each function
        for function in contract.functions:
            func_result = self.analyze_function(function)
            result.functions.append(func_result)

        return result

    def analyze_function(self, function: FunctionInfo) -> FunctionAnalysisResult:
        """
        Analyze a single function.

        Args:
            function: Function information

        Returns:
            FunctionAnalysisResult with CFG and dataflow data
        """
        result = FunctionAnalysisResult(
            function_name=function.name,
            has_body=(function.body_text is not None)
        )

        # Skip analysis if no body available
        if not function.body_text:
            result.warnings.append({
                'type': 'no_body',
                'message': f"Function '{function.name}' has no body to analyze"
            })
            return result

        try:
            # Step 1: Parse statements
            statements = self.statement_parser.parse(
                function.body_text,
                start_line=function.body_start_line or function.line
            )

            if not statements:
                result.warnings.append({
                    'type': 'no_statements',
                    'message': f"No statements found in function '{function.name}'"
                })
                return result

            # Step 2: Build CFG
            cfg = self.cfg_builder.build(function.name, statements)
            result.cfg = cfg.to_dict()

            # Step 3: Perform dataflow analysis
            dataflow_analyzer = DataflowAnalyzer(cfg)
            result.dataflow = dataflow_analyzer.analyze_all()

            # Step 4: Find potential issues
            uninitialized_vars = dataflow_analyzer.find_uninitialized_variables()
            unused_defs = dataflow_analyzer.find_unused_definitions()

            result.warnings.extend(uninitialized_vars)
            result.warnings.extend(unused_defs)

        except Exception as e:
            result.errors.append(f"Analysis failed: {str(e)}")

        return result

    def analyze_contracts(self, contracts: Dict[str, ContractInfo]) -> List[AnalysisResult]:
        """
        Analyze multiple contracts.

        Args:
            contracts: Dictionary of contract name to ContractInfo

        Returns:
            List of AnalysisResult objects
        """
        results = []
        for contract in contracts.values():
            # Skip stub contracts
            if contract.contract_type != 'stub':
                result = self.analyze_contract(contract)
                results.append(result)

        return results

    def get_summary_stats(self, results: List[AnalysisResult]) -> Dict[str, Any]:
        """
        Get summary statistics from analysis results.

        Args:
            results: List of analysis results

        Returns:
            Dictionary with summary statistics
        """
        total_contracts = len(results)
        total_functions = sum(len(r.functions) for r in results)
        functions_with_body = sum(
            1 for r in results
            for f in r.functions
            if f.has_body
        )
        total_warnings = sum(
            len(f.warnings) for r in results
            for f in r.functions
        )
        total_errors = sum(
            len(f.errors) for r in results
            for f in r.functions
        )

        # Storage access statistics
        total_storage_reads = 0
        total_storage_writes = 0
        total_external_calls = 0

        for result in results:
            for func in result.functions:
                if func.dataflow:
                    storage_accesses = func.dataflow.get('storage_accesses', [])
                    total_storage_reads += sum(
                        1 for sa in storage_accesses
                        if sa.get('access_type') == 'read'
                    )
                    total_storage_writes += sum(
                        1 for sa in storage_accesses
                        if sa.get('access_type') == 'write'
                    )

                    external_calls = func.dataflow.get('external_calls', [])
                    total_external_calls += len(external_calls)

        return {
            'total_contracts': total_contracts,
            'total_functions': total_functions,
            'functions_with_body': functions_with_body,
            'functions_without_body': total_functions - functions_with_body,
            'total_warnings': total_warnings,
            'total_errors': total_errors,
            'total_storage_reads': total_storage_reads,
            'total_storage_writes': total_storage_writes,
            'total_external_calls': total_external_calls,
        }
