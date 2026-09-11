#!/usr/bin/env python3
"""
Simple SARIF parsing utilities
File: common/sarif_parser.py

Just helpful functions for parsing SARIF files - no classes needed!
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Iterator
import ijson



def get_file_size_mb(file_path: Path) -> float:
    """Get file size in MB"""
    file_path = Path(file_path)
    return file_path.stat().st_size / (1024 * 1024)

def stream_sarif_results(sarif_file: Path) -> Iterator[Dict[str, Any]]:
    """
    Stream SARIF results from file
    Automatically chooses streaming vs full load based on file size
    """
    sarif_file = Path(sarif_file)
    file_size = get_file_size_mb(sarif_file)
    # print(f"Reading SARIF: {sarif_file} ({file_size:.1f} MB)")
    
    if file_size > 10:  # Use streaming for files > 10MB
        return _stream_with_ijson(sarif_file)
    else:
        return _parse_full_file(sarif_file)

def _stream_with_ijson(sarif_file: Path) -> Iterator[Dict[str, Any]]:
    """Stream parse using ijson for memory efficiency"""
    try:
        with open(sarif_file, 'rb') as file:
            results = ijson.items(file, 'runs.item.results.item')
            count = 0
            
            for result in results:
                yield result
                count += 1       
                # if count % 1000 == 0:
                #     print(f"  Processed {count} results...")
                        
    except Exception as e:
        print(f"Error with ijson streaming: {e}")
        print("Falling back to full file parsing...")
        yield from _parse_full_file(sarif_file)

def _parse_full_file(sarif_file: Path) -> Iterator[Dict[str, Any]]:
    """Fallback to loading entire file"""
    try:
        with open(sarif_file, 'r', encoding='utf-8') as f:
            sarif_data = json.load(f)
        
        for run in sarif_data.get('runs', []):
            for result in run.get('results', []):
                yield result
                    
    except Exception as e:
        print(f"Error parsing SARIF file: {e}")

def parse_location_string(location_str: str) -> Optional[Dict[str, Any]]:
    """
    Parse location format like:
    "file.java:126:17:126:32" or "file.java:126:32"
    Returns: {file, start_line, end_line, start_column, end_column}
    """
    try:
        # SARIF locations can carry trailing context (e.g. C# attribute lines) after a newline.
        location_str = location_str.split('\n', 1)[0].strip()
        if location_str.count(':') == 2:
            # Format: file:line:column
            file_part, line_str, col_str = location_str.rsplit(':', 2)
            line = int(line_str)
            return {
                'file': file_part.strip('"'),
                'start_line': line,
                'end_line': line,
                'start_column': int(col_str),
                'end_column': int(col_str)
            }
        elif location_str.count(':') >= 4:
            # Format: file:start_line:start_col:end_line:end_col
            parts = location_str.rsplit(':', 4)
            if len(parts) == 5:
                file_part = parts[0]
                start_line, start_col, end_line, end_col = map(int, parts[1:])
                return {
                    'file': file_part.strip('"'),
                    'start_line': start_line,
                    'end_line': end_line,
                    'start_column': start_col,
                    'end_column': end_col
                }
        
        return None
    except Exception as e:
        print(f"Error parsing location string '{location_str}': {e}")
        return None

import re
import urllib.parse

_FILE_URI_RE = re.compile(r"^file:/+")


def clean_sarif_uri(uri: str) -> str:
    """
    Normalize a SARIF ``artifactLocation.uri``.

    A location inside the source archive is a plain relative path. One
    outside it (a system/library header CodeQL's taint graph routed through,
    e.g. compiling a C++ app pulls in libc++ internals) comes back as an
    absolute ``file:/…`` URI — note *one* slash, not the ``file://`` most
    tools expect — which, left as-is, gets silently mis-joined onto
    ``source_root`` downstream (``Path("/root") / "file:/a/b"`` treats the
    whole string as one relative segment, because it doesn't start with
    ``/``) and ends up unresolvable ("File not found" placeholders breed
    through every generated flow). Strip the scheme and percent-decode.
    """
    if not uri:
        return uri
    if _FILE_URI_RE.match(uri):
        uri = _FILE_URI_RE.sub("/", uri, count=1)
        return urllib.parse.unquote(uri)
    return uri


def extract_sarif_location(location_obj: Dict[str, Any]) -> Dict[str, Any]:
    """Extract location info from SARIF location object"""
    phys_loc = location_obj.get('physicalLocation', {})
    artifact = phys_loc.get('artifactLocation', {})
    region = phys_loc.get('region', {})

    return {
        'file': clean_sarif_uri(artifact.get('uri', '')),
        'start_line': region.get('startLine', 0),
        'end_line': region.get('endLine', region.get('startLine', 0)),
        'start_column': region.get('startColumn', 0),
        'end_column': region.get('endColumn', region.get('startColumn', 0))
    }

def read_source_file(file_path: Path, encoding: str = 'utf-8') -> List[str]:
    """Read source file and return lines"""
    try:
        file_path = Path(file_path)
        with open(file_path, 'r', encoding=encoding) as f:
            return f.readlines()
    except FileNotFoundError:
        print(f"Warning: Source file not found: {file_path}")
        return [f"// Source file not found: {file_path}\n"]
    except Exception as e:
        print(f"Error reading source file {file_path}: {e}")
        return [f"// Error reading source: {str(e)}\n"]

def get_source_context(source_root: Path, file_path: str, start_line: int, end_line: int) -> str:
    """Get source code context for a given file and line range"""
    source_root = Path(source_root)
    full_path = source_root / file_path
    lines = read_source_file(full_path)
    
    # Convert to 0-based indexing
    start_idx = max(0, start_line - 1)
    end_idx = min(len(lines), end_line)
    
    return ''.join(lines[start_idx:end_idx])

def add_line_numbers(source_code: str, start_line: int) -> str:
    """Add line numbers to source code"""
    lines = source_code.split('\n')
    numbered_lines = []
    
    for i, line in enumerate(lines):
        line_number = start_line + i
        numbered_lines.append(f"{line_number}: {line}")
    
    return '\n'.join(numbered_lines)

def sarif_save_json(data: Any, output_file: Path) -> None:
    """Save data to JSON file"""
    try:
        output_file = Path(output_file)
        
        # Ensure parent directory exists
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # print(f"\t Saved to: {output_file}")
        # print(f"\tSize: {output_file.stat().st_size / 1024:.1f} KB")
        
    except Exception as e:
        print(f"Error saving JSON: {e}")

# Example usage
if __name__ == "__main__":
    print("SARIF Parser Utilities")
    print("Available functions:")
    print("- stream_sarif_results(sarif_file)")
    print("- parse_location_string(location_str)")  
    print("- extract_sarif_location(location_obj)")
    print("- get_source_context(source_root, file_path, start_line, end_line)")
    print("- save_json(data, output_file)")
