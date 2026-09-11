import sys
import os

def _get_py_indentation(line: str) -> int:
    """Calculates the leading whitespace of a string for Python."""
    return len(line) - len(line.lstrip(' '))

def _find_end_for_python(lines: list, start_line_index: int) -> int:
    """Finds the end line for a Python function."""
    start_line = start_line_index + 1
    
    # Find the first line of code to get the base indentation
    base_indent = -1
    for i in range(start_line_index + 1, len(lines)):
        line_content = lines[i].strip()
        if line_content and not line_content.startswith('#'):
            base_indent = _get_py_indentation(lines[i])
            break
    
    if base_indent == -1:
        return start_line

    initial_indent = _get_py_indentation(lines[start_line_index])
    if base_indent <= initial_indent:
         return start_line # It's a single-line function

    for i in range(start_line_index + 1, len(lines)):
        line = lines[i]
        if not line.strip() or line.strip().startswith('#'):
            continue
            
        current_indent = _get_py_indentation(line)
        
        if current_indent < base_indent and current_indent <= initial_indent:
            end_line_index = i - 1
            while end_line_index > start_line_index:
                if lines[end_line_index].strip():
                    return end_line_index + 1
                end_line_index -= 1
            return start_line

    end_line_index = len(lines) - 1
    while end_line_index > start_line_index:
        if lines[end_line_index].strip():
            return end_line_index + 1
        end_line_index -= 1
        
    return start_line

def _find_end_for_brace_based(lines: list, start_line_index: int, language: str) -> int:
    """Finds the end line for brace-based languages (Java, C, C++)."""
    brace_level = 0
    counting_started = False
    in_string = False
    in_char = False
    in_single_comment = False
    in_multi_comment = False
    i = start_line_index

    while i < len(lines):
        line = lines[i]
        j = 0
        in_single_comment = False  # Reset for each line
        
        while j < len(line):
            char = line[j]
            
            # Handle single-line comments
            if not in_string and not in_char and not in_multi_comment:
                if char == '/' and j + 1 < len(line) and line[j + 1] == '/':
                    in_single_comment = True
                    break  # Skip rest of line
                elif char == '/' and j + 1 < len(line) and line[j + 1] == '*':
                    in_multi_comment = True
                    j += 1  # Skip the '*'
                    j += 1
                    continue
            
            # Handle multi-line comment end
            if in_multi_comment:
                if char == '*' and j + 1 < len(line) and line[j + 1] == '/':
                    in_multi_comment = False
                    j += 1  # Skip the '/'
                j += 1
                continue
            
            # Skip if we're in any kind of comment
            if in_single_comment or in_multi_comment:
                j += 1
                continue
            
            # Handle string literals
            if char == '"' and not in_char:
                if not in_string:
                    in_string = True
                else:
                    # Check if it's escaped
                    escaped = False
                    k = j - 1
                    while k >= 0 and line[k] == '\\':
                        escaped = not escaped
                        k -= 1
                    if not escaped:
                        in_string = False
            
            # Handle character literals
            elif char == "'" and not in_string:
                if not in_char:
                    in_char = True
                else:
                    # Check if it's escaped
                    escaped = False
                    k = j - 1
                    while k >= 0 and line[k] == '\\':
                        escaped = not escaped
                        k -= 1
                    if not escaped:
                        in_char = False
            
            # Count braces only if not in string/char literals
            elif not in_string and not in_char:
                if char == '{':
                    if not counting_started:
                        counting_started = True
                    brace_level += 1
                elif char == '}':
                    brace_level -= 1
                    
                    # When the brace level returns to 0, we've found the end
                    if counting_started and brace_level == 0:
                        return i + 1
            
            j += 1
        
        i += 1

    # If we reach here without finding the end, there might be a brace mismatch
    if counting_started and brace_level != 0:
        print(f"Warning: Brace mismatch in {language} function. Expected closing braces.", file=sys.stderr)
    
    return -1

def _find_end_for_java(lines: list, start_line_index: int) -> int:
    """Finds the end line for a Java function using brace counting."""
    return _find_end_for_brace_based(lines, start_line_index, "Java")

def _find_end_for_c_cpp(lines: list, start_line_index: int) -> int:
    """Finds the end line for a C/C++ function using brace counting."""
    return _find_end_for_brace_based(lines, start_line_index, "C/C++")

def find_function_end_line(file_path: str, start_line: int) -> int:
    """
    Finds the end line number of a function for supported languages.

    Args:
        file_path: The path to the source file (.py, .java, .c, .cpp, .cc, .cxx, .h, .hpp).
        start_line: The line number where the function definition starts (1-indexed).

    Returns:
        The line number where the function ends.
        Returns -1 if an error occurs.
    """
    _, extension = os.path.splitext(file_path.lower())
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"Error: File not found at '{file_path}'", file=sys.stderr)
        return -1
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        return -1

    if not (0 < start_line <= len(lines)):
        print(f"Error: start_line {start_line} is out of bounds.", file=sys.stderr)
        return -1

    start_line_index = start_line - 1

    if extension == '.py':
        return _find_end_for_python(lines, start_line_index)
    elif extension == '.java':
        return _find_end_for_java(lines, start_line_index)
    elif extension in ['.c', '.cpp', '.cc', '.cxx', '.h', '.hpp']:
        return _find_end_for_c_cpp(lines, start_line_index)
    else:
        print(f"Error: Unsupported file type '{extension}'.", file=sys.stderr)
        return -1

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python function_end_finder.py <file_path> <start_line>")
        print("Supported file types: .py, .java, .c, .cpp, .cc, .cxx, .h, .hpp")
        sys.exit(1)
        
    file_path_arg = sys.argv[1]
    try:
        start_line_arg = int(sys.argv[2])
    except ValueError:
        print("Error: <start_line> must be an integer.", file=sys.stderr)
        sys.exit(1)
        
    end_line = find_function_end_line(file_path_arg, start_line_arg)
    
    if end_line != -1:
        print(f"The function in '{file_path_arg}' starting on line {start_line_arg} ends on line {end_line}.")