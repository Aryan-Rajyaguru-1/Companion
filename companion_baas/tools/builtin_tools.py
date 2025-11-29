"""
Built-in Tools - Pre-defined useful tools

Collection of commonly used tools.
"""

import math
import datetime
import json
import re
from typing import List, Dict, Any, Optional

from .tool_registry import tool


# ============================================================================
# MATH TOOLS
# ============================================================================

@tool(
    name="add",
    description="Add two numbers",
    category="math",
    tags=["arithmetic", "basic"],
    examples=["add(5, 3) -> 8"]
)
def add(a: float, b: float) -> float:
    """Add two numbers"""
    return a + b


@tool(
    name="subtract",
    description="Subtract two numbers",
    category="math",
    tags=["arithmetic", "basic"]
)
def subtract(a: float, b: float) -> float:
    """Subtract b from a"""
    return a - b


@tool(
    name="multiply",
    description="Multiply two numbers",
    category="math",
    tags=["arithmetic", "basic"]
)
def multiply(a: float, b: float) -> float:
    """Multiply two numbers"""
    return a * b


@tool(
    name="divide",
    description="Divide two numbers",
    category="math",
    tags=["arithmetic", "basic"]
)
def divide(a: float, b: float) -> float:
    """Divide a by b"""
    if b == 0:
        raise ValueError("Division by zero")
    return a / b


@tool(
    name="power",
    description="Raise a number to a power",
    category="math",
    tags=["arithmetic"]
)
def power(base: float, exponent: float) -> float:
    """Calculate base^exponent"""
    return base ** exponent


@tool(
    name="sqrt",
    description="Calculate square root",
    category="math",
    tags=["arithmetic"]
)
def sqrt(x: float) -> float:
    """Calculate square root of x"""
    if x < 0:
        raise ValueError("Cannot calculate square root of negative number")
    return math.sqrt(x)


# ============================================================================
# STRING TOOLS
# ============================================================================

@tool(
    name="uppercase",
    description="Convert text to uppercase",
    category="text",
    tags=["string", "formatting"]
)
def uppercase(text: str) -> str:
    """Convert text to uppercase"""
    return text.upper()


@tool(
    name="lowercase",
    description="Convert text to lowercase",
    category="text",
    tags=["string", "formatting"]
)
def lowercase(text: str) -> str:
    """Convert text to lowercase"""
    return text.lower()


@tool(
    name="reverse_text",
    description="Reverse a string",
    category="text",
    tags=["string"]
)
def reverse_text(text: str) -> str:
    """Reverse the order of characters in text"""
    return text[::-1]


@tool(
    name="count_words",
    description="Count words in text",
    category="text",
    tags=["string", "analysis"]
)
def count_words(text: str) -> int:
    """Count number of words in text"""
    return len(text.split())


@tool(
    name="count_characters",
    description="Count characters in text",
    category="text",
    tags=["string", "analysis"]
)
def count_characters(text: str, include_spaces: bool = True) -> int:
    """Count number of characters in text"""
    if include_spaces:
        return len(text)
    return len(text.replace(" ", ""))


@tool(
    name="extract_numbers",
    description="Extract numbers from text",
    category="text",
    tags=["string", "extraction"]
)
def extract_numbers(text: str) -> List[float]:
    """Extract all numbers from text"""
    # Find integers and decimals
    pattern = r'-?\d+\.?\d*'
    matches = re.findall(pattern, text)
    return [float(m) for m in matches if m]


# ============================================================================
# DATE/TIME TOOLS
# ============================================================================

@tool(
    name="current_datetime",
    description="Get current date and time",
    category="datetime",
    tags=["time"]
)
def current_datetime() -> str:
    """Get current date and time"""
    return datetime.datetime.now().isoformat()


@tool(
    name="current_timestamp",
    description="Get current Unix timestamp",
    category="datetime",
    tags=["time"]
)
def current_timestamp() -> int:
    """Get current Unix timestamp"""
    return int(datetime.datetime.now().timestamp())


@tool(
    name="format_date",
    description="Format a date string",
    category="datetime",
    tags=["time", "formatting"]
)
def format_date(date_str: str, format: str = "%Y-%m-%d") -> str:
    """Format a date string"""
    dt = datetime.datetime.fromisoformat(date_str)
    return dt.strftime(format)


# ============================================================================
# LIST/ARRAY TOOLS
# ============================================================================

@tool(
    name="list_sum",
    description="Sum all numbers in a list",
    category="list",
    tags=["array", "math"]
)
def list_sum(numbers: List[float]) -> float:
    """Calculate sum of all numbers in list"""
    return sum(numbers)


@tool(
    name="list_average",
    description="Calculate average of numbers in list",
    category="list",
    tags=["array", "math", "statistics"]
)
def list_average(numbers: List[float]) -> float:
    """Calculate average of numbers in list"""
    if not numbers:
        raise ValueError("Cannot calculate average of empty list")
    return sum(numbers) / len(numbers)


@tool(
    name="list_min",
    description="Find minimum value in list",
    category="list",
    tags=["array"]
)
def list_min(numbers: List[float]) -> float:
    """Find minimum value in list"""
    if not numbers:
        raise ValueError("Cannot find min of empty list")
    return min(numbers)


@tool(
    name="list_max",
    description="Find maximum value in list",
    category="list",
    tags=["array"]
)
def list_max(numbers: List[float]) -> float:
    """Find maximum value in list"""
    if not numbers:
        raise ValueError("Cannot find max of empty list")
    return max(numbers)


@tool(
    name="list_unique",
    description="Get unique values from list",
    category="list",
    tags=["array"]
)
def list_unique(items: List[Any]) -> List[Any]:
    """Get unique values from list, preserving order"""
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


@tool(
    name="list_sort",
    description="Sort a list",
    category="list",
    tags=["array"]
)
def list_sort(items: List[Any], reverse: bool = False) -> List[Any]:
    """Sort a list"""
    return sorted(items, reverse=reverse)


# ============================================================================
# DATA TOOLS
# ============================================================================

@tool(
    name="parse_json",
    description="Parse JSON string to dictionary",
    category="data",
    tags=["json", "parsing"]
)
def parse_json(json_str: str) -> Dict[str, Any]:
    """Parse JSON string to dictionary"""
    return json.loads(json_str)


@tool(
    name="to_json",
    description="Convert dictionary to JSON string",
    category="data",
    tags=["json", "serialization"]
)
def to_json(data: Dict[str, Any], pretty: bool = False) -> str:
    """Convert dictionary to JSON string"""
    if pretty:
        return json.dumps(data, indent=2)
    return json.dumps(data)


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_builtin_tools() -> List:
    """Get list of all built-in tool functions"""
    return [
        # Math
        add, subtract, multiply, divide, power, sqrt,
        # Text
        uppercase, lowercase, reverse_text, count_words, count_characters, extract_numbers,
        # DateTime
        current_datetime, current_timestamp, format_date,
        # List
        list_sum, list_average, list_min, list_max, list_unique, list_sort,
        # Data
        parse_json, to_json,
    ]


def register_builtin_tools(registry) -> int:
    """
    Register all built-in tools to a registry
    
    Args:
        registry: ToolRegistry instance
    
    Returns:
        Number of tools registered
    """
    tools = get_builtin_tools()
    
    for tool_func in tools:
        registry.register(tool_func)
    
    return len(tools)


# Example usage
if __name__ == "__main__":
    from tool_registry import ToolRegistry
    
    print("=" * 70)
    print("BUILT-IN TOOLS")
    print("=" * 70)
    
    # Create registry and register built-in tools
    registry = ToolRegistry()
    count = register_builtin_tools(registry)
    
    print(f"\n✓ Registered {count} built-in tools")
    
    # Show categories
    print("\nCategories:")
    for category in registry.get_categories():
        tools_in_cat = registry.list_tools(category=category)
        print(f"  {category}: {len(tools_in_cat)} tools")
    
    # Test some tools
    print("\nTest Executions:")
    print("-" * 70)
    
    print(f"add(10, 5) = {registry.execute('add', 10, 5)}")
    print(f"multiply(7, 8) = {registry.execute('multiply', 7, 8)}")
    print(f"sqrt(144) = {registry.execute('sqrt', 144)}")
    print(f"uppercase('hello') = {registry.execute('uppercase', 'hello')}")
    print(f"count_words('The quick brown fox') = {registry.execute('count_words', 'The quick brown fox')}")
    print(f"list_average([1, 2, 3, 4, 5]) = {registry.execute('list_average', [1, 2, 3, 4, 5])}")
    print(f"current_datetime() = {registry.execute('current_datetime')}")
    
    print("\n" + "=" * 70)
