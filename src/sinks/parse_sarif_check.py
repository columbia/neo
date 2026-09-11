#!/usr/bin/env python3
"""
parse sarif file to json for easy validation
"""


from typing import Dict, List, Any, Optional
from collections import defaultdict
from pathlib import Path

from common.sarif_parser import stream_sarif_results, extract_sarif_location, parse_location_string, get_source_context, add_line_numbers, sarif_save_json
from common.find_func_end import find_function_end_line
from common.helper import get_app_base_check_json_file, get_app_source_dir

def process_auth_result(result: Dict[str, Any], source_root: Path) -> Optional[Dict[str, Any]]:
    """Process a single auth discovery result"""
    try:
        locations = result.get('locations', [])
        if not locations:
            return None
        
        # Get the check location from SARIF
        check_location = extract_sarif_location(locations[0])
        
        # Parse the message to get auth expression and method location
        message = result.get('message', {}).get('text', '')
        if not message or "OCCURRED IN FUNCTION" not in message:
            return None
        
        auth_expression = message.split(' OCCURRED IN FUNCTION ')[0]
        
        # Extract method location from message
        method_location_str = message.split(' OCCURRED IN FUNCTION ')[1].split(' AT ')[1] if ' AT ' in message else ''
        
        # Clean up the method location string (remove file:// prefix if present)
        pos = method_location_str.find(check_location['file'])
        if pos != -1:
            method_location_str = method_location_str[pos:]
            method_location = parse_location_string(method_location_str)
        else:
            return None
        
        if not method_location:
            return None
            
        # If we only have a single line for the method, try to find the actual end
        if method_location["start_line"] == method_location["end_line"]:
            try:
                method_location["end_line"] = find_function_end_line(
                    source_root / method_location['file'],
                    method_location["start_line"]
                )
            except:
                # Fallback: estimate method bounds
                method_location["end_line"] = method_location["start_line"] + 30
        
        # Sanity check: if method is too long, limit it
        if method_location["end_line"] - method_location["start_line"] > 60:
            method_location["end_line"] = method_location["start_line"] + 60
        
        return {
            'auth_expression': auth_expression,
            'check_line': check_location['start_line'],
            'check_file': check_location['file'],
            'method_location': method_location
        }
        
    except Exception as e:
        print(f"Error processing auth result: {e}")
        return None

def group_results_by_method(processed_results: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Group auth checks by method location"""
    methods_with_checks = defaultdict(list)
    
    for result in processed_results:
        method_location = result['method_location']
        method_key = f"{method_location['file']}@{method_location['start_line']}-{method_location['end_line']}"
        methods_with_checks[method_key].append(result)
    
    return methods_with_checks

def create_method_entry(source_root: Path, method_key: str, auth_checks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Create a method entry with source code and marked auth checks"""
    # Get method location from the first check (they should all be the same)
    method_location = auth_checks[0]['method_location']
    
    # Get method source code
    method_source = get_source_context(
        source_root,
        method_location['file'],
        method_location['start_line'],
        method_location['end_line']
    )
    
    # Add line numbers
    method_source_with_lines = add_line_numbers(method_source, method_location['start_line'])
    
    # Mark auth check lines
    auth_lines = {check['check_line'] for check in auth_checks}
    lines = method_source_with_lines.split('\n')
    marked_lines = []
    
    for line in lines:
        if ':' in line:
            line_num_str = line.split(':', 1)[0]
            try:
                line_num = int(line_num_str)
                if line_num in auth_lines:
                    marked_lines.append(f"{line}  // <--POTENTIAL AUTH CHECK")
                else:
                    marked_lines.append(line)
            except ValueError:
                marked_lines.append(line)
        else:
            marked_lines.append(line)
    
    method_source_marked = '\n'.join(marked_lines)
    
    return {
        'id': method_key, # .replace('/', '_').replace('@', '_').replace('-', '_')
        'method_location': method_location,
        'method_source_with_lines': method_source_marked,
        'auth_checks': [
            {
                'expression': check['auth_expression'],
                'line': check['check_line']
            }
            for check in auth_checks
        ]
    }

def parse_check(sarif_file: Path, appname: str) -> Path:
    
    processed_results = []
    result_count = 0


    codebase = get_app_source_dir(appname)
    output_file = get_app_base_check_json_file(appname)
    
    for result in stream_sarif_results(sarif_file):
        processed = process_auth_result(result, codebase)
        if processed:
            processed_results.append(processed)
        result_count += 1
    
    if not processed_results:
        print("No check results found")
        final_data = {
            'metadata': {
                'source_sarif': sarif_file.name,
                'source_root': str(codebase),
                'total_methods_with_auth': 0,
                'total_auth_checks': 0,
                'parser_type': 'auth_discovery'
            },
            'methods_with_auth': []
        }
        sarif_save_json(final_data, output_file)
        print(f"{output_file} found 0 methods with 0 auth checks")
        return output_file
    
    print(f"Processed {result_count} SARIF results, found {len(processed_results)} auth checks")
    
    # Group by method
    methods_with_checks = group_results_by_method(processed_results)
    
    # Create final data structure
    merged_methods = []
    for method_key, auth_checks in methods_with_checks.items():
        method_entry = create_method_entry(codebase, method_key, auth_checks)
        merged_methods.append(method_entry)
    
    # Sort by number of checks (most complex methods first)
    merged_methods.sort(key=lambda x: len(x['auth_checks']), reverse=True)
    
    total_checks = sum(len(method['auth_checks']) for method in merged_methods)
    
    final_data = {
        'metadata': {
            'source_sarif': sarif_file.name,
            'source_root': str(codebase),
            'total_methods_with_auth': len(merged_methods),
            'total_auth_checks': total_checks,
            'parser_type': 'auth_discovery'
        },
        'methods_with_auth': merged_methods
    }
    
    # Save results
    
    sarif_save_json(final_data, output_file)
    
    print(f"{output_file} found {len(merged_methods)} methods with {total_checks} auth checks")
    return output_file
