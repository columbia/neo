#!/usr/bin/env python3
"""
FastAPI Decorator Resolution SARIF Parser
File: decorator_sarif_parser.py

Parse CodeQL decorator resolution SARIF and create decorator mapping database.
Maps decorated functions to router definitions with source code extraction.
"""

import os
from typing import Dict, List, Any, Optional
from pathlib import Path

from common.sarif_parser import stream_sarif_results, extract_sarif_location, sarif_save_json
from common.codeql import execute_query
from common.helper import get_query_dir, get_app_decorators_sarif_file

def process_decorator_result(result: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Process decorator result with function@file:line -> file:start:end format"""
    try:
        message = result.get('message', {}).get('text', '')
        
        if not message or ' -> ' not in message:
            return None
        
        parts = message.split(' -> ')
        if len(parts) != 2:
            return None
        
        function_id = parts[0].strip()  # function@file:line
        router_definition = parts[1].strip()  # file:start:end
        
        return {
            'function_id': function_id,
            'router_definition': router_definition
        }
        
    except Exception as e:
        print(f"Error processing decorator result: {e}")
        return None

def extract_router_source_code(router_definition: str, source_root: Path) -> Optional[str]:
    """Extract source code for router definition from file:start:end"""
    try:
        # Parse router definition: file:start_line:end_line
        location_parts = router_definition.rsplit(':', 2)
        if len(location_parts) < 3:
            return None
            
        file_path = location_parts[0]
        start_line = int(location_parts[1])
        end_line = int(location_parts[2])
        
        # Construct full file path
        full_path = source_root / file_path
        
        if not full_path.exists():
            print(f"Warning: File not found: {full_path}")
            return None
        
        # Read and extract the specified lines
        with open(full_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Extract lines (1-based to 0-based indexing)
        if start_line <= len(lines) and end_line <= len(lines):
            source_lines = lines[start_line-1:end_line]
            return ''.join(source_lines).rstrip('\n')
        else:
            print(f"Warning: Line range {start_line}:{end_line} out of bounds for {file_path}")
            return None
            
    except (ValueError, IndexError, IOError) as e:
        print(f"Error extracting source code for {router_definition}: {e}")
        return None

def extract_decorator_resolutions(source_root: Path, sarif_file: Path, output_file: Path) -> Optional[bool]:
    """Main extraction function for decorator resolutions with source code"""
    print(f"Starting FastAPI decorator resolution extraction...")
    
    processed_results = []
    result_count = 0
    
    for result in stream_sarif_results(sarif_file):
        processed = process_decorator_result(result)
        if processed:
            processed_results.append(processed)
        result_count += 1

    if not processed_results:
        print("No decorator resolution results found")
        return None
    
    print(f"Processed {result_count} SARIF results, found {len(processed_results)} decorator resolutions")
    
    # Create function -> router definition mapping
    function_to_router = {}
    for result in processed_results:
        function_id = result['function_id']
        router_definition = result['router_definition']
        function_to_router[function_id] = router_definition
    
    # Extract unique router definitions and their source code
    unique_router_definitions = set(result['router_definition'] for result in processed_results)
    router_source_code = {}
    
    print(f"Extracting source code for {len(unique_router_definitions)} unique router definitions...")
    
    for router_def in unique_router_definitions:
        source_code = extract_router_source_code(router_def, source_root)
        if source_code:
            router_source_code[router_def] = source_code
        else:
            router_source_code[router_def] = f"# Source code not available for {router_def}"
    
    # Create final data structure
    final_data = {
        'function_to_router': function_to_router,
        'router_definitions': router_source_code
    }
    
    # Save results
    sarif_save_json(final_data, output_file)
    
    print(f"Function to router mapping with source code saved: {output_file}")
    print(f"Found {len(function_to_router)} function mappings")
    print(f"Extracted source code for {len([v for v in router_source_code.values() if not v.startswith('# Source code not available')])} router definitions")
    return True

def execute_decorator_resolution_query(database: Path, language: str, appname: str, source_root: Path = None):
    """Execute CodeQL query to find FastAPI decorator resolutions"""
    print("=" * 50)
    print(f"Running FastAPI decorator resolution query for {language} on {database}")
    
    # Create query directory and file
    query_dir = get_query_dir() / language
    query_file = query_dir / "decorator.ql"

    print(f"Query file: {query_file}")

    sarif_output = get_app_decorators_sarif_file(appname)
    
    success = execute_query(
        query_path=query_file, 
        database_path=database, 
        output_file=sarif_output,
        query_wd=query_dir
    )
    
    if not success:
        print("Failed to execute CodeQL decorator query")
        return None
        
    print(f"Decorator query results saved to: {sarif_output}")
    return sarif_output