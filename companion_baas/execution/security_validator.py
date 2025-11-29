"""
Security Validator - Validates code safety before execution

Checks for dangerous patterns, imports, and operations.
"""

import re
from typing import List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class SecurityIssue:
    """Represents a security issue found in code"""
    severity: str  # 'critical', 'high', 'medium', 'low'
    message: str
    line_number: Optional[int] = None
    pattern: Optional[str] = None


class SecurityValidator:
    """Validates code for security issues before execution"""
    
    # Dangerous imports that should be blocked
    DANGEROUS_IMPORTS = {
        'os': 'File system access',
        'sys': 'System manipulation',
        'subprocess': 'Command execution',
        'eval': 'Dynamic code execution',
        'exec': 'Dynamic code execution',
        'compile': 'Dynamic code compilation',
        '__import__': 'Dynamic imports',
        'importlib': 'Dynamic imports',
        'pickle': 'Arbitrary code execution',
        'marshal': 'Arbitrary code execution',
        'shelve': 'File system access',
        'shutil': 'File operations',
        'tempfile': 'File system access',
        'socket': 'Network access',
        'urllib': 'Network access',
        'requests': 'Network access',
        'http': 'Network access',
        'ftplib': 'Network access',
        'telnetlib': 'Network access',
        'ctypes': 'System calls',
        'threading': 'Thread manipulation',
        'multiprocessing': 'Process manipulation',
    }
    
    # Dangerous function patterns
    DANGEROUS_PATTERNS = [
        (r'\beval\s*\(', 'Use of eval() function', 'critical'),
        (r'\bexec\s*\(', 'Use of exec() function', 'critical'),
        (r'\b__import__\s*\(', 'Dynamic import', 'critical'),
        (r'\bcompile\s*\(', 'Dynamic compilation', 'high'),
        (r'\bopen\s*\(', 'File access', 'high'),
        (r'\bfile\s*\(', 'File access', 'high'),
        (r'__(?:class|bases|subclasses|globals|locals)__', 'Introspection access', 'high'),
        (r'\bdelattr\s*\(', 'Attribute deletion', 'medium'),
        (r'\bsetattr\s*\(', 'Attribute modification', 'medium'),
        (r'\bgetattr\s*\(', 'Attribute access', 'low'),
        (r'\bvars\s*\(', 'Variable access', 'low'),
        (r'\bdir\s*\(', 'Directory listing', 'low'),
        (r'while\s+True\s*:', 'Potential infinite loop', 'medium'),
        (r'for\s+\w+\s+in\s+range\s*\(\s*\d{7,}', 'Large iteration', 'medium'),
    ]
    
    # Safe imports that are allowed
    SAFE_IMPORTS = {
        'math', 'random', 'datetime', 'time', 'json', 'collections',
        'itertools', 'functools', 'operator', 'string', 're',
        'decimal', 'fractions', 'statistics', 'copy', 'dataclasses',
        'typing', 'enum', 'abc', 'contextlib', 'heapq', 'bisect',
        'array', 'cmath', 'numbers', 'unicodedata',
    }
    
    def __init__(self, allow_imports: Optional[List[str]] = None):
        """
        Initialize security validator
        
        Args:
            allow_imports: Additional imports to allow (whitelist)
        """
        self.allow_imports = set(allow_imports or [])
        self.allowed_imports = self.SAFE_IMPORTS | self.allow_imports
    
    def validate_code(self, code: str, language: str = 'python') -> Tuple[bool, List[SecurityIssue]]:
        """
        Validate code for security issues
        
        Args:
            code: Code to validate
            language: Programming language ('python', 'javascript', etc.)
        
        Returns:
            (is_safe, issues) tuple
        """
        issues = []
        
        if language == 'python':
            issues.extend(self._check_python_imports(code))
            issues.extend(self._check_dangerous_patterns(code))
            issues.extend(self._check_code_complexity(code))
        elif language == 'javascript':
            issues.extend(self._check_javascript_patterns(code))
        
        # Check if any critical issues exist
        has_critical = any(issue.severity == 'critical' for issue in issues)
        
        return (not has_critical, issues)
    
    def _check_python_imports(self, code: str) -> List[SecurityIssue]:
        """Check for dangerous Python imports"""
        issues = []
        
        # Find all import statements
        import_pattern = r'^\s*(?:from\s+(\S+)\s+)?import\s+(.+)$'
        
        for line_num, line in enumerate(code.split('\n'), 1):
            match = re.search(import_pattern, line, re.MULTILINE)
            if match:
                module = match.group(1) or match.group(2).split()[0].split('.')[0]
                module = module.strip()
                
                # Check if module is dangerous
                if module in self.DANGEROUS_IMPORTS:
                    issues.append(SecurityIssue(
                        severity='critical',
                        message=f"Dangerous import '{module}': {self.DANGEROUS_IMPORTS[module]}",
                        line_number=line_num,
                        pattern=line.strip()
                    ))
                
                # Check if module is explicitly allowed
                elif module not in self.allowed_imports and module not in self.SAFE_IMPORTS:
                    issues.append(SecurityIssue(
                        severity='medium',
                        message=f"Unknown import '{module}' - not in whitelist",
                        line_number=line_num,
                        pattern=line.strip()
                    ))
        
        return issues
    
    def _check_dangerous_patterns(self, code: str) -> List[SecurityIssue]:
        """Check for dangerous code patterns"""
        issues = []
        
        for pattern, message, severity in self.DANGEROUS_PATTERNS:
            for line_num, line in enumerate(code.split('\n'), 1):
                if re.search(pattern, line):
                    issues.append(SecurityIssue(
                        severity=severity,
                        message=message,
                        line_number=line_num,
                        pattern=line.strip()
                    ))
        
        return issues
    
    def _check_code_complexity(self, code: str) -> List[SecurityIssue]:
        """Check for potentially problematic code complexity"""
        issues = []
        lines = code.split('\n')
        
        # Check for very long code
        if len(lines) > 500:
            issues.append(SecurityIssue(
                severity='medium',
                message=f"Code is very long ({len(lines)} lines) - may be resource intensive",
            ))
        
        # Check for deeply nested code
        max_indent = 0
        for line in lines:
            if line.strip():
                indent = len(line) - len(line.lstrip())
                max_indent = max(max_indent, indent // 4)
        
        if max_indent > 8:
            issues.append(SecurityIssue(
                severity='low',
                message=f"Code has deep nesting ({max_indent} levels) - may be complex",
            ))
        
        return issues
    
    def _check_javascript_patterns(self, code: str) -> List[SecurityIssue]:
        """Check for dangerous JavaScript patterns"""
        issues = []
        
        dangerous_js = [
            (r'\beval\s*\(', 'Use of eval()', 'critical'),
            (r'\bFunction\s*\(', 'Dynamic function creation', 'critical'),
            (r'\brequire\s*\(\s*["\']fs["\']', 'File system access', 'high'),
            (r'\brequire\s*\(\s*["\']child_process["\']', 'Process execution', 'critical'),
            (r'\bprocess\.exit', 'Process termination', 'high'),
            (r'while\s*\(\s*true\s*\)', 'Potential infinite loop', 'medium'),
        ]
        
        for pattern, message, severity in dangerous_js:
            for line_num, line in enumerate(code.split('\n'), 1):
                if re.search(pattern, line):
                    issues.append(SecurityIssue(
                        severity=severity,
                        message=message,
                        line_number=line_num,
                        pattern=line.strip()
                    ))
        
        return issues
    
    def get_safe_builtins(self) -> dict:
        """Get dictionary of safe built-in functions for Python execution"""
        import builtins
        
        # Only allow safe built-in functions
        safe_builtins = {
            # Type constructors
            'int': int,
            'float': float,
            'str': str,
            'bool': bool,
            'list': list,
            'dict': dict,
            'tuple': tuple,
            'set': set,
            'frozenset': frozenset,
            
            # Utility functions
            'abs': abs,
            'min': min,
            'max': max,
            'sum': sum,
            'len': len,
            'range': range,
            'enumerate': enumerate,
            'zip': zip,
            'map': map,
            'filter': filter,
            'sorted': sorted,
            'reversed': reversed,
            'any': any,
            'all': all,
            'round': round,
            'pow': pow,
            'divmod': divmod,
            
            # Type checking
            'isinstance': isinstance,
            'issubclass': issubclass,
            'type': type,
            'hasattr': hasattr,
            
            # Output
            'print': print,
            
            # String/bytes
            'ord': ord,
            'chr': chr,
            'hex': hex,
            'oct': oct,
            'bin': bin,
            
            # Constants
            'True': True,
            'False': False,
            'None': None,
            
            # Safe import mechanism
            '__import__': self._create_safe_import(),
        }
        
        return safe_builtins
    
    def _create_safe_import(self):
        """Create a safe __import__ function that only allows whitelisted modules"""
        def safe_import(name, *args, **kwargs):
            if name in self.allowed_imports:
                return __import__(name, *args, **kwargs)
            else:
                raise ImportError(f"Import of '{name}' is not allowed. Allowed imports: {', '.join(sorted(self.allowed_imports))}")
        
        return safe_import


# Example usage
if __name__ == "__main__":
    validator = SecurityValidator()
    
    # Test safe code
    safe_code = """
import math

def calculate_circle_area(radius):
    return math.pi * radius ** 2

print(calculate_circle_area(5))
"""
    
    is_safe, issues = validator.validate_code(safe_code)
    print(f"Safe code test: {'PASS' if is_safe else 'FAIL'}")
    print(f"Issues: {len(issues)}")
    
    # Test dangerous code
    dangerous_code = """
import os
import subprocess

subprocess.run(['rm', '-rf', '/'])
eval('__import__("os").system("ls")')
"""
    
    is_safe, issues = validator.validate_code(dangerous_code)
    print(f"\nDangerous code test: {'FAIL' if not is_safe else 'PASS'}")
    print(f"Issues found: {len(issues)}")
    for issue in issues:
        print(f"  [{issue.severity.upper()}] Line {issue.line_number}: {issue.message}")
