"""
JavaScript Executor - Execute JavaScript/Node.js code

Executes JavaScript code using Node.js subprocess.
"""

import subprocess
import json
import tempfile
import os
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass

from .security_validator import SecurityValidator


@dataclass
class JSExecutionResult:
    """Result of JavaScript execution"""
    success: bool
    output: str
    error: Optional[str] = None
    execution_time: float = 0.0
    return_value: Any = None


class JavaScriptExecutor:
    """
    Execute JavaScript code using Node.js
    
    Features:
    - Node.js subprocess execution
    - Timeout protection
    - Output capture
    - Security validation
    """
    
    def __init__(
        self,
        timeout: int = 5,
        node_path: str = 'node',
        max_output_size: int = 10000
    ):
        """
        Initialize JavaScript executor
        
        Args:
            timeout: Maximum execution time in seconds
            node_path: Path to Node.js executable
            max_output_size: Maximum output size in characters
        """
        self.timeout = timeout
        self.node_path = node_path
        self.max_output_size = max_output_size
        self.validator = SecurityValidator()
        
        # Check if Node.js is available
        self._check_node_availability()
    
    def _check_node_availability(self):
        """Check if Node.js is installed and available"""
        try:
            result = subprocess.run(
                [self.node_path, '--version'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                print(f"Node.js available: {version}")
            else:
                print("Warning: Node.js not responding properly")
        except FileNotFoundError:
            print(f"Warning: Node.js not found at '{self.node_path}'")
        except Exception as e:
            print(f"Warning: Error checking Node.js: {e}")
    
    def execute(
        self,
        code: str,
        capture_console: bool = True
    ) -> JSExecutionResult:
        """
        Execute JavaScript code
        
        Args:
            code: JavaScript code to execute
            capture_console: Whether to capture console.log output
        
        Returns:
            JSExecutionResult with output and status
        """
        # Validate code first
        is_safe, issues = self.validator.validate_code(code, language='javascript')
        
        if not is_safe:
            critical_issues = [i for i in issues if i.severity == 'critical']
            error_msg = "Code validation failed:\n"
            for issue in critical_issues:
                error_msg += f"  Line {issue.line_number}: {issue.message}\n"
            
            return JSExecutionResult(
                success=False,
                output="",
                error=error_msg
            )
        
        # Wrap code to capture output if needed
        if capture_console:
            wrapped_code = f"""
const originalLog = console.log;
const outputs = [];

console.log = function(...args) {{
    outputs.push(args.map(arg => 
        typeof arg === 'object' ? JSON.stringify(arg, null, 2) : String(arg)
    ).join(' '));
    originalLog(...args);
}};

try {{
    {code}
    
    // Output captured logs
    if (outputs.length > 0) {{
        process.stdout.write(outputs.join('\\n'));
    }}
}} catch (error) {{
    process.stderr.write(error.toString());
    process.exit(1);
}}
"""
        else:
            wrapped_code = code
        
        # Write code to temporary file
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.js',
            delete=False,
            encoding='utf-8'
        ) as f:
            f.write(wrapped_code)
            temp_file = f.name
        
        start_time = time.time()
        
        try:
            # Execute with Node.js
            result = subprocess.run(
                [self.node_path, temp_file],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env=os.environ.copy()
            )
            
            execution_time = time.time() - start_time
            
            output = result.stdout
            error = result.stderr if result.stderr else None
            
            # Limit output size
            if len(output) > self.max_output_size:
                output = output[:self.max_output_size] + "\n... (output truncated)"
            
            success = result.returncode == 0
            
            return JSExecutionResult(
                success=success,
                output=output,
                error=error,
                execution_time=execution_time
            )
            
        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            return JSExecutionResult(
                success=False,
                output="",
                error=f"Code execution timed out after {self.timeout} seconds",
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            return JSExecutionResult(
                success=False,
                output="",
                error=f"{type(e).__name__}: {str(e)}",
                execution_time=execution_time
            )
            
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_file)
            except:
                pass
    
    def execute_function(
        self,
        code: str,
        function_name: str,
        args: list = None
    ) -> JSExecutionResult:
        """
        Execute a JavaScript function with arguments
        
        Args:
            code: JavaScript code containing function
            function_name: Name of function to call
            args: Arguments to pass to function
        
        Returns:
            JSExecutionResult with function output
        """
        args = args or []
        args_json = json.dumps(args)
        
        wrapped_code = f"""
{code}

const args = {args_json};
const result = {function_name}(...args);
console.log(result);
"""
        
        return self.execute(wrapped_code)
    
    def evaluate_expression(self, expression: str) -> JSExecutionResult:
        """
        Evaluate a JavaScript expression
        
        Args:
            expression: JavaScript expression to evaluate
        
        Returns:
            JSExecutionResult with expression value
        """
        code = f"console.log({expression});"
        return self.execute(code)


# Example usage
if __name__ == "__main__":
    executor = JavaScriptExecutor(timeout=5)
    
    # Test 1: Simple calculation
    print("Test 1: Simple calculation")
    code1 = """
const result = 2 + 2;
console.log(`2 + 2 = ${result}`);
"""
    result1 = executor.execute(code1)
    print(f"Success: {result1.success}")
    print(f"Output: {result1.output}")
    print(f"Time: {result1.execution_time:.4f}s\n")
    
    # Test 2: Function execution
    print("Test 2: Function execution")
    code2 = """
function fibonacci(n) {
    if (n <= 1) return n;
    return fibonacci(n - 1) + fibonacci(n - 2);
}

for (let i = 0; i < 10; i++) {
    console.log(`fib(${i}) = ${fibonacci(i)}`);
}
"""
    result2 = executor.execute(code2)
    print(f"Success: {result2.success}")
    print(f"Output: {result2.output}")
    print(f"Time: {result2.execution_time:.4f}s\n")
    
    # Test 3: Expression evaluation
    print("Test 3: Expression evaluation")
    result3 = executor.evaluate_expression("[1, 2, 3, 4, 5].reduce((a, b) => a + b, 0)")
    print(f"Success: {result3.success}")
    print(f"Result: {result3.output}")
    print(f"Time: {result3.execution_time:.4f}s\n")
    
    # Test 4: Function call
    print("Test 4: Function call with arguments")
    code4 = """
function greet(name, age) {
    return `Hello, ${name}! You are ${age} years old.`;
}
"""
    result4 = executor.execute_function(code4, "greet", ["Alice", 25])
    print(f"Success: {result4.success}")
    print(f"Output: {result4.output}")
    print(f"Time: {result4.execution_time:.4f}s\n")
    
    # Test 5: Array operations
    print("Test 5: Array operations")
    code5 = """
const numbers = [1, 2, 3, 4, 5];
const squared = numbers.map(x => x * x);
const sum = squared.reduce((a, b) => a + b, 0);
console.log(`Squares: ${squared}`);
console.log(`Sum: ${sum}`);
"""
    result5 = executor.execute(code5)
    print(f"Success: {result5.success}")
    print(f"Output: {result5.output}")
    print(f"Time: {result5.execution_time:.4f}s")
