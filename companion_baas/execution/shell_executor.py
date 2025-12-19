"""
Shell Executor - Execute shell commands safely

Executes shell commands with restrictions and timeout.
"""

import subprocess
import time
from typing import Optional
from dataclasses import dataclass


@dataclass
class ShellExecutionResult:
    """Result of shell command execution"""
    success: bool
    output: str
    error: Optional[str] = None
    execution_time: float = 0.0
    return_code: int = 0


class ShellExecutor:
    """
    Execute shell commands safely
    
    Features:
    - Command whitelist
    - Timeout protection
    - Output capture
    - Security restrictions
    """
    
    # Allowed commands (whitelist approach)
    ALLOWED_COMMANDS = {
        'echo', 'pwd', 'ls', 'cat', 'grep', 'wc', 'head', 'tail',
        'date', 'whoami', 'uname', 'which', 'whereis',
        'git', 'python', 'node', 'npm', 'pip',
    }
    
    # Dangerous patterns to block
    DANGEROUS_PATTERNS = [
        'rm ', 'del ', 'format', 'mkfs',
        '> /dev/', 'dd if=', 'chmod 777',
        'wget ', 'curl ', '; wget', '; curl',
        '&& rm', '|| rm', '| rm',
    ]
    
    def __init__(
        self,
        timeout: int = 5,
        max_output_size: int = 10000,
        allowed_commands: Optional[set] = None
    ):
        """
        Initialize shell executor
        
        Args:
            timeout: Maximum execution time in seconds
            max_output_size: Maximum output size in characters
            allowed_commands: Additional commands to allow
        """
        self.timeout = timeout
        self.max_output_size = max_output_size
        
        if allowed_commands:
            self.allowed_commands = self.ALLOWED_COMMANDS | allowed_commands
        else:
            self.allowed_commands = self.ALLOWED_COMMANDS.copy()
    
    def is_command_safe(self, command: str) -> tuple[bool, Optional[str]]:
        """
        Check if command is safe to execute
        
        Args:
            command: Shell command
        
        Returns:
            (is_safe, reason) tuple
        """
        # Check for dangerous patterns
        for pattern in self.DANGEROUS_PATTERNS:
            if pattern in command.lower():
                return False, f"Dangerous pattern detected: {pattern}"
        
        # Get first word (command name)
        command_name = command.split()[0] if command.split() else ""
        
        # Check if command is in whitelist
        if command_name not in self.allowed_commands:
            return False, f"Command '{command_name}' not in whitelist"
        
        return True, None
    
    def execute(
        self,
        command: str,
        shell: bool = True,
        cwd: Optional[str] = None
    ) -> ShellExecutionResult:
        """
        Execute shell command
        
        Args:
            command: Shell command to execute
            shell: Whether to use shell
            cwd: Working directory
        
        Returns:
            ShellExecutionResult with output
        """
        # Validate command safety
        is_safe, reason = self.is_command_safe(command)
        
        if not is_safe:
            return ShellExecutionResult(
                success=False,
                output="",
                error=f"Command blocked: {reason}",
                return_code=-1
            )
        
        start_time = time.time()
        
        try:
            # Execute command
            result = subprocess.run(
                command,
                shell=shell,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=cwd
            )
            
            execution_time = time.time() - start_time
            
            output = result.stdout
            error = result.stderr if result.stderr else None
            
            # Limit output size
            if len(output) > self.max_output_size:
                output = output[:self.max_output_size] + "\n... (output truncated)"
            
            return ShellExecutionResult(
                success=result.returncode == 0,
                output=output,
                error=error,
                execution_time=execution_time,
                return_code=result.returncode
            )
            
        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            return ShellExecutionResult(
                success=False,
                output="",
                error=f"Command timed out after {self.timeout} seconds",
                execution_time=execution_time,
                return_code=-1
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            return ShellExecutionResult(
                success=False,
                output="",
                error=f"{type(e).__name__}: {str(e)}",
                execution_time=execution_time,
                return_code=-1
            )


# Example usage
if __name__ == "__main__":
    executor = ShellExecutor(timeout=5)
    
    # Test 1: Safe command
    print("Test 1: Safe command (echo)")
    result1 = executor.execute("echo 'Hello, World!'")
    print(f"Success: {result1.success}")
    print(f"Output: {result1.output}")
    print(f"Time: {result1.execution_time:.4f}s\n")
    
    # Test 2: Another safe command
    print("Test 2: List directory")
    result2 = executor.execute("ls -la")
    print(f"Success: {result2.success}")
    print(f"Output: {result2.output[:200]}...")
    print(f"Time: {result2.execution_time:.4f}s\n")
    
    # Test 3: Dangerous command (should fail)
    print("Test 3: Dangerous command (should fail)")
    result3 = executor.execute("rm -rf /")
    print(f"Success: {result3.success}")
    print(f"Error: {result3.error}\n")
    
    # Test 4: Unauthorized command (should fail)
    print("Test 4: Unauthorized command (should fail)")
    result4 = executor.execute("curl http://example.com")
    print(f"Success: {result4.success}")
    print(f"Error: {result4.error}")
