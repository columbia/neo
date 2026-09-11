#!/usr/bin/env python3
"""
Focused Flow Extractor for Path-Problem Results

Extracts flows with:
1. Step with source/sink attributes
2. Statement extracted using location
3. Tainted variable extracted using start/end columns
4. Location (file:line)
5. Containing function by function ID

Grouping options:
- By sinks (default, like codeFlows)
- By sources
- By shared source or sink

"""

import json
from typing import Dict, List, Any, Optional
from collections import defaultdict
from pathlib import Path


from common.codeql import execute_query
from common.helper import *
from common.sarif_parser import stream_sarif_results, extract_sarif_location
from duck_db.function_index import OptimizedFunctionIndex
from genquery.gen_flow2sink import gen_flow2sink_query


def _is_under(path: str, root: Path) -> bool:
    """Is *path* (already absolute) inside *root*?"""
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except ValueError:
        return False


def extract_tainted_variable(source_root: Path, file_path: str, line_num: int, start_col: int, end_col: int) -> str:
    """Extract the tainted variable using start and end columns"""
    try:
        source_root = Path(source_root)
        full_path = source_root / file_path
        
        with open(full_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Convert to 0-based index
        line_idx = line_num - 1
        
        if 0 <= line_idx < len(lines):
            line_content = lines[line_idx]
            
            # Extract variable using column positions (convert to 0-based)
            # SARIF uses 1-based indexing, so start_col-1 for start, end_col-1 for end
            start_idx = max(0, start_col - 1)
            end_idx = min(len(line_content), end_col - 1)
            
            if start_idx <= end_idx:
                variable = line_content[start_idx:end_idx].strip()
                return variable if variable else "// No variable found"
            else:
                return "// Invalid column range"
        else:
            return "// Line out of range"
            
    except FileNotFoundError:
        return f"// File not found: {file_path}"
    except Exception as e:
        return f"// Error extracting variable: {str(e)}"

def get_code_statement(source_root: Path, file_path: str, line_num: int) -> str:
    """Get the actual code statement at a specific file:line"""
    try:
        source_root = Path(source_root)
        full_path = source_root / file_path
        
        with open(full_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Convert to 0-based index
        line_idx = line_num - 1
        
        if 0 <= line_idx < len(lines):
            statement = lines[line_idx].strip()
            return statement if statement else "// Empty line"
        else:
            return f"// Line {line_num} out of range"
            
    except FileNotFoundError:
        return f"// File not found: {file_path}"
    except Exception as e:
        return f"// Error reading line: {str(e)}"

def process_thread_flow_simple(thread_flow: Dict[str, Any], source_root: Path, function_index=None) -> List[Dict[str, Any]]:
    """Process a single threadFlow and extract the required information"""
    locations = thread_flow.get('locations', [])
    
    flow_steps = []
    for i, location_wrapper in enumerate(locations):
        # The actual location is nested inside a 'location' key
        location_obj = location_wrapper.get('location', {})
        phys_loc = location_obj.get('physicalLocation', {})
        
        if not phys_loc:
            continue
            
        step_location = extract_sarif_location({'physicalLocation': phys_loc})
        
        # Get taxa information (role: source, sink, etc.)
        taxa = location_wrapper.get('taxa', [])
        role = 'step'  # default
        for taxon in taxa:
            props = taxon.get('properties', {})
            if 'CodeQL/DataflowRole' in props:
                role = props['CodeQL/DataflowRole']
                break
        
        file_path = step_location['file']
        line_num = step_location['start_line']
        start_col = step_location['start_column']
        end_col = step_location['end_column']

        # A path outside source_root is a system/library header the taint
        # path happened to route through (libc++ internals are the classic
        # case for C++: every std::string operation is a real function
        # call). It carries no information a reviewer needs and, left in,
        # both balloons the flow with dozens of unreadable "File not found"
        # placeholder steps and mis-resolves once file_path is absolute.
        if Path(file_path).is_absolute() and not _is_under(file_path, source_root):
            continue

        # Extract the required information
        step_info = {
            'step_role': f"Step {i + 1}" + (f" [{role.upper()}]" if role in ['source', 'sink'] else ""),
            'statement': get_code_statement(source_root, file_path, line_num),
            'tainted_variable': extract_tainted_variable(source_root, file_path, line_num, start_col, end_col),
            'location': f"{file_path}:{line_num}",
            'file': file_path,
            'role': role  # Keep role for internal logic
        }
        
        # Get function ID if function index is available
        if function_index:
            function_id = function_index.get_function_containing_line(Path(file_path), line_num)
            step_info['function_id'] = function_id or 'N/A'
        else:
            step_info['function_id'] = 'N/A'
        
        flow_steps.append(step_info)

    # CodeQL path graphs often put several path nodes on the same line (one
    # per SSA definition); collapse runs that land on the same location with
    # the same statement so the flow reads as one step per line of code.
    deduped: List[Dict[str, Any]] = []
    for step in flow_steps:
        prev = deduped[-1] if deduped else None
        if prev and step['location'] == prev['location'] and step['statement'] == prev['statement']:
            continue
        deduped.append(step)
    flow_steps = deduped

    if flow_steps:
        # sometimes there is no source/sink
        flow_steps[0]["role"] = "source"
        flow_steps[-1]["role"] = "sink"
        for idx, step in enumerate(flow_steps):
            tag = " [SOURCE]" if step["role"] == "source" else " [SINK]" if step["role"] == "sink" else ""
            step["step_role"] = f"Step {idx + 1}{tag}"
    return flow_steps

def process_sarif_results(sarif_file: Path, source_root: Path, function_index=None) -> List[Dict[str, Any]]:
    """Process all SARIF results and extract flow information"""
    
    all_flows = []
    
    for result_idx, result in enumerate(stream_sarif_results(sarif_file)):
        # Get sink location (primary location)
        locations = result.get('locations', [])
        if not locations:
            continue
            
        sink_location = extract_sarif_location(locations[0])
        
        # Get source locations (related locations)
        source_locations = []
        for rel_loc in result.get('relatedLocations', []):
            loc_info = extract_sarif_location(rel_loc)
            loc_info['id'] = rel_loc.get('id', '')
            loc_info['message'] = rel_loc.get('message', {}).get('text', '')
            source_locations.append(loc_info)
        
        # Process all threadFlows
        code_flows = result.get('codeFlows', [])
        
        for flow_idx, code_flow in enumerate(code_flows):
            thread_flows = code_flow.get('threadFlows', [])
            
            for thread_idx, thread_flow in enumerate(thread_flows):
                flow_steps = process_thread_flow_simple(thread_flow, source_root, function_index)
                
                if flow_steps:
                    # Find the actual source for this thread flow
                    source_step = next((step for step in flow_steps if step['role'] == 'source'), flow_steps[0])
                    sink_step = next((step for step in flow_steps if step['role'] == 'sink'), flow_steps[-1])
                    
                    flow_data = {
                        'flow_id': f"flow_{result_idx}_{flow_idx}_{thread_idx}",
                        'result_index': result_idx,
                        'codeflow_index': flow_idx,
                        'threadflow_index': thread_idx,
                        'source_location': f"{source_step['file']}:{source_step['location'].split(':')[1]}",
                        'sink_location': f"{sink_step['file']}:{sink_step['location'].split(':')[1]}",
                        'step_count': len(flow_steps),
                        'steps': flow_steps
                    }
                    
                    all_flows.append(flow_data)
    
    return all_flows

def group_flows_by_sinks(flows: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Group flows by sink locations (default SARIF behavior)"""
    grouped = defaultdict(list)
    
    for flow in flows:
        sink_key = flow['sink_location']
        grouped[sink_key].append(flow)
    
    return dict(grouped)

def group_flows_by_sources(flows: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Group flows by source locations"""
    grouped = defaultdict(list)
    
    for flow in flows:
        source_key = flow['source_location']
        grouped[source_key].append(flow)
    
    return dict(grouped)

def group_flows_by_shared(flows: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Group flows that share the same source or sink together"""
    
    # Use Union-Find (Disjoint Set) to group flows that are connected
    # by sharing sources or sinks
    
    # Create a mapping from flow_id to index for easier processing
    flow_id_to_idx = {flow['flow_id']: i for i, flow in enumerate(flows)}
    parent = list(range(len(flows)))
    
    def find(x):
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]
    
    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py
    
    # Group flows by their source and sink locations
    source_to_flows = defaultdict(list)
    sink_to_flows = defaultdict(list)
    
    for i, flow in enumerate(flows):
        source_to_flows[flow['source_location']].append(i)
        sink_to_flows[flow['sink_location']].append(i)
    
    # Union flows that share the same source
    for flow_indices in source_to_flows.values():
        if len(flow_indices) > 1:
            for i in range(1, len(flow_indices)):
                union(flow_indices[0], flow_indices[i])
    
    # Union flows that share the same sink
    for flow_indices in sink_to_flows.values():
        if len(flow_indices) > 1:
            for i in range(1, len(flow_indices)):
                union(flow_indices[0], flow_indices[i])
    
    # Group flows by their root parent
    groups = defaultdict(list)
    for i, flow in enumerate(flows):
        root = find(i)
        groups[root].append(flow)
    
    # Convert to a more readable format
    result = {}
    for group_id, group_flows in groups.items():
        if len(group_flows) > 1:
            # Create a meaningful group key based on shared locations
            sources = set(flow['source_location'] for flow in group_flows)
            sinks = set(flow['sink_location'] for flow in group_flows)
            
            # Create group key showing what's shared
            shared_parts = []
            if len(sources) < len(group_flows):  # Some flows share sources
                shared_parts.append(f"sources:{len(sources)}")
            if len(sinks) < len(group_flows):    # Some flows share sinks
                shared_parts.append(f"sinks:{len(sinks)}")
            
            group_key = f"shared_group_{group_id}_({','.join(shared_parts)})"
            result[group_key] = group_flows
        else:
            # Single flow groups (no sharing)
            flow = group_flows[0]
            result[f"isolated_{flow['flow_id']}"] = group_flows
    
    return result

def create_flow_summary(grouped_flows: Dict[str, List[Dict[str, Any]]], group_type: str) -> Dict[str, Any]:
    """Create a summary of the grouped flows including unique function counts"""
    
    total_flows = sum(len(flows) for flows in grouped_flows.values())
    total_groups = len(grouped_flows)
    total_unique_functions = 0

    group_details = []
    for group_key, flows in grouped_flows.items():
        # Get unique sources and sinks in this group
        sources = set(flow['source_location'] for flow in flows)
        sinks = set(flow['sink_location'] for flow in flows)
        
        # Collect unique functions - THIS IS THE KEY PART
        unique_functions = set()
        for flow in flows:
            for step in flow['steps']:
                func_id = step.get('function_id')
                if func_id and func_id != 'N/A':
                    unique_functions.add(func_id)
        
        group_info = {
            'group_key': group_key,
            'flow_count': len(flows),
            'unique_sources': len(sources),
            'unique_sinks': len(sinks),
            'unique_functions': len(unique_functions),
            'sources': sorted(list(sources)),
            'sinks': sorted(list(sinks)),
            'functions': sorted(list(unique_functions))
        }
        total_unique_functions += len(unique_functions)
        
        group_details.append(group_info)
    
    return {
        'grouping_type': group_type,
        'total_groups': total_groups,
        'total_flows': total_flows,
        'total_unique_functions': total_unique_functions,
        'groups': group_details
    }


def extract_flows(sarif_file: Path, source_root: Path, group_by: str, output_file: Path, function_map_file: Optional[Path] = None) -> None:
    
    sarif_file = Path(sarif_file)
    source_root = Path(source_root)
    
    # Load function index if provided
    function_index = None
    if function_map_file and function_map_file.exists():
        # print(f"Loading function map: {function_map_file}")
        try:
            function_index = OptimizedFunctionIndex.load_from_file(function_map_file)
            # print("Function mapping enabled")
        except Exception as e:
            print(f"Warning: Could not load function map: {e}")
    
    # Process all flows
    print(f"Processing SARIF file: {sarif_file}")
    all_flows = process_sarif_results(sarif_file, source_root, function_index)
    
    if not all_flows:
        grouped_flows = {}
        print(f"No flows found in SARIF file {sarif_file}")
    else:
        print(f"\tExtracted {len(all_flows)} flows")
        
        # Group flows based on the specified method
        if group_by == 'sources':
            grouped_flows = group_flows_by_sources(all_flows)
            print(f"\tGrouped by sources: {len(grouped_flows)} groups")
        elif group_by == 'shared':
            grouped_flows = group_flows_by_shared(all_flows)
            print(f"\tGrouped by shared locations: {len(grouped_flows)} groups")
        else:  # default: sinks
            grouped_flows = group_flows_by_sinks(all_flows)
            print(f"\tGrouped by sinks: {len(grouped_flows)} groups")
    
    # Create the final output structure
    output_data = {
        'metadata': {
            'source_sarif': sarif_file.name,
            'source_root': str(source_root),
            'grouping_method': group_by,
            'function_map_used': function_map_file is not None,
            'extraction_focus': 'variables_and_statements'
        },
        'summary': create_flow_summary(grouped_flows, group_by),
        'grouped_flows': grouped_flows
    }
    
    
    
    # Save to JSON, even when no flows are present, so downstream stages can
    # distinguish "zero results" from "missing artifact".
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"Summary: {output_data['summary']['total_flows']} flows in {output_data['summary']['total_groups']} groups; Unique functions in total: {output_data['summary']['total_unique_functions']}")




def execute_flow2sink_query(database: Path, appname: str, language: str) -> Optional[Path]:
    """Execute CodeQL query to find potential auth checks"""
    
    full_query_path = gen_flow2sink_query(language, appname)
    print(f"Running flow2sink query for {language}/{appname} @ {full_query_path}")

    sarif_output = get_flow2sink_sarif_file(appname)
    
    success = execute_query(
        query_path=full_query_path, 
        database_path=database, 
        output_file=sarif_output,
        query_wd= full_query_path.parent.parent # parent of tmp
    )
    
    if not success:
        print("Failed to execute CodeQL query")
        return None
        
    # print(f"Query results saved to: {sarif_output}")
    return sarif_output


def execute_flow2out_query(database: Path, appname: str, language: str) -> Optional[Path]:
    """Execute CodeQL query to find potential auth checks"""

    full_query_path = get_flow2out_query(language)
    print(f"Running flow2out query for {language}/{appname} @ {full_query_path}")
    
    sarif_output = get_flow2out_sarif_file(appname)
    
    success = execute_query(
        query_path=full_query_path, 
        database_path=database, 
        output_file=sarif_output,
        query_wd= full_query_path.parent # slightly different from above
    )
    
    if not success:
        print("Failed to execute CodeQL query")
        return None
        
    # print(f"Query results saved to: {sarif_output}")
    return sarif_output

def find_flow_main(database: Path, codebase: Path, appname: str, group_by: str):

    if check_status(appname, AnalysisStatus.FIND_FLOWS):
        print(f"{AnalysisStatus.FIND_FLOWS} is already done")
        return 0

    language = get_database_language(database)

    if not check_status(appname, AnalysisStatus.DUCKDB):
        # do duck
        from duck_db.create_duckdb import duckdb_main
        if duckdb_main(database, codebase, appname):
            update_status(appname, AnalysisStatus.DUCKDB)
    
    function_map = get_app_function_map_file(appname)
    database = get_app_database_dir(appname)

    print("=" * 50)
    sarif_file = execute_flow2sink_query(database, appname, language)
    if not sarif_file:
        return 1
    
    # Run extraction
    output_file = get_flow2sink_json_file(appname)
    extract_flows(sarif_file, codebase, group_by, output_file, function_map)


    sarif_file = execute_flow2out_query(database, appname, language)
    output_file = get_flow2out_json_file(appname)
    extract_flows(sarif_file, codebase, "sources", output_file, function_map) # we alreasy group by sources

    update_status(appname, AnalysisStatus.FIND_FLOWS)

    return 0
