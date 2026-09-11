from pathlib import Path
from typing import List
from common.helper import get_customize_op_query


def _escape_codeql_string_literal(value: str) -> str:
    """Escape an arbitrary regex for safe inclusion in a CodeQL string literal."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def gen_callsite_query(calls: List[str], language: str, appname: str):
    """this is for additional callsites op"""

    from common.helper import get_template_op_query
    template_path = get_template_op_query(language)
    
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")
    
    with open(template_path, 'r') as f:
        template_content = f.read()
    
    if language.lower() == "java":
        query_content = _gen_callsite_java(calls, template_content)

    elif language.lower() == "python":
        query_content = _gen_callsite_python(calls, template_content)

    elif language.lower() == "go":
        query_content = _gen_callsite_go(calls, template_content)
    
    elif language.lower() in ["javascript", "js"]:
        query_content = _gen_callsite_javascript(calls, template_content)
    
    elif language.lower() in ["typescript", "ts"]:
        query_content = _gen_callsite_typescript(calls, template_content)

    elif language.lower() in ["csharp", "c#", "cs"]:
        query_content = _gen_callsite_csharp(calls, template_content)

    elif language.lower() in ["cpp", "c++"]:
        query_content = _gen_callsite_cpp(calls, template_content)

    else:
        raise ValueError(f"Unsupported language: {language}")

    output_file = get_customize_op_query(language, appname)
    output_file.write_text(query_content)
    
    # print(f"Callsite query generated: {output_file}")
    return output_file

def _gen_callsite_java(calls: List[str], template_content: str) -> str:
    """Generate Java callsite query using template."""
    
    # Create method name conditions using regex match
    method_conditions = []
    for call in calls:
        escaped_call = _escape_codeql_string_literal(call)
        method_conditions.append(
            f'call.getMethod().getName().toLowerCase().regexpMatch("{escaped_call}")'
        )
    
    method_checks = " or\n  ".join(method_conditions)
    
    # Replace the single placeholder
    query_content = template_content.replace("{{REGEX_PATTERNS}}", method_checks)
    
    return query_content

def _gen_callsite_python(calls: List[str], template_content: str) -> str:
    """Generate Python callsite query using template."""
    
    # Create function name conditions using regex match
    function_conditions = []
    for call in calls:
        escaped_call = _escape_codeql_string_literal(call)
        function_conditions.append(
            f'call.getFunc().(Name).getId().toLowerCase().regexpMatch("{escaped_call}")'
        )
    
    function_checks = " or\n    ".join(function_conditions)
    
    # Replace the single placeholder
    query_content = template_content.replace("{{REGEX_PATTERNS}}", function_checks)
    
    return query_content

def _gen_callsite_go(calls: List[str], template_content: str) -> str:
    """Generate Go callsite query using template."""
    
    # Create function name conditions using regex match
    function_conditions = []
    for call in calls:
        # For Go, use getTarget().getName() to get the called function name
        escaped_call = _escape_codeql_string_literal(call)
        function_conditions.append(
            f'call.getTarget().getName().toLowerCase().regexpMatch("{escaped_call}")'
        )
    
    function_checks = " or\n    ".join(function_conditions)
    
    # Replace the single placeholder
    query_content = template_content.replace("{{REGEX_PATTERNS}}", function_checks)
    
    return query_content

def _gen_callsite_javascript(calls: List[str], template_content: str) -> str:
    """Generate JavaScript callsite query using template."""
    
    # Create function name conditions using regex match
    function_conditions = []
    for call in calls:
        # For JavaScript, use getCalleeName() to get the called function name
        escaped_call = _escape_codeql_string_literal(call)
        function_conditions.append(
            f'call.getCalleeName().toLowerCase().regexpMatch("{escaped_call}")'
        )
    
    function_checks = " or\n    ".join(function_conditions)
    
    # Replace the single placeholder
    query_content = template_content.replace("{{REGEX_PATTERNS}}", function_checks)
    
    return query_content

def _gen_callsite_csharp(calls: List[str], template_content: str) -> str:
    """Generate C# callsite query using template."""

    function_conditions = []
    for call in calls:
        escaped_call = _escape_codeql_string_literal(call)
        function_conditions.append(
            f'call.getTarget().getName().toLowerCase().regexpMatch("{escaped_call}")'
        )

    function_checks = " or\n    ".join(function_conditions)

    query_content = template_content.replace("{{REGEX_PATTERNS}}", function_checks)

    return query_content


def _gen_callsite_typescript(calls: List[str], template_content: str) -> str:
    """Generate TypeScript callsite query using template."""
    
    # Create function name conditions using regex match
    function_conditions = []
    for call in calls:
        # For TypeScript, use getCalleeName() to get the called function name
        escaped_call = _escape_codeql_string_literal(call)
        function_conditions.append(
            f'call.getCalleeName().toLowerCase().regexpMatch("{escaped_call}")'
        )
    
    function_checks = " or\n    ".join(function_conditions)
    
    # Replace the single placeholder
    query_content = template_content.replace("{{REGEX_PATTERNS}}", function_checks)
    
    return query_content


def _gen_callsite_cpp(calls: List[str], template_content: str) -> str:
    """Generate C++ callsite query using template."""
    function_conditions = []
    for call in calls:
        function_conditions.append(
            f'call.getTarget().getName().toLowerCase().matches("{call}")'
        )
    function_checks = " or\n    ".join(function_conditions)
    return template_content.replace("{{REGEX_PATTERNS}}", function_checks)
