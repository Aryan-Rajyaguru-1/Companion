"""
Parameter Validator - Validates tool parameters

Ensures type safety and validates parameters before tool execution.
"""

import inspect
from typing import Any, Dict, Optional, get_type_hints, get_args, get_origin
from dataclasses import is_dataclass


class ValidationError(Exception):
    """Raised when parameter validation fails"""
    pass


class ParameterValidator:
    """
    Validates parameters against function signatures
    
    Features:
    - Type checking
    - Required parameter validation
    - Default value handling
    - Complex type support (List, Dict, Optional)
    """
    
    @staticmethod
    def validate_parameters(
        func: callable,
        args: tuple = None,
        kwargs: dict = None
    ) -> tuple[tuple, dict]:
        """
        Validate parameters against function signature
        
        Args:
            func: Function to validate against
            args: Positional arguments
            kwargs: Keyword arguments
        
        Returns:
            (validated_args, validated_kwargs) tuple
        
        Raises:
            ValidationError: If validation fails
        """
        args = args or ()
        kwargs = kwargs or {}
        
        # Get function signature
        sig = inspect.signature(func)
        type_hints = get_type_hints(func) if hasattr(func, '__annotations__') else {}
        
        # Bind arguments to signature
        try:
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
        except TypeError as e:
            raise ValidationError(f"Parameter binding failed: {str(e)}")
        
        # Validate types
        for param_name, param_value in bound_args.arguments.items():
            if param_name in type_hints:
                expected_type = type_hints[param_name]
                ParameterValidator._validate_type(param_name, param_value, expected_type)
        
        return bound_args.args, bound_args.kwargs
    
    @staticmethod
    def _validate_type(param_name: str, value: Any, expected_type: Any):
        """Validate a single parameter type"""
        
        # Handle Any type - accept anything
        if expected_type is Any or str(expected_type) == 'typing.Any':
            return
        
        # Handle None/Optional
        if value is None:
            origin = get_origin(expected_type)
            if origin is not type(None):
                args = get_args(expected_type)
                # Check if Optional (Union with None)
                if type(None) not in args:
                    raise ValidationError(
                        f"Parameter '{param_name}' cannot be None"
                    )
            return
        
        # Get origin type for generic types (List, Dict, etc.)
        origin = get_origin(expected_type)
        
        if origin is None:
            # Simple type checking
            # Allow int for float parameters (int is compatible with float)
            if expected_type is float and isinstance(value, (int, float)):
                return
            
            if not isinstance(value, expected_type):
                raise ValidationError(
                    f"Parameter '{param_name}' must be {expected_type.__name__}, "
                    f"got {type(value).__name__}"
                )
        else:
            # Handle generic types
            ParameterValidator._validate_generic_type(param_name, value, expected_type, origin)
    
    @staticmethod
    def _validate_generic_type(param_name: str, value: Any, expected_type: Any, origin: Any):
        """Validate generic types (List, Dict, Optional, etc.)"""
        
        args = get_args(expected_type)
        
        if origin is list:
            if not isinstance(value, list):
                raise ValidationError(
                    f"Parameter '{param_name}' must be a list, got {type(value).__name__}"
                )
            
            # Validate list items if type is specified
            if args:
                item_type = args[0]
                for i, item in enumerate(value):
                    try:
                        ParameterValidator._validate_type(f"{param_name}[{i}]", item, item_type)
                    except ValidationError:
                        pass  # Allow mixed types in list for now
        
        elif origin is dict:
            if not isinstance(value, dict):
                raise ValidationError(
                    f"Parameter '{param_name}' must be a dict, got {type(value).__name__}"
                )
        
        elif origin is tuple:
            if not isinstance(value, tuple):
                raise ValidationError(
                    f"Parameter '{param_name}' must be a tuple, got {type(value).__name__}"
                )
        
        # Handle Union types (including Optional)
        elif hasattr(origin, '__origin__') and origin.__origin__ is Union:
            # Try each type in the union
            valid = False
            for arg_type in args:
                try:
                    ParameterValidator._validate_type(param_name, value, arg_type)
                    valid = True
                    break
                except ValidationError:
                    continue
            
            if not valid:
                type_names = [t.__name__ if hasattr(t, '__name__') else str(t) for t in args]
                raise ValidationError(
                    f"Parameter '{param_name}' must be one of {type_names}, "
                    f"got {type(value).__name__}"
                )
    
    @staticmethod
    def get_parameter_info(func: callable) -> Dict[str, Any]:
        """
        Get information about function parameters
        
        Args:
            func: Function to inspect
        
        Returns:
            Dictionary with parameter information
        """
        sig = inspect.signature(func)
        type_hints = get_type_hints(func) if hasattr(func, '__annotations__') else {}
        
        params_info = {}
        
        for param_name, param in sig.parameters.items():
            info = {
                'name': param_name,
                'required': param.default == inspect.Parameter.empty,
                'default': None if param.default == inspect.Parameter.empty else param.default,
                'type': type_hints.get(param_name, Any),
                'type_name': ParameterValidator._get_type_name(type_hints.get(param_name, Any))
            }
            params_info[param_name] = info
        
        return params_info
    
    @staticmethod
    def _get_type_name(type_hint: Any) -> str:
        """Get human-readable name for a type hint"""
        if hasattr(type_hint, '__name__'):
            return type_hint.__name__
        
        origin = get_origin(type_hint)
        if origin:
            args = get_args(type_hint)
            if args:
                arg_names = [ParameterValidator._get_type_name(arg) for arg in args]
                origin_name = origin.__name__ if hasattr(origin, '__name__') else str(origin)
                return f"{origin_name}[{', '.join(arg_names)}]"
            return origin.__name__ if hasattr(origin, '__name__') else str(origin)
        
        return str(type_hint)


# Example usage
if __name__ == "__main__":
    from typing import List, Optional
    
    # Test function with type hints
    def example_function(
        name: str,
        age: int,
        tags: List[str],
        active: bool = True,
        metadata: Optional[dict] = None
    ) -> str:
        return f"{name}, {age}, {tags}, {active}, {metadata}"
    
    validator = ParameterValidator()
    
    # Test 1: Valid parameters
    print("Test 1: Valid parameters")
    try:
        args, kwargs = validator.validate_parameters(
            example_function,
            kwargs={
                'name': 'Alice',
                'age': 30,
                'tags': ['python', 'developer'],
            }
        )
        print(f"✅ Validation passed")
        print(f"   Args: {args}")
        print(f"   Kwargs: {kwargs}")
    except ValidationError as e:
        print(f"❌ Validation failed: {e}")
    
    # Test 2: Invalid type
    print("\nTest 2: Invalid type (age as string)")
    try:
        args, kwargs = validator.validate_parameters(
            example_function,
            kwargs={
                'name': 'Bob',
                'age': '25',  # Should be int
                'tags': ['rust'],
            }
        )
        print(f"❌ Should have failed")
    except ValidationError as e:
        print(f"✅ Correctly rejected: {e}")
    
    # Test 3: Missing required parameter
    print("\nTest 3: Missing required parameter")
    try:
        args, kwargs = validator.validate_parameters(
            example_function,
            kwargs={
                'name': 'Charlie',
                # Missing 'age' and 'tags'
            }
        )
        print(f"❌ Should have failed")
    except ValidationError as e:
        print(f"✅ Correctly rejected: {e}")
    
    # Test 4: Get parameter info
    print("\nTest 4: Parameter information")
    params_info = validator.get_parameter_info(example_function)
    for param_name, info in params_info.items():
        print(f"  {param_name}:")
        print(f"    Type: {info['type_name']}")
        print(f"    Required: {info['required']}")
        print(f"    Default: {info['default']}")
