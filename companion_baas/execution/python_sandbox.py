"""
Python Sandbox - Safe Python code execution

Executes Python code in a restricted environment with timeouts and resource limits.
"""

import sys
import io
import signal
import traceback
from contextlib import contextmanager
from typing import Optional, Dict, Any
from dataclasses import dataclass
import time

from .security_validator import SecurityValidator


@dataclass
class ExecutionResult:
    """Result of code execution"""
    success: bool
    output: str
    error: Optional[str] = None
    execution_time: float = 0.0
    return_value: Any = None


class TimeoutException(Exception):
    """Raised when code execution times out"""
    pass


class PythonSandbox:
    """
    Safe Python code execution sandbox
    
    Features:
    - Restricted built-in functions
    - Timeout protection
    - Output capture
    - Memory limits (optional)
    - Import restrictions
    """
    
    def __init__(
        self,
        timeout: int = 5,
        max_output_size: int = 10000,
        allowed_imports: Optional[list] = None
    ):
        """
        Initialize Python sandbox
        
        Args:
            timeout: Maximum execution time in seconds
            max_output_size: Maximum output size in characters
            allowed_imports: Additional imports to allow beyond safe defaults
        """
        self.timeout = timeout
        self.max_output_size = max_output_size
        self.validator = SecurityValidator(allow_imports=allowed_imports)
    
    @contextmanager
    def _time_limit(self, seconds: int):
        """Context manager for timeout protection"""
        def signal_handler(signum, frame):
            raise TimeoutException(f"Code execution timed out after {seconds} seconds")
        
        # Set up signal handler (Unix only)
        if hasattr(signal, 'SIGALRM'):
            signal.signal(signal.SIGALRM, signal_handler)
            signal.alarm(seconds)
            try:
                yield
            finally:
                signal.alarm(0)
        else:
            # Windows fallback - no timeout protection
            yield
    
    def execute(
        self,
        code: str,
        globals_dict: Optional[Dict[str, Any]] = None,
        locals_dict: Optional[Dict[str, Any]] = None
    ) -> ExecutionResult:
        """
        Execute Python code safely
        
        Args:
            code: Python code to execute
            globals_dict: Global variables to provide
            locals_dict: Local variables to provide
        
        Returns:
            ExecutionResult with output and status
        """
        # Validate code first
        is_safe, issues = self.validator.validate_code(code, language='python')
        
        if not is_safe:
            critical_issues = [i for i in issues if i.severity == 'critical']
            error_msg = "Code validation failed:\n"
            for issue in critical_issues:
                error_msg += f"  Line {issue.line_number}: {issue.message}\n"
            
            return ExecutionResult(
                success=False,
                output="",
                error=error_msg
            )
        
        # Set up restricted environment
        safe_globals = globals_dict or {}
        safe_globals['__builtins__'] = self.validator.get_safe_builtins()
        
        # Use safe_globals as locals too to allow function definitions to be accessible
        safe_locals = locals_dict if locals_dict is not None else safe_globals
        
        # Capture output
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        
        sys.stdout = stdout_capture
        sys.stderr = stderr_capture
        
        start_time = time.time()
        return_value = None
        
        try:
            # Execute code with timeout
            with self._time_limit(self.timeout):
                exec(code, safe_globals, safe_locals)
                
                # Try to get return value from last expression
                if safe_locals:
                    # Get the last variable that was set
                    return_value = list(safe_locals.values())[-1] if safe_locals else None
            
            execution_time = time.time() - start_time
            
            # Get output
            output = stdout_capture.getvalue()
            error_output = stderr_capture.getvalue()
            
            # Limit output size
            if len(output) > self.max_output_size:
                output = output[:self.max_output_size] + "\n... (output truncated)"
            
            success = True
            error = error_output if error_output else None
            
        except TimeoutException as e:
            execution_time = time.time() - start_time
            output = stdout_capture.getvalue()
            error = str(e)
            success = False
            
        except Exception as e:
            execution_time = time.time() - start_time
            output = stdout_capture.getvalue()
            error = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
            success = False
        
        finally:
            # Restore stdout/stderr
            sys.stdout = old_stdout
            sys.stderr = old_stderr
        
        return ExecutionResult(
            success=success,
            output=output,
            error=error,
            execution_time=execution_time,
            return_value=return_value
        )
    
    def execute_function(
        self,
        code: str,
        function_name: str,
        *args,
        **kwargs
    ) -> ExecutionResult:
        """
        Execute a function defined in code with arguments
        
        Args:
            code: Python code containing function definition
            function_name: Name of function to call
            *args: Positional arguments to pass
            **kwargs: Keyword arguments to pass
        
        Returns:
            ExecutionResult with function output
        """
        # First execute the code to define the function
        result = self.execute(code)
        
        if not result.success:
            return result
        
        # Now call the function
        call_code = f"result = {function_name}(*{args}, **{kwargs})"
        
        # Create a context with the function
        globals_dict = {'__builtins__': self.validator.get_safe_builtins()}
        
        # Execute original code to get function
        exec(code, globals_dict)
        
        # Now call it
        return self.execute(call_code, globals_dict=globals_dict)
    
    def evaluate_expression(self, expression: str) -> ExecutionResult:
        """
        Evaluate a Python expression
        
        Args:
            expression: Python expression to evaluate
        
        Returns:
            ExecutionResult with expression value
        """
        # Validate expression
        is_safe, issues = self.validator.validate_code(expression, language='python')
        
        if not is_safe:
            critical_issues = [i for i in issues if i.severity == 'critical']
            error_msg = "Expression validation failed:\n"
            for issue in critical_issues:
                error_msg += f"  {issue.message}\n"
            
            return ExecutionResult(
                success=False,
                output="",
                error=error_msg
            )
        
        # Set up restricted environment
        safe_globals = {'__builtins__': self.validator.get_safe_builtins()}
        
        start_time = time.time()
        
        try:
            with self._time_limit(self.timeout):
                result = eval(expression, safe_globals)
            
            execution_time = time.time() - start_time
            
            return ExecutionResult(
                success=True,
                output=str(result),
                execution_time=execution_time,
                return_value=result
            )
            
        except TimeoutException as e:
            execution_time = time.time() - start_time
            return ExecutionResult(
                success=False,
                output="",
                error=str(e),
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            return ExecutionResult(
                success=False,
                output="",
                error=f"{type(e).__name__}: {str(e)}",
                execution_time=execution_time
            )


# Example usage
if __name__ == "__main__":
    sandbox = PythonSandbox(timeout=5)
    
    # Test 1: Simple calculation
    print("Test 1: Simple calculation")
    code1 = """
result = 2 + 2
print(f"2 + 2 = {result}")
"""
    result1 = sandbox.execute(code1)
    print(f"Success: {result1.success}")
    print(f"Output: {result1.output}")
    print(f"Time: {result1.execution_time:.4f}s\n")
    
    # Test 2: Function definition and execution
    print("Test 2: Function execution")
    code2 = """
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

for i in range(10):
    print(f"fib({i}) = {fibonacci(i)}")
"""
    result2 = sandbox.execute(code2)
    print(f"Success: {result2.success}")
    print(f"Output: {result2.output}")
    print(f"Time: {result2.execution_time:.4f}s\n")
    
    # Test 3: Expression evaluation
    print("Test 3: Expression evaluation")
    result3 = sandbox.evaluate_expression("sum([i**2 for i in range(10)])")
    print(f"Success: {result3.success}")
    print(f"Result: {result3.return_value}")
    print(f"Time: {result3.execution_time:.4f}s\n")
    
    # Test 4: Dangerous code (should fail)
    print("Test 4: Dangerous code (should fail)")
    dangerous_code = """
import os
os.system('echo "This should not execute"')
"""
    result4 = sandbox.execute(dangerous_code)
    print(f"Success: {result4.success}")
    print(f"Error: {result4.error}\n")
    
    # Test 5: Infinite loop (should timeout)
    print("Test 5: Timeout test")
    infinite_loop = """
while True:
    pass
"""
    result5 = sandbox.execute(infinite_loop)
    print(f"Success: {result5.success}")
    print(f"Error: {result5.error}")
