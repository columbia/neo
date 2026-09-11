#!/usr/bin/env python3
"""
Call Site Resolution SARIF Parser
File: callsite_sarif_parser.py

Parse CodeQL call site resolution SARIF and create call mapping database.
Based on auth_sarif_parser.py structure.
"""

import os
from typing import Dict, List, Any, Optional
from pathlib import Path

from common.sarif_parser import stream_sarif_results, extract_sarif_location, sarif_save_json
from common.codeql import execute_query
from common.helper import get_query_dir, get_app_callsites_sarif_file

def process_callsite_result(result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Process callsite result with consistent function_name@file:line format"""
    try:
        locations = result.get('locations', [])
        if not locations:
            return None
        
        call_location = extract_sarif_location(locations[0])
        message = result.get('message', {}).get('text', '')
        
        if not message or ' -> ' not in message:
            return None
        
        parts = message.split(' -> ')
        if len(parts) != 2:
            return None
        
        callsite_part = parts[0].strip()
        target_part = parts[1].strip()
        
        # Parse callsite location
        callsite_components = parse_callsite_location(callsite_part)
        if not callsite_components:
            return None
        
        # Parse target function
        target_components = parse_target_function(target_part)
        if not target_components:
            return None
        
        # Create consistent callsite ID: method_name@file:line (at call location)
        callsite_id = f"{target_components['function_name']}@{callsite_components['file']}:{callsite_components['line']}"
        
        return {
            'callsite_id': callsite_id,  # method_name@file:line (where call happens)
            'callsite_file': callsite_components['file'],
            'callsite_line': callsite_components['line'],
            'called_method': target_components['function_name'],
            'target_function_id': target_part,  # method_name@file:line (where method is defined)
            'target_function_name': target_components['function_name'],
            'target_file': target_components['file'],
            'target_line': target_components['line']
        }
        
    except Exception as e:
        print(f"Error processing callsite result: {e}")
        return None

def parse_callsite_location(callsite_str: str) -> Optional[Dict[str, Any]]:
    """Parse callsite location: file:line:col"""
    try:
        # Handle paths that might contain colons
        parts = callsite_str.rsplit(':', 2)  # Split from right to handle Windows paths
        if len(parts) >= 3:
            return {
                'file': parts[0],
                'line': int(parts[1]),
                'column': int(parts[2])
            }
        elif len(parts) >= 2:
            return {
                'file': parts[0], 
                'line': int(parts[1]),
                'column': 0  # Default column
            }
    except (ValueError, IndexError):
        pass
    return None

def parse_target_function(target_str: str) -> Optional[Dict[str, Any]]:
    """Parse target function: function_name@file:line (simplified)"""
    try:
        if '@' not in target_str:
            return None
            
        parts = target_str.rsplit('@', 1)  # Split from right
        function_name = parts[0]  # Just the function name now
        location_part = parts[1]
        
        # Parse location: file:line
        location_parts = location_part.rsplit(':', 1)
        if len(location_parts) >= 2:
            return {
                'function_name': function_name,
                'file': location_parts[0],
                'line': int(location_parts[1])
            }
    except (ValueError, IndexError):
        pass
    return None



def create_call_resolution_mapping(processed_results: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Create callsite_id -> target_function_id mapping"""
    call_mapping = {}
    
    for result in processed_results:
        callsite_id = result['callsite_id']
        call_mapping[callsite_id] = result['target_function_id']

    
    return call_mapping

def extract_callsite_resolutions(sarif_file: Path, output_file: Path) -> Optional[bool]:
    """Main extraction function for call site resolutions - minimal output"""
    print(f"Starting call site resolution extraction...")
    
    processed_results = []
    result_count = 0
    
    for result in stream_sarif_results(sarif_file):
        processed = process_callsite_result(result)
        if processed:
            processed_results.append(processed)
        result_count += 1

    if not processed_results:
        # a service with only library calls has no intra-project edges — that is
        # a valid (empty) call graph, so still write the file.
        print("No call site resolution results found (empty call graph)")
        sarif_save_json({
            "metadata": {"source_sarif": os.path.basename(sarif_file),
                         "total_call_sites": 0, "unique_targets": 0,
                         "parser_type": "call_site_resolution"},
            "call_resolutions": {},
        }, output_file)
        return True

    print(f"Processed {result_count} SARIF results, found {len(processed_results)} call resolutions")
    
    # Create minimal mapping: callsite_id -> target_function_id
    call_mapping = {}
    for result in processed_results:
        callsite_id = result['callsite_id']
        target_function_id = result['target_function_id']
        call_mapping[callsite_id] = target_function_id
    
    # Minimal data structure
    final_data = {
        'metadata': {
            'source_sarif': os.path.basename(sarif_file),
            'total_call_sites': len(call_mapping),
            'unique_targets': len(set(call_mapping.values())),
            'parser_type': 'call_site_resolution'
        },
        'call_resolutions': call_mapping  # Simple key -> value mapping
    }
    
    # Save results
    sarif_save_json(final_data, output_file)
    
    print(f"Call resolution mapping saved: {output_file}")
    print(f"Found {len(call_mapping)} call sites mapping to {final_data['metadata']['unique_targets']} unique functions")
    return True

def execute_callsite_resolution_query(database: Path, language: str, appname: str):
    """Execute CodeQL query to find call site resolutions"""
    print("=" * 50)
    print(f"Running call site resolution query for {language} on {database}")
    
    
    # Create query directory and file
    query_dir = get_query_dir() / language
    # query_dir.mkdir(parents=True, exist_ok=True)
    query_file = query_dir / "callsites.ql"

    print(f"Query file: {query_file}")


    sarif_output = get_app_callsites_sarif_file(appname)
    
    success = execute_query(
        query_path=query_file, 
        database_path=database, 
        output_file=sarif_output,
        query_wd=query_dir
    )
    
    if not success:
        print("Failed to execute CodeQL query")
        return None
        
    print(f"Query results saved to: {sarif_output}")
    return sarif_output
