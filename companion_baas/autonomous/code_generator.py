#!/usr/bin/env python3
"""
Code Generator - Autonomous Code Generation
===========================================

Generates code solutions autonomously for:
- Algorithm implementations
- Bug fixes
- API integrations
- Test generation
- Refactoring suggestions
- Documentation generation
"""

import logging
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class CodeGenerationRequest:
    """Request for code generation"""
    task_type: str  # 'implement', 'fix', 'test', 'refactor', 'document'
    description: str
    language: str = 'python'
    context: Dict[str, Any] = field(default_factory=dict)
    constraints: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)


@dataclass
class GeneratedCode:
    """Generated code result"""
    code: str
    explanation: str
    confidence: float
    language: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    tests: List[str] = field(default_factory=list)


class CodeGenerator:
    """
    Autonomous code generator that creates solutions, fixes bugs,
    and generates various types of code artifacts.
    """

    def __init__(self, brain):
        self.brain = brain
        self.generation_history = []
        self.templates = self._load_code_templates()

        logger.info("💻 Code Generator initialized")

    def generate_solution(self, problem: str, language: str = 'python', context: Dict[str, Any] = None) -> GeneratedCode:
        """
        Generate a complete code solution for a given problem

        Args:
            problem: Description of the problem to solve
            language: Programming language for the solution
            context: Additional context (existing code, requirements, etc.)

        Returns:
            GeneratedCode with solution and metadata
        """
        request = CodeGenerationRequest(
            task_type='implement',
            description=problem,
            language=language,
            context=context or {}
        )

        return self._generate_code(request)

    def generate_fix(self, error: str, context: Dict[str, Any] = None) -> GeneratedCode:
        """
        Generate a bug fix for a given error

        Args:
            error: Error message or description
            context: Code context, stack trace, etc.

        Returns:
            GeneratedCode with the fix
        """
        request = CodeGenerationRequest(
            task_type='fix',
            description=error,
            context=context or {}
        )

        return self._generate_code(request)

    def generate_tests(self, code: str, language: str = 'python') -> List[str]:
        """
        Generate unit tests for given code

        Args:
            code: Code to generate tests for
            language: Programming language

        Returns:
            List of test code strings
        """
        request = CodeGenerationRequest(
            task_type='test',
            description=f"Generate comprehensive unit tests for this code:\n\n{code}",
            language=language,
            context={'code_to_test': code}
        )

        result = self._generate_code(request)
        return result.tests or [result.code]

    def generate_refactor(self, code: str, improvement_type: str = 'readability') -> GeneratedCode:
        """
        Generate refactored version of code

        Args:
            code: Code to refactor
            improvement_type: Type of improvement ('readability', 'performance', 'maintainability')

        Returns:
            GeneratedCode with refactored version
        """
        request = CodeGenerationRequest(
            task_type='refactor',
            description=f"Refactor this code for better {improvement_type}:\n\n{code}",
            context={'original_code': code, 'improvement_type': improvement_type}
        )

        return self._generate_code(request)

    def generate_api_integration(self, api_spec: Dict[str, Any], language: str = 'python') -> GeneratedCode:
        """
        Generate API integration code

        Args:
            api_spec: API specification (endpoints, methods, etc.)
            language: Target language

        Returns:
            GeneratedCode with API client
        """
        request = CodeGenerationRequest(
            task_type='api',
            description=f"Generate API client for: {api_spec.get('name', 'API')}",
            language=language,
            context={'api_spec': api_spec}
        )

        return self._generate_code(request)

    def _generate_code(self, request: CodeGenerationRequest) -> GeneratedCode:
        """
        Core code generation logic
        """
        start_time = datetime.now()

        try:
            # Create generation prompt based on task type
            prompt = self._create_generation_prompt(request)

            # Generate code using brain
            system_prompt = self._get_system_prompt(request.task_type, request.language)
            generated_code = self.brain.ask(prompt, system="You are an expert software engineer and code generator")

            # Parse and validate the generated code
            parsed_result = self._parse_generated_code(generated_code, request)

            # Generate explanation
            explanation = self._generate_explanation(parsed_result, request)

            # Calculate confidence
            confidence = self._calculate_confidence(parsed_result, request)

            # Generate tests if applicable
            tests = []
            if request.task_type in ['implement', 'fix']:
                tests = self._generate_tests_for_code(parsed_result.code, request.language)

            result = GeneratedCode(
                code=parsed_result.code,
                explanation=explanation,
                confidence=confidence,
                language=request.language,
                tests=tests,
                metadata={
                    'task_type': request.task_type,
                    'generation_time': (datetime.now() - start_time).total_seconds(),
                    'prompt_tokens': len(prompt.split()),
                    'code_lines': len(parsed_result.code.split('\n')),
                    'complexity': self._estimate_complexity(parsed_result.code)
                }
            )

            # Store in history
            self.generation_history.append({
                'request': request,
                'result': result,
                'timestamp': datetime.now().isoformat()
            })

            logger.info(f"✅ Generated {request.task_type} code ({len(result.code)} chars, confidence: {confidence:.2f})")
            return result

        except Exception as e:
            logger.error(f"Code generation failed: {e}")
            return GeneratedCode(
                code="",
                explanation=f"Code generation failed: {str(e)}",
                confidence=0.0,
                language=request.language,
                metadata={'error': str(e)}
            )

    def _create_generation_prompt(self, request: CodeGenerationRequest) -> str:
        """Create the appropriate prompt for code generation"""
        base_prompt = f"""
Generate {request.task_type} code in {request.language}.

TASK: {request.description}
"""

        if request.context:
            base_prompt += f"\nCONTEXT:\n{request.context}\n"

        if request.constraints:
            base_prompt += f"\nCONSTRAINTS:\n" + "\n".join(f"- {c}" for c in request.constraints) + "\n"

        if request.examples:
            base_prompt += f"\nEXAMPLES:\n" + "\n".join(request.examples) + "\n"

        # Task-specific instructions
        if request.task_type == 'implement':
            base_prompt += """
REQUIREMENTS:
- Complete, working code
- Proper error handling
- Comments for complex logic
- Follow language best practices
- Include necessary imports
"""
        elif request.task_type == 'fix':
            base_prompt += """
REQUIREMENTS:
- Identify the root cause
- Provide corrected code
- Explain what was wrong
- Ensure the fix doesn't break other functionality
"""
        elif request.task_type == 'test':
            base_prompt += """
REQUIREMENTS:
- Comprehensive unit tests
- Edge cases covered
- Both positive and negative tests
- Clear test names and assertions
"""
        elif request.task_type == 'refactor':
            improvement = request.context.get('improvement_type', 'readability')
            base_prompt += f"""
REQUIREMENTS:
- Improve {improvement}
- Maintain exact same functionality
- Better variable names and structure
- Remove code duplication
- Add helpful comments
"""

        return base_prompt

    def _get_system_prompt(self, task_type: str, language: str) -> str:
        """Get appropriate system prompt for the task"""
        base = f"You are an expert {language} developer. "

        if task_type == 'implement':
            return base + "Generate clean, efficient, and well-documented code."
        elif task_type == 'fix':
            return base + "Debug and fix code issues with clear explanations."
        elif task_type == 'test':
            return base + "Write comprehensive, maintainable unit tests."
        elif task_type == 'refactor':
            return base + "Refactor code for better readability and maintainability."
        else:
            return base + "Generate high-quality code solutions."

    def _parse_generated_code(self, generated_text: str, request: CodeGenerationRequest) -> Any:
        """Parse the generated code from the response"""
        # Simple parsing - extract code blocks
        code_blocks = re.findall(r'```(?:\w+)?\n(.*?)\n```', generated_text, re.DOTALL)

        if code_blocks:
            code = code_blocks[0].strip()
        else:
            # No code blocks, assume the whole response is code
            code = generated_text.strip()

        # Clean up common artifacts
        code = re.sub(r'^```\w*\n', '', code, flags=re.MULTILINE)
        code = re.sub(r'\n```$', '', code)

        return type('ParsedResult', (), {'code': code})()

    def _generate_explanation(self, parsed_result, request: CodeGenerationRequest) -> str:
        """Generate explanation for the generated code"""
        prompt = f"""
Explain what this code does:

``` {request.language}
{parsed_result.code}
```

Provide a clear, concise explanation of:
1. What the code accomplishes
2. Key algorithms or patterns used
3. Any important design decisions
"""

        try:
            explanation = self.brain.ask(prompt, system="You are a technical documentation expert")
            return explanation
        except:
            return f"Generated {request.task_type} code in {request.language}"

    def _calculate_confidence(self, parsed_result, request: CodeGenerationRequest) -> float:
        """Calculate confidence score for the generated code"""
        confidence = 0.5  # Base confidence

        code = parsed_result.code

        # Length check
        if len(code) > 50:
            confidence += 0.2

        # Structure check
        if any(keyword in code for keyword in ['def ', 'function ', 'class ', 'import ', 'from ']):
            confidence += 0.2

        # Error handling check
        if any(keyword in code for keyword in ['try:', 'except', 'catch', 'throw']):
            confidence += 0.1

        # Comments check
        comment_lines = sum(1 for line in code.split('\n') if line.strip().startswith(('#', '//', '/*')))
        if comment_lines > 2:
            confidence += 0.1

        return min(confidence, 1.0)

    def _generate_tests_for_code(self, code: str, language: str) -> List[str]:
        """Generate unit tests for the given code"""
        if language != 'python':
            return []

        prompt = f"""
Generate unit tests for this Python code:

```python
{code}
```

Requirements:
- Use pytest framework
- Cover main functionality
- Include edge cases
- Test both success and failure scenarios
- Use descriptive test names

Return the test code in a code block.
"""

        try:
            test_code = self.brain.ask(prompt, system="You are an expert test developer")
            # Extract code blocks
            test_blocks = re.findall(r'```(?:\w+)?\n(.*?)\n```', test_code, re.DOTALL)
            return test_blocks if test_blocks else [test_code]
        except:
            return []

    def _estimate_complexity(self, code: str) -> int:
        """Estimate code complexity"""
        lines = code.split('\n')
        complexity = 1  # Base

        for line in lines:
            stripped = line.strip()
            if any(keyword in stripped for keyword in ['if ', 'for ', 'while ', 'def ', 'function ', 'class ']):
                complexity += 1
            if ' and ' in stripped or ' or ' in stripped:
                complexity += 0.5

        return int(complexity)

    def _load_code_templates(self) -> Dict[str, Dict[str, str]]:
        """Load code templates for different languages and patterns"""
        return {
            'python': {
                'class_template': '''
class {ClassName}:
    """{Description}"""

    def __init__(self{params}):
        """Initialize {ClassName}"""
        {init_body}

    def {main_method}(self{params}):
        """{Method description}"""
        {method_body}
''',
                'function_template': '''
def {function_name}({params}):
    """
    {Description}

    Args:
        {args_description}

    Returns:
        {return_description}
    """
    {function_body}
''',
                'test_template': '''
import pytest
from {module_name} import {class_or_function}

def test_{test_name}():
    """Test {test_description}"""
    # Arrange
    {arrange}

    # Act
    {act}

    # Assert
    {assert}
'''
            }
        }

    def get_generation_stats(self) -> Dict[str, Any]:
        """Get statistics about code generation performance"""
        if not self.generation_history:
            return {'total_generations': 0}

        total = len(self.generation_history)
        avg_confidence = sum(h['result'].confidence for h in self.generation_history) / total
        avg_time = sum(h['result'].metadata.get('generation_time', 0) for h in self.generation_history) / total

        task_types = {}
        for h in self.generation_history:
            task_type = h['request'].task_type
            task_types[task_type] = task_types.get(task_type, 0) + 1

        return {
            'total_generations': total,
            'average_confidence': avg_confidence,
            'average_generation_time': avg_time,
            'task_type_distribution': task_types,
            'languages_used': list(set(h['request'].language for h in self.generation_history))
        }
