#!/usr/bin/env python3
"""
Call Graph Database
File: callgraph_database.py

Create and manage three-table call graph database:
1. Function definitions: function_id -> function_info
2. Call resolutions: callsite_id -> target_function_id
3. Router definitions: function_id -> router_info
"""

import json
import re
import duckdb
import pandas as pd
from typing import Dict, Optional, List
from pathlib import Path
from common.helper import get_app_function_map_file, get_app_callsite_json_file, get_app_decorator_json_file, get_app_duckdb_file, get_app_classes_json_file, get_database_language
from .codeql_function_mapper import (
    build_enhanced_function_mapping_codeql,
    extract_java_classes,
    extract_python_classes,
    extract_csharp_classes,
    extract_javascript_classes,
)
from .callsite_extractor import execute_callsite_resolution_query, extract_callsite_resolutions
from .decorator_extractor import execute_decorator_resolution_query, extract_decorator_resolutions

class CallGraphDatabase:
    """Three-table call graph database with DuckDB"""
    
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.conn = duckdb.connect(str(self.db_path))
        self._create_schema()
    
    def _create_schema(self):
        """Create three independent tables"""
        self.conn.execute("""
        -- Table 1: Function Definitions
        CREATE TABLE IF NOT EXISTS function_definitions (
            function_id VARCHAR PRIMARY KEY,
            name VARCHAR NOT NULL,
            file_path VARCHAR NOT NULL,
            start_line INTEGER NOT NULL,
            end_line INTEGER NOT NULL,
            signature TEXT,
            class_name VARCHAR,
            package_name VARCHAR
        );
        
        -- Table 2: Call Site Resolutions
        CREATE TABLE IF NOT EXISTS call_resolutions (
            callsite_id VARCHAR PRIMARY KEY,
            target_function_id VARCHAR NOT NULL
        );
        
        -- Table 3: Router Definitions
        CREATE TABLE IF NOT EXISTS router_definitions (
            function_id VARCHAR PRIMARY KEY,
            router_definition_id VARCHAR NOT NULL,
            router_source_code TEXT
        );

        -- Table 4: Class Definitions (DTOs, entities, forms)
        CREATE TABLE IF NOT EXISTS class_definitions (
            class_id VARCHAR PRIMARY KEY,
            name VARCHAR NOT NULL,
            file_path VARCHAR NOT NULL,
            start_line INTEGER NOT NULL,
            end_line INTEGER NOT NULL,
            package_name VARCHAR,
            annotations TEXT,  -- JSON array of annotation names
            fields TEXT        -- JSON array of field definitions
        );
        """)

        # Create indexes for fast lookups
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_func_name ON function_definitions(name)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_func_file ON function_definitions(file_path)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_callsite ON call_resolutions(callsite_id)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_target ON call_resolutions(target_function_id)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_router_func ON router_definitions(function_id)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_class_name ON class_definitions(name)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_class_file ON class_definitions(file_path)")
    
    def load_function_definitions(self, functions_json_file: Path):
        """Load function definitions from JSON file"""
        functions_json_file = Path(functions_json_file)
        
        with open(functions_json_file, 'r') as f:
            data = json.load(f)
        
        function_definitions = data.get('function_definitions', {})
        
        if not function_definitions:
            print("No function definitions found in JSON")
            return
        
        # Convert to list of records for insertion
        records = []
        for func_id, func_info in function_definitions.items():
            records.append({
                'function_id': func_id,
                'name': func_info.get('name', ''),
                'file_path': func_info.get('file_path', ''),
                'start_line': func_info.get('start_line', 0),
                'end_line': func_info.get('end_line', 0),
                'signature': func_info.get('signature', ''),
                'class_name': func_info.get('class_name'),
                'package_name': func_info.get('package_name')
            })
        
        # Bulk insert
        df = pd.DataFrame(records)
        self.conn.register('temp_functions', df)
        
        self.conn.execute("""
            INSERT INTO function_definitions 
            SELECT * FROM temp_functions
            ON CONFLICT (function_id) DO UPDATE SET
                name = EXCLUDED.name,
                file_path = EXCLUDED.file_path,
                start_line = EXCLUDED.start_line,
                end_line = EXCLUDED.end_line,
                signature = EXCLUDED.signature,
                class_name = EXCLUDED.class_name,
                package_name = EXCLUDED.package_name
        """)
        
        self.conn.unregister('temp_functions')
    
    def load_call_resolutions(self, calls_json_file: Path):
        """Load call resolutions from JSON file"""
        calls_json_file = Path(calls_json_file)
        
        with open(calls_json_file, 'r') as f:
            data = json.load(f)
        
        call_resolutions = data.get('call_resolutions', {})
        
        if not call_resolutions:
            print("No call resolutions found in JSON")
            return
        
        # Convert to list of records
        records = []
        for callsite_id, target_function_id in call_resolutions.items():
            records.append({
                'callsite_id': callsite_id,
                'target_function_id': target_function_id
            })
        
        # Bulk insert
        df = pd.DataFrame(records)
        self.conn.register('temp_calls', df)
        
        self.conn.execute("""
            INSERT INTO call_resolutions 
            SELECT * FROM temp_calls
            ON CONFLICT (callsite_id) DO UPDATE SET
                target_function_id = EXCLUDED.target_function_id
        """)
        
        self.conn.unregister('temp_calls')
    
    def load_router_definitions(self, routers_json_file: Path):
        """Load router definitions from JSON file"""
        routers_json_file = Path(routers_json_file)
        
        if not routers_json_file.exists():
            print(f"Router definitions file not found: {routers_json_file}")
            return
        
        with open(routers_json_file, 'r') as f:
            data = json.load(f)
        
        function_to_router = data.get('function_to_router', {})
        router_definitions = data.get('router_definitions', {})
        
        if not function_to_router:
            print("No router mappings found in JSON")
            return
        
        # Convert to list of records
        records = []
        for function_id, router_definition_id in function_to_router.items():
            router_source_code = router_definitions.get(router_definition_id, '')
            records.append({
                'function_id': function_id,
                'router_definition_id': router_definition_id,
                'router_source_code': router_source_code
            })
        
        # Bulk insert
        df = pd.DataFrame(records)
        self.conn.register('temp_routers', df)
        
        self.conn.execute("""
            INSERT INTO router_definitions 
            SELECT * FROM temp_routers
            ON CONFLICT (function_id) DO UPDATE SET
                router_definition_id = EXCLUDED.router_definition_id,
                router_source_code = EXCLUDED.router_source_code
        """)
        
        self.conn.unregister('temp_routers')
        print(f"Loaded {len(records)} router definitions")

    def load_class_definitions(self, classes_json_file: Path):
        """Load class definitions from JSON file"""
        classes_json_file = Path(classes_json_file)

        if not classes_json_file.exists():
            print(f"Class definitions file not found: {classes_json_file}")
            return

        with open(classes_json_file, 'r') as f:
            data = json.load(f)

        class_definitions = data.get('class_definitions', {})

        if not class_definitions:
            print("No class definitions found in JSON")
            return

        # Convert to list of records
        records = []
        for class_id, class_info in class_definitions.items():
            records.append({
                'class_id': class_id,
                'name': class_info.get('name', ''),
                'file_path': class_info.get('file_path', ''),
                'start_line': class_info.get('start_line', 0),
                'end_line': class_info.get('end_line', 0),
                'package_name': class_info.get('package_name'),
                'annotations': json.dumps(class_info.get('annotations', [])),
                'fields': json.dumps(class_info.get('fields', []))
            })

        # Bulk insert
        df = pd.DataFrame(records)
        self.conn.register('temp_classes', df)

        self.conn.execute("""
            INSERT INTO class_definitions
            SELECT * FROM temp_classes
            ON CONFLICT (class_id) DO UPDATE SET
                name = EXCLUDED.name,
                file_path = EXCLUDED.file_path,
                start_line = EXCLUDED.start_line,
                end_line = EXCLUDED.end_line,
                package_name = EXCLUDED.package_name,
                annotations = EXCLUDED.annotations,
                fields = EXCLUDED.fields
        """)

        self.conn.unregister('temp_classes')
        print(f"Loaded {len(records)} class definitions")

    def get_class_definition(self, class_id: str) -> Optional[Dict]:
        """Get class definition by class_id"""
        try:
            cursor = self.conn.execute("""
                SELECT class_id, name, file_path, start_line, end_line,
                       package_name, annotations, fields
                FROM class_definitions
                WHERE class_id = ?
            """, [class_id])

            result = cursor.fetchone()

        except duckdb.InvalidInputException:
            print(f"Error fetching class definition: {class_id}")
            return None

        if result:
            return {
                'class_id': result[0],
                'name': result[1],
                'file_path': result[2],
                'start_line': result[3],
                'end_line': result[4],
                'package_name': result[5],
                'annotations': json.loads(result[6]) if result[6] else [],
                'fields': json.loads(result[7]) if result[7] else [],
                '_is_class': True  # Flag for class vs function
            }
        return None

    def get_classes_by_name(self, class_name: str) -> List[Dict]:
        """Get all class definitions with matching name"""
        try:
            cursor = self.conn.execute("""
                SELECT class_id, name, file_path, start_line, end_line,
                       package_name, annotations, fields
                FROM class_definitions
                WHERE name = ?
                ORDER BY file_path, start_line
            """, [class_name])

            results = cursor.fetchall()

        except duckdb.InvalidInputException:
            print(f"Error fetching classes by name: {class_name}")
            return []

        classes = []
        for result in results:
            classes.append({
                'class_id': result[0],
                'name': result[1],
                'file_path': result[2],
                'start_line': result[3],
                'end_line': result[4],
                'package_name': result[5],
                'annotations': json.loads(result[6]) if result[6] else [],
                'fields': json.loads(result[7]) if result[7] else [],
                '_is_class': True
            })

        return classes

    def get_function_by_identifier(self, identifier: str, source_root: Optional[Path] = None) -> List[Dict]:
        """
        Unified function lookup with router information and class file fallback

        Args:
            identifier: Function or class identifier to look up
            source_root: Optional path to codebase root for class file fallback

        Returns:
            List of function/class info dictionaries
        """
        # First sanitize the identifier
        sanitized_identifier = self._sanitize_identifier(identifier)

        # First try as callsite_id (prioritized)
        function_info = self.resolve_call_to_definition(sanitized_identifier)

        if function_info:
            return [function_info]

        # Fall back to function_id lookup
        function_info = self.get_function_definition(sanitized_identifier)

        if function_info:
            return [function_info]

        # Third fallback: name-only matching for functions
        function_name = sanitized_identifier.split('@')[0] if '@' in sanitized_identifier else sanitized_identifier
        functions = self.get_functions_by_name(function_name)

        if functions:
            return functions

        # Fourth fallback: Try as class_id (for DTOs, entities, etc.)
        class_info = self.get_class_definition(sanitized_identifier)

        if class_info:
            return [class_info]

        # Fifth fallback: name-only matching for classes
        classes = self.get_classes_by_name(function_name)

        if classes:
            return classes

        # Final fallback: Try to read as class file (for classes not in database)
        if source_root and self._is_class_identifier(sanitized_identifier):
            class_info = self._read_class_file(sanitized_identifier, source_root)
            if class_info:
                return [class_info]

        # Sixth fallback: Try to read as a field/constant declaration
        if source_root:
            field_info = self._read_field_from_file(sanitized_identifier, source_root)
            if field_info:
                return [field_info]

        return []

    def _sanitize_identifier(self, identifier: str) -> str:
        """
        Clean up identifier format for multiple languages:
        - Java/Python: obj.func@file:line -> func@file:line
        - C++: obj->func@file:line -> func@file:line  
        - C++: Class::func@file:line -> func@file:line
        """
        # Split into name and location parts
        if '@' in identifier:
            name_part, location_part = identifier.split('@', 1)
        else:
            name_part, location_part = identifier, None
        
        # Clean the name part - handle multiple separators
        # C++: obj->func, Class::func
        # Java/Python: obj.func
        separators = ['->', '::', '.']
        
        for sep in separators:
            if sep in name_part:
                name_part = name_part.split(sep)[-1]  # Take last part
                break
        
        # Remove function call parentheses
        if name_part.endswith('()'):
            name_part = name_part[:-2]
        
        name_part = name_part.strip()
        
        # Reconstruct identifier
        if location_part:
            return f"{name_part}@{location_part}"
        else:
            return name_part

    def _is_class_identifier(self, identifier: str) -> bool:
        """
        Detect if identifier looks like a class path (no method name, just file path)

        Class identifiers typically look like:
        - ClassName@path/to/File.java
        - ClassName@path/to/File.java:line

        This is distinguished from function identifiers by:
        - Class name matches filename (e.g., MemberRegisterDto@.../MemberRegisterDto.java)
        - OR identifier contains patterns like Dto, Form, Request, Response, Entity
        """
        if '@' not in identifier:
            return False

        name_part, location_part = identifier.split('@', 1)

        # Extract filename from location
        file_path = location_part.split(':')[0] if ':' in location_part else location_part

        # Check if it's a .java file (extend for other languages as needed)
        if not file_path.endswith('.java'):
            return False

        # Check if name matches filename pattern (common for DTOs/entities)
        filename = Path(file_path).stem  # Get filename without extension
        if name_part == filename:
            return True

        # Check for common DTO/entity/form naming patterns
        class_patterns = ['Dto', 'DTO', 'Form', 'Request', 'Response', 'Entity', 'Bean', 'Model', 'Vo', 'VO']
        for pattern in class_patterns:
            if pattern in name_part:
                return True

        return False

    def _read_class_file(self, identifier: str, source_root: Path) -> Optional[Dict]:
        """
        Read class file directly and return as function_info-like dict

        Args:
            identifier: Class identifier (e.g., MemberRegisterDto@path/to/File.java)
            source_root: Path to codebase root

        Returns:
            Dict with class information, or None if file not found
        """
        source_root = Path(source_root)

        # Parse identifier
        name_part, location_part = identifier.split('@', 1)
        file_path = location_part.split(':')[0] if ':' in location_part else location_part

        # Build full path
        full_path = source_root / file_path

        if not full_path.exists():
            # Try alternative paths (sometimes LLM provides incorrect paths)
            # Search for the file by name
            filename = Path(file_path).name
            candidates = list(source_root.glob(f"**/{filename}"))

            if not candidates:
                return None

            # Use first match
            full_path = candidates[0]
            file_path = str(full_path.relative_to(source_root))

        # Read class source
        try:
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            # Find class definition (simple heuristic: look for "class ClassName" or "@Data")
            class_start = 0
            class_end = len(lines)

            for i, line in enumerate(lines):
                # Look for class declaration or common annotations
                if ('class ' in line and name_part in line) or ('@Data' in line) or ('@Entity' in line):
                    class_start = max(0, i - 5)  # Include annotations above class
                    break

            # Return as function_info-like dict
            return {
                'function_id': identifier,
                'name': name_part,
                'file_path': file_path,
                'start_line': 1,  # Full class
                'end_line': len(lines),
                'signature': f"class {name_part}",
                'class_name': name_part,
                'package_name': None,
                '_is_class': True,  # Flag to indicate this is a class, not a function
                '_source_lines': lines,  # Store lines for direct access
            }

        except Exception as e:
            print(f"Error reading class file {full_path}: {e}")
            return None

    def _read_field_from_file(self, identifier: str, source_root: Path) -> Optional[Dict]:
        """
        Read a field/constant declaration from a source file.

        Used when all DuckDB lookups fail for an identifier that points to a .java
        source file — typically static constants (e.g. DEFAULT_ALLOWED_EXTENSION)
        that are not captured in function_definitions.

        Handles multi-line declarations (e.g. array initializers ending with '};').
        """
        if '@' not in identifier:
            return None

        name_part, location_part = identifier.split('@', 1)
        file_path = location_part.split(':')[0] if ':' in location_part else location_part

        if not file_path.endswith('.java'):
            return None

        source_root = Path(source_root)
        full_path = source_root / file_path

        if not full_path.exists():
            filename = Path(file_path).name
            candidates = list(source_root.glob(f"**/{filename}"))
            if not candidates:
                return None
            full_path = candidates[0]
            file_path = str(full_path.relative_to(source_root))

        try:
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except Exception as e:
            print(f"Error reading field file {full_path}: {e}")
            return None

        # Find the first line where the name appears as a standalone identifier,
        # ignoring inline comments.
        pattern = re.compile(r'\b' + re.escape(name_part) + r'\b')
        start_idx = None
        for i, line in enumerate(lines):
            stripped = line.split('//')[0]
            if pattern.search(stripped):
                start_idx = i
                break

        if start_idx is None:
            return None

        # Collect lines until the statement terminates with ';'
        end_idx = start_idx
        for j in range(start_idx, min(start_idx + 50, len(lines))):
            end_idx = j
            if ';' in lines[j]:
                break

        start_line = start_idx + 1  # convert to 1-based
        end_line = end_idx + 1

        numbered = [f"{start_idx + k + 1}:{lines[start_idx + k].rstrip()}"
                    for k in range(end_idx - start_idx + 1)]
        source = '\n'.join(numbered)

        return {
            'function_id': identifier,
            'name': name_part,
            'file_path': file_path,
            'start_line': start_line,
            'end_line': end_line,
            'signature': f'field {name_part}',
            '_is_field': True,
            '_source': source,
        }

    def get_functions_by_name(self, function_name: str) -> List[Dict]:
        """Get all function definitions with matching name and router info"""
        try:
            cursor = self.conn.execute("""
                SELECT fd.function_id, fd.name, fd.file_path, fd.start_line, fd.end_line, 
                       fd.signature, fd.class_name, fd.package_name,
                       rd.router_definition_id, rd.router_source_code
                FROM function_definitions fd
                LEFT JOIN router_definitions rd ON fd.function_id = rd.function_id
                WHERE fd.name = ?
                ORDER BY fd.file_path, fd.start_line
            """, [function_name])
            
            results = cursor.fetchall()
            
        except duckdb.InvalidInputException:
            print(f"Error fetching functions by name: {function_name}")
            return []
        
        functions = []
        for result in results:
            function_info = {
                'function_id': result[0],
                'name': result[1],
                'file_path': result[2],
                'start_line': result[3],
                'end_line': result[4],
                'signature': result[5],
                'class_name': result[6],
                'package_name': result[7],
            }
            
            # Add router info if available
            if result[8]:  # router_definition_id
                function_info['router_info'] = {
                    'router_definition_id': result[8],
                    'router_source_code': result[9]
                }
            
            functions.append(function_info)
        
        return functions
        
    def get_function_definition(self, function_id: str) -> Optional[Dict]:
        """Get function definition by function_id with router info"""
        try:
            cursor = self.conn.execute("""
                SELECT fd.function_id, fd.name, fd.file_path, fd.start_line, fd.end_line, 
                       fd.signature, fd.class_name, fd.package_name,
                       rd.router_definition_id, rd.router_source_code
                FROM function_definitions fd
                LEFT JOIN router_definitions rd ON fd.function_id = rd.function_id
                WHERE fd.function_id = ?
            """, [function_id])
            
            result = cursor.fetchone()
            
        except duckdb.InvalidInputException:
            print(f"Error fetching function definition: {function_id}")
            return None
        
        if result:
            function_info = {
                'function_id': result[0],
                'name': result[1],
                'file_path': result[2],
                'start_line': result[3],
                'end_line': result[4],
                'signature': result[5],
                'class_name': result[6],
                'package_name': result[7],
            }
            
            # Add router info if available
            if result[8]:  # router_definition_id
                function_info['router_info'] = {
                    'router_definition_id': result[8],
                    'router_source_code': result[9]
                }
            
            return function_info
        return None
    
    def get_function_source_code(self, function_info: Dict, source_root: Path) -> Optional[str]:
        """Extract source code for a function or class"""
        # Check if this is a field read via file fallback (has pre-computed source)
        if function_info.get('_is_field') and '_source' in function_info:
            return function_info['_source']

        # Check if this is a class read via file fallback (has pre-read lines)
        if function_info.get('_is_class') and '_source_lines' in function_info:
            # Use pre-read lines
            lines = function_info['_source_lines']

            # Add line numbers for context
            numbered_lines = []
            for i, line in enumerate(lines):
                numbered_lines.append(f"{i+1}:{line.rstrip()}")

            return '\n'.join(numbered_lines)

        # Standard function/class source extraction from file
        source_root = Path(source_root)
        file_path = source_root / function_info['file_path']

        if not file_path.exists():
            return None

        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        start_line = function_info['start_line']
        end_line = function_info['end_line']

        # Validate line ranges
        if start_line <= 0 or start_line > len(lines):
            return None

        if end_line > len(lines):
            print(f"Warning: end_line {end_line} exceeds file length {len(lines)} for {function_info.get('name')} in {file_path}")
            end_line = len(lines)  # Truncate to file length

        # Extract function/class lines (1-based to 0-based conversion)
        start_idx = start_line - 1
        end_idx = min(end_line, len(lines))

        function_lines = lines[start_idx:end_idx]

        # Add line numbers for context
        numbered_lines = []
        for i, line in enumerate(function_lines):
            line_num = start_idx + i + 1
            numbered_lines.append(f"{line_num}:{line.rstrip()}")

        return '\n'.join(numbered_lines)
        
    def resolve_call_to_definition(self, callsite_id: str) -> Optional[Dict]:
        """Main function: Given callsite_id, return function definition with router info"""
        try:
            cursor = self.conn.execute("""
                SELECT fd.function_id, fd.name, fd.file_path, fd.start_line, fd.end_line, 
                       fd.signature, fd.class_name, fd.package_name,
                       rd.router_definition_id, rd.router_source_code
                FROM call_resolutions cr
                JOIN function_definitions fd ON cr.target_function_id = fd.function_id
                LEFT JOIN router_definitions rd ON fd.function_id = rd.function_id
                WHERE cr.callsite_id = ?
            """, [callsite_id])
            
            result = cursor.fetchone()
            
        except duckdb.InvalidInputException:
            print(f"Error resolving call to definition: {callsite_id}")
            return None
        
        if result:
            function_info = {
                'function_id': result[0],
                'name': result[1],
                'file_path': result[2],
                'start_line': result[3],
                'end_line': result[4],
                'signature': result[5],
                'class_name': result[6],
                'package_name': result[7],
            }
            
            # Add router info if available
            if result[8]:  # router_definition_id
                function_info['router_info'] = {
                    'router_definition_id': result[8],
                    'router_source_code': result[9]
                }
            
            return function_info
        return None
    
    # ------------------------------------------------------------------
    # code-search primitive support  (see src/agent/primitives.py)
    # ------------------------------------------------------------------
    def _rows_to_functions(self, rows) -> List[Dict]:
        out = []
        for r in rows:
            out.append({
                'function_id': r[0], 'name': r[1], 'file_path': r[2],
                'start_line': r[3], 'end_line': r[4], 'signature': r[5],
                'class_name': r[6], 'package_name': r[7],
            })
        return out

    def search_functions_by_name(self, pattern: str, limit: int = 200) -> List[Dict]:
        """Regex (RE2) match against function/method names — powers Qname."""
        try:
            cur = self.conn.execute("""
                SELECT function_id, name, file_path, start_line, end_line,
                       signature, class_name, package_name
                FROM function_definitions
                WHERE regexp_matches(name, ?)
                ORDER BY file_path, start_line
                LIMIT ?
            """, [pattern, limit])
            return self._rows_to_functions(cur.fetchall())
        except Exception as e:
            print(f"search_functions_by_name({pattern!r}) failed: {e}")
            return []

    def search_classes_by_name(self, pattern: str, limit: int = 200) -> List[Dict]:
        try:
            cur = self.conn.execute("""
                SELECT class_id, name, file_path, start_line, end_line, package_name
                FROM class_definitions
                WHERE regexp_matches(name, ?)
                ORDER BY file_path, start_line
                LIMIT ?
            """, [pattern, limit])
            return [{'class_id': r[0], 'name': r[1], 'file_path': r[2],
                     'start_line': r[3], 'end_line': r[4], 'package_name': r[5]}
                    for r in cur.fetchall()]
        except Exception as e:
            print(f"search_classes_by_name({pattern!r}) failed: {e}")
            return []

    def all_functions(self, limit: int = 5000) -> List[Dict]:
        cur = self.conn.execute("""
            SELECT function_id, name, file_path, start_line, end_line,
                   signature, class_name, package_name
            FROM function_definitions ORDER BY file_path, start_line LIMIT ?
        """, [limit])
        return self._rows_to_functions(cur.fetchall())

    # ``callsite_id`` is ``<callee-name>@<file>:<line>`` where the call happens.
    _CS_FILE = r"regexp_extract(callsite_id, '@(.*):([0-9]+)$', 1)"
    _CS_LINE = r"CAST(regexp_extract(callsite_id, '@(.*):([0-9]+)$', 2) AS BIGINT)"

    def _containing_function(self, file_path: str, line: int) -> Optional[Dict]:
        """Smallest function whose line range covers (file_path, line)."""
        row = self.conn.execute("""
            SELECT function_id, name, file_path, start_line, end_line,
                   signature, class_name, package_name
            FROM function_definitions
            WHERE file_path = ? AND start_line <= ? AND end_line >= ?
            ORDER BY (end_line - start_line) ASC LIMIT 1
        """, [file_path, line, line]).fetchone()
        return self._rows_to_functions([row])[0] if row else None

    def get_callees(self, function_id: str) -> List[Dict]:
        """
        Resolved calls made from inside *function_id* — powers Qcg(direction=callees).
        The call-site location is filtered in SQL from ``callsite_id``.
        """
        fn = self.get_function_definition(function_id)
        if not fn:
            return []
        rows = self.conn.execute(f"""
            SELECT cr.callsite_id, cr.target_function_id,
                   fd.name, fd.file_path, fd.start_line, fd.end_line,
                   fd.signature, fd.class_name, fd.package_name
            FROM call_resolutions cr
            LEFT JOIN function_definitions fd ON fd.function_id = cr.target_function_id
            WHERE {self._CS_FILE} = ? AND {self._CS_LINE} BETWEEN ? AND ?
        """, [fn['file_path'], fn['start_line'], fn['end_line']]).fetchall()
        out = []
        for cid, target, name, fpath, sl, el, sig, cn, pkg in rows:
            tgt = {'function_id': target,
                   'name': name or (target.split('@')[0] if target else ''),
                   'file_path': fpath or (target.split('@')[-1].rsplit(':', 1)[0] if target and '@' in target else ''),
                   'start_line': sl, 'end_line': el, 'signature': sig,
                   'class_name': cn, 'package_name': pkg, 'callsite': cid}
            out.append(tgt)
        return out

    def get_callers(self, function_id: str) -> List[Dict]:
        """Functions that contain a resolved call to *function_id* — Qcg(direction=callers)."""
        cur = self.conn.execute(
            "SELECT callsite_id FROM call_resolutions WHERE target_function_id = ?",
            [function_id],
        )
        callers, seen = [], set()
        for (callsite_id,) in cur.fetchall():
            loc = callsite_id.rsplit("@", 1)[-1] if "@" in callsite_id else ""
            file_part, _, line_part = loc.rpartition(":")
            if not line_part.isdigit():
                continue
            c = self._containing_function(file_part, int(line_part))
            if c and c['function_id'] not in seen:
                seen.add(c['function_id'])
                c['callsite'] = callsite_id
                callers.append(c)
        return callers

    def get_database_stats(self) -> Dict:
        """Get database statistics"""
        try:
            # Get function count
            cursor = self.conn.execute("SELECT COUNT(*) FROM function_definitions")
            func_count = cursor.fetchone()[0]
            
            # Get call count
            cursor = self.conn.execute("SELECT COUNT(*) FROM call_resolutions")
            call_count = cursor.fetchone()[0]
            
            # Get router count
            cursor = self.conn.execute("SELECT COUNT(*) FROM router_definitions")
            router_count = cursor.fetchone()[0]

            # Get class count
            cursor = self.conn.execute("SELECT COUNT(*) FROM class_definitions")
            class_count = cursor.fetchone()[0]

            # Check referential integrity
            cursor = self.conn.execute("""
                SELECT COUNT(*) FROM call_resolutions cr
                LEFT JOIN function_definitions fd ON cr.target_function_id = fd.function_id
                WHERE fd.function_id IS NULL
            """)
            orphaned_calls = cursor.fetchone()[0]

        except duckdb.InvalidInputException:
            print("Error getting database statistics")
            return {
                'total_functions': 0,
                'total_call_sites': 0,
                'total_routers': 0,
                'total_classes': 0,
                'orphaned_calls': 0,
                'database_path': str(self.db_path)
            }

        return {
            'total_functions': func_count,
            'total_call_sites': call_count,
            'total_routers': router_count,
            'total_classes': class_count,
            'orphaned_calls': orphaned_calls,
            'database_path': str(self.db_path)
        }
    
    # ... (keep all other existing methods unchanged)
    
    def close(self):
        """Close database connection"""
        self.conn.close()

def load_database_from_json(functions_json: Path, calls_json: Path, routers_json: Path, db_path: Path, classes_json: Optional[Path] = None) -> CallGraphDatabase:
    """Load database from JSON files"""

    # Validate input files
    if not functions_json.exists():
        raise FileNotFoundError(f"Functions JSON not found: {functions_json}")

    if not calls_json.exists():
        raise FileNotFoundError(f"Calls JSON not found: {calls_json}")

    # Delete old database to ensure clean state (prevent accumulation of old corrupt data)
    db_path = Path(db_path)
    if db_path.exists():
        db_path.unlink()
        print(f"Deleted old database: {db_path}")

    # Create fresh database
    db = CallGraphDatabase(db_path)

    # Load data
    db.load_function_definitions(functions_json)
    db.load_call_resolutions(calls_json)
    if routers_json:
        db.load_router_definitions(routers_json)  # New router loading
    if classes_json and classes_json.exists():
        db.load_class_definitions(classes_json)  # Load classes (DTOs, entities, forms)

    return db

def duckdb_main(database, codebase, appname: str):
    # Build the enhanced function mapping
    try:
        function_map = get_app_function_map_file(appname)
        callsites = get_app_callsite_json_file(appname)
        decorator = get_app_decorator_json_file(appname)
        classes_json = get_app_classes_json_file(appname)
        _duckdb = get_app_duckdb_file(appname)

        language = get_database_language(database)
        sarif_file = execute_decorator_resolution_query(database, language, appname)
        if sarif_file:
            # print(f"decorator sarif not generated")
            # return False
            extract_decorator_resolutions(codebase, sarif_file, decorator)  # Note: order changed

        # create function map using CodeQL
        function_index = build_enhanced_function_mapping_codeql(
            source_root=codebase,
            codeql_db_path=database,
            language=language
        )
        function_index.save_optimized_mapping(function_map)

        # Extract class definitions using CodeQL (Java, Python, C#)
        if language in ("java", "python", "csharp", "javascript"):
            try:
                print("\nExtracting class definitions...")
                extractor = {
                    "java": extract_java_classes,
                    "python": extract_python_classes,
                    "csharp": extract_csharp_classes,
                    "javascript": extract_javascript_classes,
                }[language]
                classes = extractor(codebase_path=codebase, codeql_db_path=database)

                classes_data = {
                    "class_definitions": {
                        class_id: clazz.to_dict()
                        for class_id, clazz in classes.items()
                    }
                }
                with open(classes_json, "w", encoding="utf-8") as f:
                    json.dump(classes_data, f, indent=2)
                print(f"Saved {len(classes)} classes to {classes_json}")
            except Exception as e:
                print(f"Warning: Class extraction failed: {e}")
                print("Continuing without class definitions (file fallback will still work)")
                classes_json = None

        # create callsites
        sarif_file = execute_callsite_resolution_query(database, language, appname)
        if not sarif_file:
            print(f"callsites sarif not generated")
            return False

        extract_callsite_resolutions(sarif_file, callsites)

        # Load database with router and class support
        db = load_database_from_json(function_map, callsites, decorator, _duckdb, classes_json)

        # Show statistics
        stats = db.get_database_stats()
        print(f"\nDatabase Statistics:")
        print(f"  Functions: {stats['total_functions']}")
        print(f"  Call Sites: {stats['total_call_sites']}")
        print(f"  Routers: {stats['total_routers']}")
        print(f"  Classes: {stats['total_classes']}")
        print(f"  Orphaned Calls: {stats['orphaned_calls']}")
        print(f"  Database: {stats['database_path']}")
        db.close()
        return True

    except Exception as e:
        print(f"Error: {e}")
        return False
