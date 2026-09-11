#!/usr/bin/env python3
"""
CodeQL-based Function Mapper

Replaces tree-sitter parsing with CodeQL query results for accurate function extraction.
Maintains same API as function_mapper.py for drop-in replacement.
"""

import csv
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class EnhancedFunction:
    """Enhanced function info matching function_mapper.py structure"""
    name: str
    start_line: int  # Includes decorators/annotations
    end_line: int
    signature: str
    file_path: Path
    function_def_line: int  # Actual function definition line
    class_name: Optional[str] = None
    namespace_name: Optional[str] = None
    package_name: Optional[str] = None
    decorators: List[str] = field(default_factory=list)

    @property
    def function_id(self) -> str:
        """Create function ID based on function definition line"""
        return f"{self.name}@{self.file_path}:{self.function_def_line}"

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON/database storage"""
        return {
            'function_id': self.function_id,
            'name': self.name,
            'start_line': self.start_line,
            'end_line': self.end_line,
            'function_def_line': self.function_def_line,
            'signature': self.signature,
            'file_path': str(self.file_path),
            'class_name': self.class_name,
            'namespace_name': self.namespace_name,
            'package_name': self.package_name,
            'decorators': self.decorators
        }


@dataclass
class EnhancedClass:
    """Enhanced class info for DTOs, entities, forms, etc."""
    name: str
    start_line: int  # Includes annotations
    end_line: int
    file_path: Path
    package_name: Optional[str] = None
    annotations: List[str] = field(default_factory=list)
    fields: List[Dict[str, str]] = field(default_factory=list)  # [{"name": "fieldName", "type": "String"}]

    @property
    def class_id(self) -> str:
        """Create class ID based on start line"""
        return f"{self.name}@{self.file_path}:{self.start_line}"

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON/database storage"""
        return {
            'class_id': self.class_id,
            'name': self.name,
            'start_line': self.start_line,
            'end_line': self.end_line,
            'file_path': str(self.file_path),
            'package_name': self.package_name,
            'annotations': self.annotations,
            'fields': self.fields
        }


class CodeQLFunctionMapper:
    """Extract functions using CodeQL queries"""

    def __init__(self, codeql_db_path: Path, codeql_bin: str = "codeql"):
        self.codeql_db_path = Path(codeql_db_path)
        self.codeql_bin = codeql_bin

    def extract_functions(self, query_path: Path, language: str = "java") -> List[EnhancedFunction]:
        """
        Run CodeQL query and parse results

        Args:
            query_path: Path to .ql query file
            language: Programming language (java, python, cpp, etc.)

        Returns:
            List of EnhancedFunction objects
        """
        # Run CodeQL query
        output_csv = self._run_codeql_query(query_path)

        # Parse CSV output
        functions = self._parse_codeql_csv(output_csv, language)

        return functions

    def _run_codeql_query(self, query_path: Path) -> Path:
        """Execute CodeQL query and return output path"""
        import tempfile
        import os

        # Create temp directory for output
        output_dir = Path(tempfile.mkdtemp(prefix="codeql_output_"))
        output_csv = output_dir / "functions.csv"

        cmd = [
            self.codeql_bin,
            "database", "analyze",
            str(self.codeql_db_path),
            str(query_path),
            "--format=csv",
            "--output", str(output_csv),
            "--rerun"  # Force fresh evaluation
        ]

        # Suppress CodeQL warnings about installation location
        env = os.environ.copy()
        env['CODEQL_ALLOW_INSTALLATION_ANYWHERE'] = 'true'

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env
        )

        if result.returncode != 0:
            raise RuntimeError(f"CodeQL query failed: {result.stderr}")

        if not output_csv.exists():
            raise RuntimeError(f"CodeQL output file not created: {output_csv}")

        return output_csv

    def _parse_codeql_csv(self, csv_path: Path, language: str) -> List[EnhancedFunction]:
        """
        Parse CodeQL CSV output into EnhancedFunction objects

        CodeQL CSV format has query metadata in first 3 columns,
        then file path and location info. The pipe-delimited data is in column 4.
        """
        functions = []

        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)

            for row in reader:
                if len(row) < 4:
                    continue

                # Column 4 contains our pipe-delimited data
                data_str = row[3]

                try:
                    func = self._parse_function_data(data_str, language)
                    if func and self._is_valid_function(func, language):
                        functions.append(func)
                except Exception as e:
                    # Log parsing errors but continue
                    print(f"Warning: Failed to parse function data: {data_str[:100]}... Error: {e}")
                    continue

        return functions

    def _parse_function_data(self, data_str: str, language: str) -> Optional[EnhancedFunction]:
        """
        Parse pipe-delimited function data

        Format: function_id|name|file|start|end|signature|class|package|annotations
        """
        parts = data_str.split('|')

        if len(parts) < 9:
            return None

        function_id = parts[0]
        name = parts[1]
        file_path = parts[2]
        start_line = parts[3]
        end_line = parts[4]
        signature = parts[5]
        class_name = parts[6] if parts[6] else None
        package_name = parts[7]
        annotations_str = parts[8]

        # Parse annotations
        decorators = []
        if annotations_str:
            decorators = [a.strip() for a in annotations_str.split(',') if a.strip()]

        try:
            start_line_int = int(start_line)
            end_line_int = int(end_line)
        except ValueError:
            return None

        return EnhancedFunction(
            name=name,
            start_line=start_line_int,
            end_line=end_line_int,
            signature=signature,
            file_path=Path(file_path),
            function_def_line=start_line_int,  # CodeQL start_line already includes annotations
            class_name=class_name,
            package_name=package_name,
            decorators=decorators
        )

    def _is_valid_function(self, func: EnhancedFunction, language: str) -> bool:
        """
        Filter out noise; dispatch to language-specific validators.

        Args:
            func: EnhancedFunction to validate
            language: Programming language

        Returns:
            True if function should be included
        """
        if not func.name or func.name.isspace():
            return False
        if func.start_line <= 0:
            return False
        if func.end_line < func.start_line:
            print(f"Warning: Invalid line range for {func.name}: start={func.start_line}, end={func.end_line}")
            return False
        if language == "java":
            return self._is_valid_java(func)
        if language == "python":
            return self._is_valid_python(func)
        if language == "csharp":
            return self._is_valid_csharp(func)
        if language == "go":
            return self._is_valid_go(func)
        if language in ("cpp", "c++"):
            return self._is_valid_cpp(func)
        return True

    def _is_valid_java(self, func: EnhancedFunction) -> bool:
        """Java-specific validation: reject lambdas, compiler-generated names, empty package."""
        if func.name in ['apply', 'accept', 'test', 'get']:
            if not func.class_name or not func.file_path.stem.endswith(func.class_name):
                return False
        if func.name.startswith('<') and func.name not in ('<init>', '<clinit>'):
            return False
        if not func.package_name:
            return False
        if func.end_line - func.start_line < 2:
            print(f"Info: Small line range for {func.name} in {func.file_path}: {func.start_line}-{func.end_line}")
        return True

    def _is_valid_python(self, func: EnhancedFunction) -> bool:
        """Python-specific validation: reject module-level noise dunders; allow empty package."""
        python_dunder_denylist = {
            '__module__', '__qualname__', '__dict__', '__doc__', '__weakref__'
        }
        if func.name in python_dunder_denylist:
            return False
        return True

    def _is_valid_csharp(self, func: EnhancedFunction) -> bool:
        """C# validation: reject compiler-generated names.

        Does NOT require a namespace: top-level statements and minimal APIs
        (the modern, now-default template for a small ASP.NET Core service)
        routinely have no `namespace` declaration at all, and the implicit
        one is empty -- requiring a namespace silently dropped every
        function in exactly that style of app.
        """
        if '<' in func.name and '>' in func.name:
            return False
        return True

    def _is_valid_go(self, func: EnhancedFunction) -> bool:
        """Go: require a package; reject blank identifier."""
        if func.name == '_':
            return False
        if not func.package_name:
            return False
        return True

    def _is_valid_cpp(self, func: EnhancedFunction) -> bool:
        """C++: allow empty namespace (global scope); reject compiler internals."""
        if func.name.startswith('__'):
            return False
        return True


def extract_java_functions(codebase_path: Path, codeql_db_path: Path, codeql_bin: str = "codeql") -> Dict[str, EnhancedFunction]:
    """
    Main entry point - extract Java functions using CodeQL

    Maintains same API as function_mapper.py for drop-in replacement.

    Args:
        codebase_path: Path to source code (not used, but kept for API compatibility)
        codeql_db_path: Path to CodeQL database
        codeql_bin: Path to codeql binary (default: "codeql" from PATH)

    Returns:
        Dict mapping function_id to EnhancedFunction
    """
    mapper = CodeQLFunctionMapper(codeql_db_path, codeql_bin)

    # Determine query path - look in queries/java/
    query_path = Path(__file__).parent.parent.parent / "queries" / "java" / "functions.ql"

    if not query_path.exists():
        raise FileNotFoundError(f"CodeQL query not found: {query_path}")

    print(f"Running CodeQL query: {query_path}")
    print(f"CodeQL database: {codeql_db_path}")

    functions = mapper.extract_functions(query_path, language="java")

    print(f"Extracted {len(functions)} Java functions from CodeQL")

    # Convert to dict by function_id
    function_dict = {}
    duplicates = 0

    for func in functions:
        if func.function_id in function_dict:
            duplicates += 1
            # Keep the first one (could implement smarter de-duplication if needed)
            continue
        function_dict[func.function_id] = func

    if duplicates > 0:
        print(f"Warning: Found {duplicates} duplicate function_ids (kept first occurrence)")

    return function_dict


def extract_python_functions(codebase_path: Path, codeql_db_path: Path, codeql_bin: str = "codeql") -> Dict[str, EnhancedFunction]:
    """
    Extract Python functions using CodeQL.

    Args:
        codebase_path: Path to source code (kept for API compatibility)
        codeql_db_path: Path to CodeQL database
        codeql_bin: Path to codeql binary (default: "codeql" from PATH)

    Returns:
        Dict mapping function_id to EnhancedFunction
    """
    mapper = CodeQLFunctionMapper(codeql_db_path, codeql_bin)

    query_path = Path(__file__).parent.parent.parent / "queries" / "python" / "functions.ql"
    if not query_path.exists():
        raise FileNotFoundError(f"CodeQL query not found: {query_path}")

    print(f"Running CodeQL query: {query_path}")
    print(f"CodeQL database: {codeql_db_path}")

    functions = mapper.extract_functions(query_path, language="python")
    print(f"Extracted {len(functions)} Python functions from CodeQL")

    function_dict = {}
    duplicates = 0
    for func in functions:
        if func.function_id in function_dict:
            duplicates += 1
            continue
        function_dict[func.function_id] = func

    if duplicates > 0:
        print(f"Warning: Found {duplicates} duplicate function_ids (kept first occurrence)")

    return function_dict


def extract_python_classes(codebase_path: Path, codeql_db_path: Path, codeql_bin: str = "codeql") -> Dict[str, EnhancedClass]:
    """
    Extract Python classes using CodeQL.

    Args:
        codebase_path: Path to source code (kept for API compatibility)
        codeql_db_path: Path to CodeQL database
        codeql_bin: Path to codeql binary

    Returns:
        Dict mapping class_id to EnhancedClass
    """
    mapper = CodeQLFunctionMapper(codeql_db_path, codeql_bin)

    query_path = Path(__file__).parent.parent.parent / "queries" / "python" / "classes.ql"
    if not query_path.exists():
        raise FileNotFoundError(f"CodeQL query not found: {query_path}")

    print(f"Running CodeQL class query: {query_path}")
    print(f"CodeQL database: {codeql_db_path}")

    output_csv = mapper._run_codeql_query(query_path)
    classes = _parse_class_csv(output_csv)
    print(f"Extracted {len(classes)} Python classes from CodeQL")

    class_dict = {}
    duplicates = 0
    for clazz in classes:
        if clazz.class_id in class_dict:
            duplicates += 1
            continue
        class_dict[clazz.class_id] = clazz

    if duplicates > 0:
        print(f"Warning: Found {duplicates} duplicate class_ids (kept first occurrence)")

    return class_dict


def extract_csharp_functions(codebase_path: Path, codeql_db_path: Path, codeql_bin: str = "codeql") -> Dict[str, EnhancedFunction]:
    """
    Extract C# functions using CodeQL.

    Args:
        codebase_path: Path to source code (kept for API compatibility)
        codeql_db_path: Path to CodeQL database
        codeql_bin: Path to codeql binary

    Returns:
        Dict mapping function_id to EnhancedFunction
    """
    mapper = CodeQLFunctionMapper(codeql_db_path, codeql_bin)

    query_path = Path(__file__).parent.parent.parent / "queries" / "csharp" / "functions.ql"
    if not query_path.exists():
        raise FileNotFoundError(f"CodeQL query not found: {query_path}")

    print(f"Running CodeQL query: {query_path}")
    print(f"CodeQL database: {codeql_db_path}")

    functions = mapper.extract_functions(query_path, language="csharp")
    print(f"Extracted {len(functions)} C# functions from CodeQL")

    function_dict = {}
    duplicates = 0
    for func in functions:
        if func.function_id in function_dict:
            duplicates += 1
            continue
        function_dict[func.function_id] = func

    if duplicates > 0:
        print(f"Warning: Found {duplicates} duplicate function_ids (kept first occurrence)")

    return function_dict


def extract_csharp_classes(codebase_path: Path, codeql_db_path: Path, codeql_bin: str = "codeql") -> Dict[str, EnhancedClass]:
    """
    Extract C# classes using CodeQL.

    Args:
        codebase_path: Path to source code (kept for API compatibility)
        codeql_db_path: Path to CodeQL database
        codeql_bin: Path to codeql binary

    Returns:
        Dict mapping class_id to EnhancedClass
    """
    mapper = CodeQLFunctionMapper(codeql_db_path, codeql_bin)

    query_path = Path(__file__).parent.parent.parent / "queries" / "csharp" / "classes.ql"
    if not query_path.exists():
        raise FileNotFoundError(f"CodeQL query not found: {query_path}")

    print(f"Running CodeQL class query: {query_path}")
    print(f"CodeQL database: {codeql_db_path}")

    output_csv = mapper._run_codeql_query(query_path)
    classes = _parse_class_csv(output_csv)
    print(f"Extracted {len(classes)} C# classes from CodeQL")

    class_dict = {}
    duplicates = 0
    for clazz in classes:
        if clazz.class_id in class_dict:
            duplicates += 1
            continue
        class_dict[clazz.class_id] = clazz

    if duplicates > 0:
        print(f"Warning: Found {duplicates} duplicate class_ids (kept first occurrence)")

    return class_dict


def extract_go_functions(
    codebase_path: Path,
    codeql_db_path: Path,
    codeql_bin: str = "codeql",
) -> Dict[str, EnhancedFunction]:
    """Extract Go functions using CodeQL."""
    mapper = CodeQLFunctionMapper(codeql_db_path, codeql_bin)

    query_path = Path(__file__).parent.parent.parent / "queries" / "go" / "functions.ql"
    if not query_path.exists():
        raise FileNotFoundError(f"CodeQL query not found: {query_path}")

    print(f"Running CodeQL query: {query_path}")
    print(f"CodeQL database: {codeql_db_path}")

    functions = mapper.extract_functions(query_path, language="go")
    print(f"Extracted {len(functions)} Go functions from CodeQL")

    function_dict: Dict[str, EnhancedFunction] = {}
    duplicates = 0
    for func in functions:
        if func.function_id in function_dict:
            duplicates += 1
            continue
        function_dict[func.function_id] = func

    if duplicates > 0:
        print(f"Warning: Found {duplicates} duplicate function_ids (kept first occurrence)")

    return function_dict


def extract_javascript_functions(
    codebase_path: Path,
    codeql_db_path: Path,
    codeql_bin: str = "codeql",
) -> Dict[str, EnhancedFunction]:
    """Extract JavaScript / TypeScript functions using CodeQL."""
    mapper = CodeQLFunctionMapper(codeql_db_path, codeql_bin)

    query_path = Path(__file__).parent.parent.parent / "queries" / "javascript" / "functions.ql"
    if not query_path.exists():
        raise FileNotFoundError(f"CodeQL query not found: {query_path}")

    print(f"Running CodeQL query: {query_path}")
    print(f"CodeQL database: {codeql_db_path}")

    functions = mapper.extract_functions(query_path, language="javascript")
    print(f"Extracted {len(functions)} JavaScript functions from CodeQL")

    function_dict: Dict[str, EnhancedFunction] = {}
    for func in functions:
        function_dict.setdefault(func.function_id, func)
    return function_dict


def extract_javascript_classes(
    codebase_path: Path,
    codeql_db_path: Path,
    codeql_bin: str = "codeql",
) -> Dict[str, EnhancedClass]:
    """Extract JavaScript / TypeScript classes using CodeQL."""
    mapper = CodeQLFunctionMapper(codeql_db_path, codeql_bin)

    query_path = Path(__file__).parent.parent.parent / "queries" / "javascript" / "classes.ql"
    if not query_path.exists():
        raise FileNotFoundError(f"CodeQL query not found: {query_path}")

    print(f"Running CodeQL class query: {query_path}")
    output_csv = mapper._run_codeql_query(query_path)
    classes = _parse_class_csv(output_csv)
    print(f"Extracted {len(classes)} JavaScript classes from CodeQL")

    class_dict: Dict[str, EnhancedClass] = {}
    for clazz in classes:
        class_dict.setdefault(clazz.class_id, clazz)
    return class_dict


def extract_cpp_functions(
    codebase_path: Path,
    codeql_db_path: Path,
    codeql_bin: str = "codeql",
) -> Dict[str, EnhancedFunction]:
    """Extract C++ functions using CodeQL."""
    mapper = CodeQLFunctionMapper(codeql_db_path, codeql_bin)

    query_path = Path(__file__).parent.parent.parent / "queries" / "cpp" / "functions.ql"
    if not query_path.exists():
        raise FileNotFoundError(f"CodeQL query not found: {query_path}")

    print(f"Running CodeQL query: {query_path}")
    print(f"CodeQL database: {codeql_db_path}")

    functions = mapper.extract_functions(query_path, language="cpp")
    print(f"Extracted {len(functions)} C++ functions from CodeQL")

    function_dict: Dict[str, EnhancedFunction] = {}
    duplicates = 0
    for func in functions:
        if func.function_id in function_dict:
            duplicates += 1
            continue
        function_dict[func.function_id] = func

    if duplicates > 0:
        print(f"Warning: Found {duplicates} duplicate function_ids (kept first occurrence)")

    return function_dict


def extract_java_classes(codebase_path: Path, codeql_db_path: Path, codeql_bin: str = "codeql") -> Dict[str, EnhancedClass]:
    """
    Extract Java classes (DTOs, entities, forms) using CodeQL

    Args:
        codebase_path: Path to source code (not used, but kept for API compatibility)
        codeql_db_path: Path to CodeQL database
        codeql_bin: Path to codeql binary (default: "codeql" from PATH)

    Returns:
        Dict mapping class_id to EnhancedClass
    """
    mapper = CodeQLFunctionMapper(codeql_db_path, codeql_bin)

    # Determine query path - look in queries/java/
    query_path = Path(__file__).parent.parent.parent / "queries" / "java" / "classes.ql"

    if not query_path.exists():
        raise FileNotFoundError(f"CodeQL query not found: {query_path}")

    print(f"Running CodeQL class query: {query_path}")
    print(f"CodeQL database: {codeql_db_path}")

    # Run query
    output_csv = mapper._run_codeql_query(query_path)

    # Parse CSV output
    classes = _parse_class_csv(output_csv)

    print(f"Extracted {len(classes)} Java classes from CodeQL")

    # Convert to dict by class_id
    class_dict = {}
    duplicates = 0

    for clazz in classes:
        if clazz.class_id in class_dict:
            duplicates += 1
            continue
        class_dict[clazz.class_id] = clazz

    if duplicates > 0:
        print(f"Warning: Found {duplicates} duplicate class_ids (kept first occurrence)")

    return class_dict


def _parse_class_csv(csv_path: Path) -> List[EnhancedClass]:
    """
    Parse CodeQL CSV output for classes

    CSV format: class_id|name|file|start|end|package|annotations|fields
    """
    classes = []

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)

        for row in reader:
            if len(row) < 4:
                continue

            # Column 4 contains our pipe-delimited data
            data_str = row[3]

            try:
                clazz = _parse_class_data(data_str)
                if clazz:
                    classes.append(clazz)
            except Exception as e:
                print(f"Warning: Failed to parse class data: {data_str[:100]}... Error: {e}")
                continue

    return classes


def _parse_class_data(data_str: str) -> Optional[EnhancedClass]:
    """
    Parse pipe-delimited class data

    Format: class_id|name|file|start|end|package|annotations|fields
    """
    parts = data_str.split('|')

    if len(parts) < 8:
        return None

    class_id = parts[0]
    name = parts[1]
    file_path = parts[2]
    start_line = parts[3]
    end_line = parts[4]
    package_name = parts[5]
    annotations_str = parts[6]
    fields_str = parts[7]

    # Parse annotations
    annotations = []
    if annotations_str:
        annotations = [a.strip() for a in annotations_str.split(',') if a.strip()]

    # Parse fields (format: "fieldName:FieldType,fieldName2:FieldType2")
    fields = []
    if fields_str:
        for field_spec in fields_str.split(','):
            if ':' in field_spec:
                field_name, field_type = field_spec.split(':', 1)
                fields.append({
                    'name': field_name.strip(),
                    'type': field_type.strip()
                })

    try:
        start_line_int = int(start_line)
        end_line_int = int(end_line)
    except ValueError:
        return None

    return EnhancedClass(
        name=name,
        start_line=start_line_int,
        end_line=end_line_int,
        file_path=Path(file_path),
        package_name=package_name if package_name else None,
        annotations=annotations,
        fields=fields
    )


def build_enhanced_function_mapping_codeql(source_root: Path, codeql_db_path: Path, language: str = "java"):
    """
    Build enhanced function mapping using CodeQL (drop-in replacement for tree-sitter version)

    This provides the same API as function_mapper.build_enhanced_function_mapping()
    but uses CodeQL for extraction instead of tree-sitter.

    Args:
        source_root: Path to source code (for compatibility, but CodeQL db is used)
        codeql_db_path: Path to CodeQL database
        language: Programming language (default: java)

    Returns:
        OptimizedFunctionIndex compatible with existing code
    """
    from .function_index import OptimizedFunctionIndex

    print(f"Building enhanced function mapping using CodeQL for: {source_root}")
    print(f"CodeQL database: {codeql_db_path}")

    # Extract functions using CodeQL
    if language == "java":
        functions_dict = extract_java_functions(source_root, codeql_db_path)
    elif language == "python":
        functions_dict = extract_python_functions(source_root, codeql_db_path)
    elif language == "go":
        functions_dict = extract_go_functions(source_root, codeql_db_path)
    elif language == "cpp" or language == "c++":
        functions_dict = extract_cpp_functions(source_root, codeql_db_path)
    elif language == "csharp":
        functions_dict = extract_csharp_functions(source_root, codeql_db_path)
    elif language == "javascript":
        functions_dict = extract_javascript_functions(source_root, codeql_db_path)
    else:
        raise ValueError(f"Unsupported language: {language}")

    # Convert to OptimizedFunctionIndex format
    index = OptimizedFunctionIndex()

    # Add all functions to index
    functions_list = list(functions_dict.values())
    index.add_functions(functions_list)

    print(f"Built function index: {len(index.functions)} functions")

    return index


if __name__ == "__main__":
    # Quick test
    import sys

    if len(sys.argv) < 2:
        print("Usage: python codeql_function_mapper.py <codeql_db_path>")
        sys.exit(1)

    db_path = Path(sys.argv[1])
    codebase_path = db_path.parent.parent / "codebases" / db_path.parent.name

    print(f"Testing CodeQL function extraction...")
    print(f"Database: {db_path}")
    print(f"Codebase: {codebase_path}")
    print()

    functions = extract_java_functions(codebase_path, db_path)

    print(f"\nTotal functions: {len(functions)}")
    print("\nSample functions:")
    for i, (fid, func) in enumerate(list(functions.items())[:10]):
        print(f"  {i+1}. {fid}")
        print(f"     Class: {func.class_name}")
        print(f"     Signature: {func.signature}")
        if func.decorators:
            print(f"     Annotations: {', '.join(func.decorators)}")
        print()
