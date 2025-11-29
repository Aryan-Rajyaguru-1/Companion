"""
Code Executor - Main execution engine for multiple languages

Unified interface for executing code in different programming languages.
"""

from typing import Optional, Dict, Any, Union
from dataclasses import dataclass
import time

from .python_sandbox import PythonSandbox, ExecutionResult
from .javascript_executor import JavaScriptExecutor, JSExecutionResult
from .security_validator import SecurityValidator


@dataclass
class UnifiedExecutionResult:
    """Unified result across all executors"""
    success: bool
    output: str
    error: Optional[str] = None
    execution_time: float = 0.0
    return_value: Any = None
    language: str = "unknown"


class CodeExecutor:
    """
    Multi-language code executor
    
    Supports:
    - Python (via PythonSandbox)
    - JavaScript/Node.js (via JavaScriptExecutor)
    - More languages can be added
    
    Features:
    - Automatic language detection
    - Unified result format
    - Security validation
    - Timeout protection
    """
    
    SUPPORTED_LANGUAGES = ['python', 'javascript', 'js', 'node']
    
    def __init__(
        self,
        timeout: int = 5,
        max_output_size: int = 10000,
        allowed_imports: Optional[list] = None
    ):
        """
        Initialize code executor
        
        Args:
            timeout: Maximum execution time in seconds
            max_output_size: Maximum output size in characters
            allowed_imports: Additional Python imports to allow
        """
        self.timeout = timeout
        self.max_output_size = max_output_size
        
        # Initialize executors
        self.python_executor = PythonSandbox(
            timeout=timeout,
            max_output_size=max_output_size,
            allowed_imports=allowed_imports
        )
        
        self.javascript_executor = JavaScriptExecutor(
            timeout=timeout,
            max_output_size=max_output_size
        )
        
        self.validator = SecurityValidator(allow_imports=allowed_imports)
    
    def detect_language(self, code: str) -> str:
        """
        Detect programming language from code
        
        Args:
            code: Source code
        
        Returns:
            Detected language ('python', 'javascript', or 'unknown')
        """
        code_lower = code.lower().strip()
        
        # JavaScript indicators
        js_indicators = [
            'console.log',
            'const ',
            'let ',
            'var ',
            'function ',
            '=>',
            'require(',
            'module.exports',
            'export default',
        ]
        
        # Python indicators
        python_indicators = [
            'def ',
            'import ',
            'from ',
            'print(',
            '__name__',
            '__main__',
            'if __name__',
            'self.',
            'class ',
        ]
        
        js_score = sum(1 for indicator in js_indicators if indicator in code_lower)
        python_score = sum(1 for indicator in python_indicators if indicator in code_lower)
        
        if python_score > js_score:
            return 'python'
        elif js_score > python_score:
            return 'javascript'
        else:
            # Default to Python if unclear
            return 'python'
    
    def execute(
        self,
        code: str,
        language: Optional[str] = None,
        **kwargs
    ) -> UnifiedExecutionResult:
        """
        Execute code in specified or auto-detected language
        
        Args:
            code: Source code to execute
            language: Programming language ('python', 'javascript', etc.)
                     If None, will auto-detect
            **kwargs: Additional arguments for specific executors
        
        Returns:
            UnifiedExecutionResult with execution output
        """
        # Auto-detect language if not specified
        if language is None:
            language = self.detect_language(code)
        
        language = language.lower()
        
        # Validate language is supported
        if language not in self.SUPPORTED_LANGUAGES:
            return UnifiedExecutionResult(
                success=False,
                output="",
                error=f"Unsupported language: {language}. Supported: {', '.join(self.SUPPORTED_LANGUAGES)}",
                language=language
            )
        
        # Execute based on language
        start_time = time.time()
        
        try:
            if language == 'python':
                result = self.python_executor.execute(code, **kwargs)
                return self._convert_python_result(result)
            
            elif language in ['javascript', 'js', 'node']:
                result = self.javascript_executor.execute(code, **kwargs)
                return self._convert_js_result(result)
            
            else:
                return UnifiedExecutionResult(
                    success=False,
                    output="",
                    error=f"Language '{language}' not yet implemented",
                    language=language
                )
                
        except Exception as e:
            execution_time = time.time() - start_time
            return UnifiedExecutionResult(
                success=False,
                output="",
                error=f"Execution error: {str(e)}",
                execution_time=execution_time,
                language=language
            )
    
    def execute_python(self, code: str, **kwargs) -> UnifiedExecutionResult:
        """Execute Python code directly"""
        result = self.python_executor.execute(code, **kwargs)
        return self._convert_python_result(result)
    
    def execute_javascript(self, code: str, **kwargs) -> UnifiedExecutionResult:
        """Execute JavaScript code directly"""
        result = self.javascript_executor.execute(code, **kwargs)
        return self._convert_js_result(result)
    
    def evaluate_expression(
        self,
        expression: str,
        language: str = 'python'
    ) -> UnifiedExecutionResult:
        """
        Evaluate an expression
        
        Args:
            expression: Expression to evaluate
            language: Programming language
        
        Returns:
            UnifiedExecutionResult with expression value
        """
        language = language.lower()
        
        if language == 'python':
            result = self.python_executor.evaluate_expression(expression)
            return self._convert_python_result(result)
        
        elif language in ['javascript', 'js', 'node']:
            result = self.javascript_executor.evaluate_expression(expression)
            return self._convert_js_result(result)
        
        else:
            return UnifiedExecutionResult(
                success=False,
                output="",
                error=f"Unsupported language: {language}",
                language=language
            )
    
    def _convert_python_result(self, result: ExecutionResult) -> UnifiedExecutionResult:
        """Convert Python execution result to unified format"""
        return UnifiedExecutionResult(
            success=result.success,
            output=result.output,
            error=result.error,
            execution_time=result.execution_time,
            return_value=result.return_value,
            language='python'
        )
    
    def _convert_js_result(self, result: JSExecutionResult) -> UnifiedExecutionResult:
        """Convert JavaScript execution result to unified format"""
        return UnifiedExecutionResult(
            success=result.success,
            output=result.output,
            error=result.error,
            execution_time=result.execution_time,
            return_value=result.return_value,
            language='javascript'
        )
    
    def validate_code(self, code: str, language: str) -> tuple[bool, list]:
        """
        Validate code for security issues
        
        Args:
            code: Source code
            language: Programming language
        
        Returns:
            (is_safe, issues) tuple
        """
        return self.validator.validate_code(code, language)
    
    def get_supported_languages(self) -> list:
        """Get list of supported programming languages"""
        return self.SUPPORTED_LANGUAGES.copy()


# Example usage and tests
if __name__ == "__main__":
    print("=" * 60)
    print("CODE EXECUTOR - Multi-Language Execution Engine")
    print("=" * 60)
    
    executor = CodeExecutor(timeout=5)
    
    # Test 1: Auto-detect Python
    print("\n" + "=" * 60)
    print("Test 1: Auto-detect Python")
    print("=" * 60)
    python_code = """
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)

for i in range(1, 6):
    print(f"factorial({i}) = {factorial(i)}")
"""
    result1 = executor.execute(python_code)
    print(f"Language: {result1.language}")
    print(f"Success: {result1.success}")
    print(f"Output:\n{result1.output}")
    print(f"Time: {result1.execution_time:.4f}s")
    
    # Test 2: Auto-detect JavaScript
    print("\n" + "=" * 60)
    print("Test 2: Auto-detect JavaScript")
    print("=" * 60)
    js_code = """
const factorial = (n) => {
    if (n <= 1) return 1;
    return n * factorial(n - 1);
};

for (let i = 1; i <= 5; i++) {
    console.log(`factorial(${i}) = ${factorial(i)}`);
}
"""
    result2 = executor.execute(js_code)
    print(f"Language: {result2.language}")
    print(f"Success: {result2.success}")
    print(f"Output:\n{result2.output}")
    print(f"Time: {result2.execution_time:.4f}s")
    
    # Test 3: Python expression evaluation
    print("\n" + "=" * 60)
    print("Test 3: Python Expression Evaluation")
    print("=" * 60)
    result3 = executor.evaluate_expression("sum([i**2 for i in range(10)])", language='python')
    print(f"Success: {result3.success}")
    print(f"Result: {result3.return_value}")
    print(f"Time: {result3.execution_time:.4f}s")
    
    # Test 4: JavaScript expression evaluation
    print("\n" + "=" * 60)
    print("Test 4: JavaScript Expression Evaluation")
    print("=" * 60)
    result4 = executor.evaluate_expression("[1, 2, 3, 4, 5].reduce((a, b) => a + b)", language='javascript')
    print(f"Success: {result4.success}")
    print(f"Result: {result4.output.strip()}")
    print(f"Time: {result4.execution_time:.4f}s")
    
    # Test 5: Security validation
    print("\n" + "=" * 60)
    print("Test 5: Security Validation (Dangerous Code)")
    print("=" * 60)
    dangerous_code = """
import os
os.system('rm -rf /')
"""
    result5 = executor.execute(dangerous_code, language='python')
    print(f"Success: {result5.success}")
    print(f"Error: {result5.error}")
    
    # Test 6: Compare same algorithm in both languages
    print("\n" + "=" * 60)
    print("Test 6: Fibonacci - Python vs JavaScript")
    print("=" * 60)
    
    python_fib = """
def fib(n):
    if n <= 1:
        return n
    return fib(n-1) + fib(n-2)

print(fib(10))
"""
    
    js_fib = """
function fib(n) {
    if (n <= 1) return n;
    return fib(n - 1) + fib(n - 2);
}

console.log(fib(10));
"""
    
    py_result = executor.execute(python_fib, language='python')
    js_result = executor.execute(js_fib, language='javascript')
    
    print(f"Python: {py_result.output.strip()} (Time: {py_result.execution_time:.4f}s)")
    print(f"JavaScript: {js_result.output.strip()} (Time: {js_result.execution_time:.4f}s)")
    
    print("\n" + "=" * 60)
    print("Supported Languages:", ", ".join(executor.get_supported_languages()))
    print("=" * 60)
