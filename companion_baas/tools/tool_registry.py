"""
Tool Registry - Registers and manages tools/functions

Provides a decorator-based system for registering tools.
"""

import inspect
import functools
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field

from .parameter_validator import ParameterValidator, ValidationError


@dataclass
class Tool:
    """Represents a registered tool"""
    name: str
    function: Callable
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    return_type: Optional[type] = None
    category: str = "general"
    tags: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Extract parameter information after initialization"""
        if not self.parameters:
            self.parameters = ParameterValidator.get_parameter_info(self.function)
        
        if not self.return_type:
            # Try to get return type from annotations
            sig = inspect.signature(self.function)
            self.return_type = sig.return_annotation if sig.return_annotation != inspect.Signature.empty else Any
    
    def to_dict(self) -> dict:
        """Convert tool to dictionary representation"""
        return {
            'name': self.name,
            'description': self.description,
            'category': self.category,
            'tags': self.tags,
            'parameters': {
                name: {
                    'type': info['type_name'],
                    'required': info['required'],
                    'default': info['default']
                }
                for name, info in self.parameters.items()
            },
            'return_type': self.return_type.__name__ if hasattr(self.return_type, '__name__') else str(self.return_type),
            'examples': self.examples
        }


def tool(
    name: Optional[str] = None,
    description: Optional[str] = None,
    category: str = "general",
    tags: Optional[List[str]] = None,
    examples: Optional[List[str]] = None
):
    """
    Decorator to register a function as a tool
    
    Usage:
        @tool(name="my_tool", description="Does something cool")
        def my_function(x: int, y: str) -> str:
            return f"{y}: {x}"
    
    Args:
        name: Tool name (defaults to function name)
        description: Tool description (defaults to docstring)
        category: Tool category for organization
        tags: Tags for discovery
        examples: Usage examples
    """
    def decorator(func: Callable) -> Callable:
        tool_name = name or func.__name__
        tool_description = description or (inspect.getdoc(func) or "No description")
        tool_tags = tags or []
        tool_examples = examples or []
        
        # Store tool metadata
        func._tool_metadata = {
            'name': tool_name,
            'description': tool_description,
            'category': category,
            'tags': tool_tags,
            'examples': tool_examples
        }
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        wrapper._tool_metadata = func._tool_metadata
        
        return wrapper
    
    return decorator


class ToolRegistry:
    """
    Registry for tools/functions
    
    Features:
    - Dynamic tool registration
    - Parameter validation
    - Tool discovery and search
    - Metadata management
    """
    
    def __init__(self):
        """Initialize tool registry"""
        self.tools: Dict[str, Tool] = {}
        self.validator = ParameterValidator()
        self._categories: Dict[str, List[str]] = {}
    
    def register(
        self,
        func: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None,
        category: str = "general",
        tags: Optional[List[str]] = None,
        examples: Optional[List[str]] = None
    ) -> Tool:
        """
        Register a function as a tool
        
        Args:
            func: Function to register
            name: Tool name (defaults to function name)
            description: Tool description
            category: Tool category
            tags: Search tags
            examples: Usage examples
        
        Returns:
            Registered Tool object
        """
        # Check if function has tool metadata from decorator
        if hasattr(func, '_tool_metadata'):
            metadata = func._tool_metadata
            name = name or metadata['name']
            description = description or metadata['description']
            category = metadata.get('category', category)
            tags = tags or metadata.get('tags', [])
            examples = examples or metadata.get('examples', [])
        
        tool_name = name or func.__name__
        tool_description = description or (inspect.getdoc(func) or "No description")
        
        # Create tool object
        tool_obj = Tool(
            name=tool_name,
            function=func,
            description=tool_description,
            category=category,
            tags=tags or [],
            examples=examples or []
        )
        
        # Register tool
        self.tools[tool_name] = tool_obj
        
        # Update category index
        if category not in self._categories:
            self._categories[category] = []
        if tool_name not in self._categories[category]:
            self._categories[category].append(tool_name)
        
        return tool_obj
    
    def unregister(self, name: str) -> bool:
        """
        Unregister a tool
        
        Args:
            name: Tool name
        
        Returns:
            True if unregistered, False if not found
        """
        if name in self.tools:
            tool = self.tools[name]
            
            # Remove from category index
            if tool.category in self._categories:
                self._categories[tool.category].remove(name)
            
            # Remove tool
            del self.tools[name]
            return True
        
        return False
    
    def execute(
        self,
        name: str,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute a registered tool
        
        Args:
            name: Tool name
            *args: Positional arguments
            **kwargs: Keyword arguments
        
        Returns:
            Tool execution result
        
        Raises:
            KeyError: If tool not found
            ValidationError: If parameters invalid
        """
        if name not in self.tools:
            raise KeyError(f"Tool '{name}' not found. Available tools: {', '.join(self.tools.keys())}")
        
        tool = self.tools[name]
        
        # Validate parameters
        validated_args, validated_kwargs = self.validator.validate_parameters(
            tool.function,
            args=args,
            kwargs=kwargs
        )
        
        # Execute tool
        return tool.function(*validated_args, **validated_kwargs)
    
    def get_tool(self, name: str) -> Optional[Tool]:
        """Get tool by name"""
        return self.tools.get(name)
    
    def list_tools(self, category: Optional[str] = None) -> List[Tool]:
        """
        List all registered tools
        
        Args:
            category: Filter by category (optional)
        
        Returns:
            List of Tool objects
        """
        if category:
            tool_names = self._categories.get(category, [])
            return [self.tools[name] for name in tool_names]
        
        return list(self.tools.values())
    
    def search_tools(
        self,
        query: str,
        search_in: List[str] = None
    ) -> List[Tool]:
        """
        Search for tools
        
        Args:
            query: Search query
            search_in: Fields to search in ('name', 'description', 'tags')
        
        Returns:
            List of matching tools
        """
        search_in = search_in or ['name', 'description', 'tags']
        query_lower = query.lower()
        
        matches = []
        
        for tool in self.tools.values():
            matched = False
            
            if 'name' in search_in and query_lower in tool.name.lower():
                matched = True
            
            if 'description' in search_in and query_lower in tool.description.lower():
                matched = True
            
            if 'tags' in search_in:
                if any(query_lower in tag.lower() for tag in tool.tags):
                    matched = True
            
            if matched:
                matches.append(tool)
        
        return matches
    
    def get_categories(self) -> List[str]:
        """Get list of all categories"""
        return list(self._categories.keys())
    
    def to_dict(self) -> dict:
        """Convert registry to dictionary"""
        return {
            'tools': {name: tool.to_dict() for name, tool in self.tools.items()},
            'categories': self._categories,
            'total_tools': len(self.tools)
        }


# Example usage
if __name__ == "__main__":
    print("=" * 70)
    print("TOOL REGISTRY - Function Registration System")
    print("=" * 70)
    
    # Create registry
    registry = ToolRegistry()
    
    # Example 1: Register with decorator
    @tool(
        name="calculate_sum",
        description="Calculate sum of two numbers",
        category="math",
        tags=["arithmetic", "basic"],
        examples=["calculate_sum(5, 3) -> 8"]
    )
    def add(a: int, b: int) -> int:
        """Add two numbers together"""
        return a + b
    
    registry.register(add)
    
    # Example 2: Register without decorator
    def multiply(x: float, y: float) -> float:
        """Multiply two numbers"""
        return x * y
    
    registry.register(
        multiply,
        name="calculate_product",
        description="Calculate product of two numbers",
        category="math",
        tags=["arithmetic"]
    )
    
    # Example 3: Register with optional parameters
    def greet(name: str, greeting: str = "Hello") -> str:
        """Greet someone"""
        return f"{greeting}, {name}!"
    
    registry.register(greet, category="text")
    
    # Test execution
    print("\nTest 1: Execute tools")
    print("-" * 70)
    result1 = registry.execute("calculate_sum", 10, 5)
    print(f"calculate_sum(10, 5) = {result1}")
    
    result2 = registry.execute("calculate_product", x=7.5, y=4.0)
    print(f"calculate_product(7.5, 4.0) = {result2}")
    
    result3 = registry.execute("greet", "Alice")
    print(f"greet('Alice') = {result3}")
    
    result4 = registry.execute("greet", name="Bob", greeting="Hi")
    print(f"greet('Bob', 'Hi') = {result4}")
    
    # Test listing
    print("\nTest 2: List tools")
    print("-" * 70)
    all_tools = registry.list_tools()
    print(f"Total tools: {len(all_tools)}")
    for tool in all_tools:
        print(f"  - {tool.name}: {tool.description}")
    
    # Test search
    print("\nTest 3: Search tools")
    print("-" * 70)
    math_tools = registry.search_tools("calculate")
    print(f"Tools matching 'calculate': {[t.name for t in math_tools]}")
    
    # Test categories
    print("\nTest 4: Categories")
    print("-" * 70)
    categories = registry.get_categories()
    print(f"Categories: {categories}")
    for category in categories:
        tools_in_cat = registry.list_tools(category=category)
        print(f"  {category}: {[t.name for t in tools_in_cat]}")
    
    # Test tool info
    print("\nTest 5: Tool information")
    print("-" * 70)
    tool_info = registry.get_tool("calculate_sum")
    print(f"Tool: {tool_info.name}")
    print(f"Description: {tool_info.description}")
    print(f"Category: {tool_info.category}")
    print(f"Parameters:")
    for param_name, param_info in tool_info.parameters.items():
        print(f"  {param_name}: {param_info['type_name']} "
              f"(required={param_info['required']}, default={param_info['default']})")
    
    print("\n" + "=" * 70)
