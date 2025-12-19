#!/usr/bin/env python3
"""
Code Analyzer - Autonomous Code Analysis and Optimization
=========================================================

Analyzes code for:
- Performance bottlenecks
- Code quality issues
- Security vulnerabilities
- Optimization opportunities
- Best practice violations
- Complexity analysis
"""

import logging
import ast
import re
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import time

logger = logging.getLogger(__name__)


@dataclass
class CodeIssue:
    """Represents a code issue found during analysis"""
    file_path: str
    line_number: int
    column: int
    issue_type: str
    severity: str  # 'low', 'medium', 'high', 'critical'
    message: str
    suggestion: str
    code_snippet: str = ""
    confidence: float = 1.0


@dataclass
class AnalysisResult:
    """Result of code analysis"""
    file_path: str
    issues: List[CodeIssue] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    suggestions: List[str] = field(default_factory=list)
    analysis_time: float = 0.0


class CodeAnalyzer:
    """
    Autonomous code analyzer that examines code for quality, performance,
    and optimization opportunities.
    """

    def __init__(self, file_controller=None):
        self.file_controller = file_controller
        self.supported_languages = {'python', 'javascript', 'typescript', 'java', 'cpp', 'c'}

        # Analysis patterns
        self.performance_patterns = self._load_performance_patterns()
        self.security_patterns = self._load_security_patterns()
        self.quality_patterns = self._load_quality_patterns()

        logger.info("🔍 Code Analyzer initialized")

    def analyze_file(self, path: str) -> AnalysisResult:
        """
        Analyze a single file for issues and optimization opportunities

        Args:
            path: Path to the file to analyze

        Returns:
            AnalysisResult with issues, metrics, and suggestions
        """
        start_time = time.time()
        result = AnalysisResult(file_path=path)

        try:
            file_path = Path(path)
            if not file_path.exists():
                result.issues.append(CodeIssue(
                    file_path=path,
                    line_number=0,
                    column=0,
                    issue_type="file_not_found",
                    severity="high",
                    message=f"File does not exist: {path}",
                    suggestion="Check file path and permissions"
                ))
                return result

            # Read file content
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            lines = content.split('\n')

            # Determine language
            language = self._detect_language(path, content)
            result.metrics['language'] = language

            # Basic metrics
            result.metrics.update(self._calculate_basic_metrics(content, lines))

            # Language-specific analysis
            if language == 'python':
                issues = self._analyze_python(content, lines, path)
            elif language in ['javascript', 'typescript']:
                issues = self._analyze_javascript(content, lines, path)
            else:
                issues = self._analyze_generic(content, lines, path)

            result.issues.extend(issues)

            # Generate suggestions
            result.suggestions = self._generate_suggestions(result.issues, result.metrics)

        except Exception as e:
            logger.error(f"Analysis failed for {path}: {e}")
            result.issues.append(CodeIssue(
                file_path=path,
                line_number=0,
                column=0,
                issue_type="analysis_error",
                severity="medium",
                message=f"Analysis failed: {str(e)}",
                suggestion="Check file format and try again"
            ))

        result.analysis_time = time.time() - start_time
        return result

    def find_optimization_opportunities(self, analysis_results: List[AnalysisResult]) -> List[Dict[str, Any]]:
        """
        Find optimization opportunities across multiple files

        Args:
            analysis_results: List of analysis results

        Returns:
            List of optimization opportunities
        """
        opportunities = []

        # Aggregate metrics across files
        total_lines = sum(r.metrics.get('lines', 0) for r in analysis_results)
        total_complexity = sum(r.metrics.get('complexity', 0) for r in analysis_results)
        total_issues = sum(len(r.issues) for r in analysis_results)

        # Code duplication analysis
        duplication_opportunities = self._analyze_code_duplication(analysis_results)
        opportunities.extend(duplication_opportunities)

        # Performance optimization opportunities
        perf_opportunities = self._analyze_performance_opportunities(analysis_results)
        opportunities.extend(perf_opportunities)

        # Architecture improvement opportunities
        arch_opportunities = self._analyze_architecture_opportunities(analysis_results)
        opportunities.extend(arch_opportunities)

        return opportunities

    def _detect_language(self, path: str, content: str) -> str:
        """Detect programming language from file path and content"""
        path_lower = path.lower()

        # Check file extension
        if path_lower.endswith(('.py', '.pyw')):
            return 'python'
        elif path_lower.endswith(('.js', '.mjs')):
            return 'javascript'
        elif path_lower.endswith(('.ts', '.tsx')):
            return 'typescript'
        elif path_lower.endswith(('.java', '.scala')):
            return 'java'
        elif path_lower.endswith(('.cpp', '.cc', '.cxx', '.c++', '.hpp')):
            return 'cpp'
        elif path_lower.endswith(('.c', '.h')):
            return 'c'

        # Check content patterns
        if re.search(r'^\s*(import|from)\s+\w+', content, re.MULTILINE):
            return 'python'
        elif re.search(r'^\s*(function|const|let|var)\s+', content, re.MULTILINE):
            return 'javascript'
        elif re.search(r'^\s*(public|private|class)\s+', content, re.MULTILINE):
            return 'java'

        return 'unknown'

    def _calculate_basic_metrics(self, content: str, lines: List[str]) -> Dict[str, Any]:
        """Calculate basic code metrics"""
        metrics = {
            'lines': len(lines),
            'characters': len(content),
            'non_empty_lines': sum(1 for line in lines if line.strip()),
            'average_line_length': sum(len(line) for line in lines) / len(lines) if lines else 0,
        }

        # Calculate complexity (simplified)
        complexity = 0
        for line in lines:
            stripped = line.strip()
            if any(keyword in stripped for keyword in ['if ', 'for ', 'while ', 'def ', 'function ', 'class ']):
                complexity += 1
            if ' and ' in stripped or ' or ' in stripped or '&&' in stripped or '||' in stripped:
                complexity += 0.5

        metrics['complexity'] = complexity
        return metrics

    def _analyze_python(self, content: str, lines: List[str], path: str) -> List[CodeIssue]:
        """Analyze Python code specifically"""
        issues = []

        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            issues.append(CodeIssue(
                file_path=path,
                line_number=e.lineno or 0,
                column=e.offset or 0,
                issue_type="syntax_error",
                severity="critical",
                message=f"Syntax error: {e.msg}",
                suggestion="Fix the syntax error"
            ))
            return issues

        # Analyze AST for Python-specific issues
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Check function complexity
                complexity = self._calculate_function_complexity(node)
                if complexity > 10:
                    issues.append(CodeIssue(
                        file_path=path,
                        line_number=node.lineno,
                        column=node.col_offset,
                        issue_type="high_complexity",
                        severity="medium",
                        message=f"Function '{node.name}' has high complexity ({complexity})",
                        suggestion="Break down into smaller functions"
                    ))

                # Check function length
                if len(node.body) > 50:
                    issues.append(CodeIssue(
                        file_path=path,
                        line_number=node.lineno,
                        column=node.col_offset,
                        issue_type="long_function",
                        severity="low",
                        message=f"Function '{node.name}' is very long ({len(node.body)} lines)",
                        suggestion="Consider splitting into smaller functions"
                    ))

            elif isinstance(node, ast.Import):
                # Check for unused imports (simplified)
                pass

        # Pattern-based analysis
        for i, line in enumerate(lines, 1):
            # Check for performance issues
            if 'print(' in line and not line.strip().startswith('#'):
                issues.append(CodeIssue(
                    file_path=path,
                    line_number=i,
                    column=0,
                    issue_type="debug_code",
                    severity="low",
                    message="Debug print statement found",
                    suggestion="Remove debug prints or use logging",
                    code_snippet=line.strip()
                ))

            # Check for inefficient patterns
            if re.search(r'for\s+\w+\s+in\s+range\(len\(', line):
                issues.append(CodeIssue(
                    file_path=path,
                    line_number=i,
                    column=0,
                    issue_type="inefficient_loop",
                    severity="medium",
                    message="Inefficient loop pattern: for i in range(len(list))",
                    suggestion="Use enumerate() or direct iteration",
                    code_snippet=line.strip()
                ))

        return issues

    def _analyze_javascript(self, content: str, lines: List[str], path: str) -> List[CodeIssue]:
        """Analyze JavaScript/TypeScript code"""
        issues = []

        for i, line in enumerate(lines, 1):
            # Check for console.log in production code
            if 'console.log(' in line and not line.strip().startswith('//'):
                issues.append(CodeIssue(
                    file_path=path,
                    line_number=i,
                    column=0,
                    issue_type="debug_code",
                    severity="low",
                    message="Console.log found in code",
                    suggestion="Use proper logging or remove debug statements",
                    code_snippet=line.strip()
                ))

            # Check for var usage (prefer let/const)
            if re.search(r'\bvar\s+', line) and not line.strip().startswith('//'):
                issues.append(CodeIssue(
                    file_path=path,
                    line_number=i,
                    column=0,
                    issue_type="outdated_syntax",
                    severity="low",
                    message="Using 'var' instead of 'let' or 'const'",
                    suggestion="Use 'let' or 'const' for better scoping",
                    code_snippet=line.strip()
                ))

        return issues

    def _analyze_generic(self, content: str, lines: List[str], path: str) -> List[CodeIssue]:
        """Generic analysis for unsupported languages"""
        issues = []

        for i, line in enumerate(lines, 1):
            # Check for TODO comments
            if 'TODO' in line.upper():
                issues.append(CodeIssue(
                    file_path=path,
                    line_number=i,
                    column=0,
                    issue_type="todo_comment",
                    severity="low",
                    message="TODO comment found",
                    suggestion="Address the TODO or remove if no longer needed",
                    code_snippet=line.strip()
                ))

            # Check for long lines
            if len(line) > 120:
                issues.append(CodeIssue(
                    file_path=path,
                    line_number=i,
                    column=0,
                    issue_type="long_line",
                    severity="low",
                    message=f"Line too long ({len(line)} characters)",
                    suggestion="Break line into multiple lines for readability",
                    code_snippet=line.strip()[:50] + "..."
                ))

        return issues

    def _calculate_function_complexity(self, node: ast.FunctionDef) -> int:
        """Calculate cyclomatic complexity of a function"""
        complexity = 1  # Base complexity

        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.With)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1

        return complexity

    def _generate_suggestions(self, issues: List[CodeIssue], metrics: Dict[str, Any]) -> List[str]:
        """Generate improvement suggestions based on analysis"""
        suggestions = []

        # Group issues by type
        issue_counts = {}
        for issue in issues:
            issue_counts[issue.issue_type] = issue_counts.get(issue.issue_type, 0) + 1

        # Generate suggestions based on issue patterns
        if issue_counts.get('high_complexity', 0) > 0:
            suggestions.append("Refactor high-complexity functions into smaller, more focused functions")

        if issue_counts.get('long_function', 0) > 0:
            suggestions.append("Break down long functions into smaller, single-responsibility functions")

        if issue_counts.get('debug_code', 0) > 0:
            suggestions.append("Remove debug statements and implement proper logging")

        if metrics.get('complexity', 0) > 20:
            suggestions.append("Consider breaking this file into multiple modules")

        if metrics.get('lines', 0) > 1000:
            suggestions.append("This file is very large - consider splitting into multiple files")

        return suggestions

    def _analyze_code_duplication(self, results: List[AnalysisResult]) -> List[Dict[str, Any]]:
        """Analyze code duplication across files"""
        # Simplified duplication analysis
        opportunities = []

        # Look for files with similar names that might be duplicated
        file_names = [Path(r.file_path).name for r in results]
        name_counts = {}

        for name in file_names:
            base_name = re.sub(r'[0-9]+', '', name)  # Remove numbers
            name_counts[base_name] = name_counts.get(base_name, 0) + 1

        for name, count in name_counts.items():
            if count > 2:
                opportunities.append({
                    'type': 'code_duplication',
                    'description': f'Potential code duplication: {count} files with similar names ({name})',
                    'impact': 'high',
                    'effort': 'medium',
                    'suggestion': 'Extract common functionality into shared modules'
                })

        return opportunities

    def _analyze_performance_opportunities(self, results: List[AnalysisResult]) -> List[Dict[str, Any]]:
        """Analyze performance optimization opportunities"""
        opportunities = []

        for result in results:
            issues = result.issues
            perf_issues = [i for i in issues if 'performance' in i.issue_type.lower() or 'inefficient' in i.issue_type.lower()]

            if len(perf_issues) > 2:
                opportunities.append({
                    'type': 'performance_optimization',
                    'file': result.file_path,
                    'description': f'{len(perf_issues)} performance issues in {Path(result.file_path).name}',
                    'impact': 'high',
                    'effort': 'medium',
                    'suggestion': 'Address performance bottlenecks and inefficient algorithms'
                })

        return opportunities

    def _analyze_architecture_opportunities(self, results: List[AnalysisResult]) -> List[Dict[str, Any]]:
        """Analyze architecture improvement opportunities"""
        opportunities = []

        # Check for high coupling (many imports from same module)
        # This is a simplified analysis
        total_issues = sum(len(r.issues) for r in results)
        avg_issues_per_file = total_issues / len(results) if results else 0

        if avg_issues_per_file > 5:
            opportunities.append({
                'type': 'code_quality',
                'description': f'High average issues per file ({avg_issues_per_file:.1f})',
                'impact': 'medium',
                'effort': 'high',
                'suggestion': 'Implement code quality standards and automated checks'
            })

        return opportunities

    def _load_performance_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Load performance analysis patterns"""
        return {
            'nested_loops': {
                'pattern': r'for\s+.*:\s*\n\s*for\s+.*:',
                'message': 'Nested loops detected - consider optimization',
                'severity': 'medium'
            },
            'string_concatenation': {
                'pattern': r'(\w+)\s*\+=\s*".*"\s*\+=\s*".*"',
                'message': 'Inefficient string concatenation in loop',
                'severity': 'high'
            }
        }

    def _load_security_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Load security analysis patterns"""
        return {
            'sql_injection': {
                'pattern': r'execute\([^)]*\+.*\)',
                'message': 'Potential SQL injection vulnerability',
                'severity': 'critical'
            },
            'hardcoded_password': {
                'pattern': r'password\s*=\s*["\'][^"\']*["\']',
                'message': 'Hardcoded password detected',
                'severity': 'high'
            }
        }

    def _load_quality_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Load code quality patterns"""
        return {
            'magic_number': {
                'pattern': r'\b\d{2,}\b',
                'message': 'Magic number detected - consider using named constants',
                'severity': 'low'
            },
            'long_line': {
                'pattern': r'^.{120,}$',
                'message': 'Line exceeds 120 characters',
                'severity': 'low'
            }
        }
