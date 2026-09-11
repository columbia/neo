#!/usr/bin/env python3
"""
Refined Flow Validator
Validates extracted flow JSON using sequential LLM analysis with function database retrieval.
Each group gets a separate context, but all flows within a group share the same conversation context.

"""

import json, re, os
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path

from common.llms import LLMClient
from duck_db.create_duckdb import CallGraphDatabase
from common.helper import * 
from common.z3helper import check_z3_constraints
from common.library_semantics import LibrarySemanticsIndex

## support concurrency..
import asyncio
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


class IterativeFlowValidator:
    """Validates flow data using sequential LLM analysis with function database lookups"""
    
    def __init__(self, llm_client: LLMClient, db: CallGraphDatabase, source_root: Path, output_dir: Path,
                 cross_service: bool = False):
        self.llm = llm_client
        self.db = db
        self.source_root = Path(source_root)
        self.output_dir = Path(output_dir)
        self.cross_service = cross_service
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectory for LLM interaction logs
        self.llm_logs_dir = self.output_dir / "llm_interactions"
        self.llm_logs_dir.mkdir(parents=True, exist_ok=True)

        # Load library semantics index (optional — disabled if path not configured)
        semantics_path = os.environ.get("LIBRARY_SEMANTICS_PATH")
        if semantics_path is None:
            default_path = Path(__file__).parent.parent / "data" / "library_semantics.json"
            semantics_path = str(default_path)
        try:
            self._semantics = LibrarySemanticsIndex(Path(semantics_path))
        except FileNotFoundError:
            logger.warning(
                "Library semantics index not found at '%s'; library fallback disabled.",
                semantics_path,
            )
            self._semantics = None
    
    def load_flow_data(self, json_file: Path) -> Dict[str, Any]:
        """Load flow results JSON data"""
        json_file = Path(json_file)
        with open(json_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def create_single_flow_summary(self, flow_data: Dict[str, Any], flow_index: int, total_flows: int) -> str:
        """Create summary for a single flow"""
        steps = flow_data.get('steps', [])
        if not steps:
            return "No steps found in this flow"
        
        summary = f"Flow {flow_index + 1} of {total_flows}: {flow_data.get('flow_id', 'unknown')}\n"
        summary += f"Source: {flow_data.get('source_location', 'unknown')}\n"
        summary += f"Sink: {flow_data.get('sink_location', 'unknown')}\n\n"
        
        summary += "Execution steps:\n"
        for step in steps:
            step_role = step.get('step_role', 'Step ?')
            location = step.get('location', 'unknown')
            statement = step.get('statement', 'unknown')
            func_id = step.get('function_id', 'N/A')
            
            summary += f"- {step_role} @ {location}\n"
            summary += f"  Statement: {statement}\n"
            summary += f"  Containing Function (id) which you could request: {func_id}\n\n"
        
        return summary

    def create_flow_analysis_prompt(self, flow_data: Dict[str, Any], flow_index: int, total_flows: int, is_first_flow: bool = True) -> str:
        """Create prompt for analyzing a single flow"""
        flow_summary = self.create_single_flow_summary(flow_data, flow_index, total_flows)
        
        if self.cross_service:
            prompt_template = (
                load_validate_global_flow_prompt() if is_first_flow
                else load_validate_global_next_flow_prompt()
            )
        elif is_first_flow:
            prompt_template = load_validate_flow_prompt()
        else:
            prompt_template = load_validate_next_flow_prompt()

        return prompt_template.format(flow_summary=flow_summary)
        
    
    def create_iterative_analysis_prompt(self, group_data: Dict[str, Any], conversation_history: List[Dict], requested_functions: Dict[str, str]) -> str:
        """Create follow-up prompt with requested function definitions"""
        
        prompt = "Here are the function definitions you requested:\n\n"
        
        for func_request, func_code in requested_functions.items():
            if func_code:
                prompt += f"Function: {func_request}\n\n"
                prompt += "```\n"
                prompt += func_code
                prompt += "\n```\n\n"
            else:
                prompt += f"Function: {func_request}\nNot found in database\n\n"
        
        prompt += """Now, with this additional context, please provide your updated analysis following the same response format as before, e.g., <request>, <assessment>, <reasoning> tags."""
        return prompt
    
    def parse_function_requests(self, response_text: str) -> List[str]:
        """Parse function requests from LLM response using <request> tags

        Accepts multiple formats:
        1. Standard: function_name@file_path:line_number
        2. Class-qualified: ClassName.methodName
        3. Package-qualified: com.package.ClassName.methodName
        """
        requests = []

        # Look for <request> tags
        request_pattern = r'<request>(.*?)</request>'
        matches = re.findall(request_pattern, response_text, re.IGNORECASE | re.DOTALL)

        for match in matches:
            # Split by semicolon or newlines to handle multiple functions per tag
            func_list = re.split(r'[;\n]', match)

            for func_request in func_list:
                func_request = func_request.strip()

                # Skip empty requests
                if not func_request:
                    continue

                # Valid request formats:
                # 1. Standard: function_name@file_path:line (has @)
                # 2. Class-qualified: ClassName.methodName (has . but no @)
                # 3. Package-qualified: com.example.Class.method (has . but no @)

                if '@' in func_request:
                    # Standard format with file path - keep as is
                    requests.append(func_request)
                elif '.' in func_request and self._looks_like_class_method(func_request):
                    # Class-qualified format - try to resolve via name lookup
                    print(f"      Note: Accepting class-qualified request: {func_request}")
                    requests.append(func_request)
                else:
                    # Unrecognized format - skip with warning
                    if func_request:  # Don't warn about empty strings
                        print(f"      Warning: Skipping unrecognized request format: {func_request}")

        return requests

    def _looks_like_class_method(self, request: str) -> bool:
        """
        Detect if request looks like a class.method pattern

        Examples that should match:
        - SysRoleServiceImpl.deleteRoles ✓
        - com.youlai.system.service.impl.SysRoleServiceImpl.deleteRoles ✓
        - Service.method_name ✓ (underscore allowed)

        Examples that should NOT match:
        - just.some.random.text ✗
        - file.path.to.Something ✗
        - Service.method implementation ✗ (spaces not allowed)
        - Service.method-name ✗ (hyphens not allowed)
        """
        parts = request.split('.')
        if len(parts) < 2:
            return False

        # Last part should look like a method name (starts with lowercase)
        method_name = parts[-1]
        if not method_name or not method_name[0].islower():
            return False

        # Method names must be alphanumeric + underscore only (no spaces!)
        if not method_name.replace('_', '').isalnum():
            return False

        # Second-to-last part should look like a class name (starts with uppercase)
        class_name = parts[-2]
        if not class_name or not class_name[0].isupper():
            return False

        # Class names must be alphanumeric only
        if not class_name.isalnum():
            return False

        return True
    
    def parse_assessment(self, response_text: str) -> str:
        """Parse assessment from <assessment> tags"""
        assessment_pattern = r'<assessment>(.*?)</assessment>'
        match = re.search(assessment_pattern, response_text, re.IGNORECASE | re.DOTALL)
        
        if match:
            return match.group(1).strip()
        
        return 'Unknown'
    
    def parse_reasoning(self, response_text: str) -> str:
        """Parse reasoning from <reasoning> tags"""
        reason_pattern = r'<reasoning>(.*?)</reasoning>'
        match = re.search(reason_pattern, response_text, re.IGNORECASE | re.DOTALL)
        
        if match:
            return match.group(1).strip()
        
        return 'No reasoning provided'
    
    def parse_constraints(self, response_text: str) -> str:
        """Parse constraints from <constraints> tags"""
        constraints_pattern = r'<constraints>(.*?)</constraints>'
        match = re.search(constraints_pattern, response_text, re.IGNORECASE | re.DOTALL)

        if match:
            return match.group(1).strip()

        return 'No constraints provided'

    def save_llm_interaction(self, group_index: int, flow_index: int, iteration: int,
                            interaction_type: str, prompt: str, response: str = None,
                            requested_functions: Dict[str, str] = None) -> None:
        """
        Save LLM interaction (prompt and response) to log files

        Args:
            group_index: Index of the flow group
            flow_index: Index of the flow within the group
            iteration: Iteration number (0 for initial, 1+ for follow-ups)
            interaction_type: Type of interaction ('initial', 'followup')
            prompt: The prompt sent to the LLM
            response: The response received from the LLM (optional)
            requested_functions: Dict of requested function code (optional)
        """
        # Create group-specific subdirectory
        group_dir = self.llm_logs_dir / f"group_{group_index:03d}"
        group_dir.mkdir(parents=True, exist_ok=True)

        # Create filename with flow and iteration info
        base_filename = f"flow_{flow_index:02d}_iter_{iteration:02d}_{interaction_type}"

        # Save the prompt (input to LLM)
        prompt_file = group_dir / f"{base_filename}_prompt.txt"
        with open(prompt_file, 'w', encoding='utf-8') as f:
            f.write("=" * 100 + "\n")
            f.write(f"LLM INPUT - Group {group_index}, Flow {flow_index}, Iteration {iteration}\n")
            f.write(f"Type: {interaction_type}\n")
            f.write("=" * 100 + "\n\n")
            f.write(prompt)
            f.write("\n")

        # Save requested functions if provided (for follow-up interactions)
        if requested_functions:
            functions_file = group_dir / f"{base_filename}_functions.txt"
            with open(functions_file, 'w', encoding='utf-8') as f:
                f.write("=" * 100 + "\n")
                f.write(f"REQUESTED FUNCTIONS - Group {group_index}, Flow {flow_index}, Iteration {iteration}\n")
                f.write("=" * 100 + "\n\n")
                for func_id, func_code in requested_functions.items():
                    f.write(f"\n{'=' * 100}\n")
                    f.write(f"Function: {func_id}\n")
                    f.write(f"{'=' * 100}\n\n")
                    f.write(func_code)
                    f.write("\n\n")

        # Save the response (output from LLM)
        if response:
            response_file = group_dir / f"{base_filename}_response.txt"
            with open(response_file, 'w', encoding='utf-8') as f:
                f.write("=" * 100 + "\n")
                f.write(f"LLM OUTPUT - Group {group_index}, Flow {flow_index}, Iteration {iteration}\n")
                f.write(f"Type: {interaction_type}\n")
                f.write("=" * 100 + "\n\n")
                f.write(response)
                f.write("\n")

    
    def resolve_function_request(self, func_request: str) -> Optional[str]:
        """Resolve function request to source code using database"""
        # Use the new unified lookup method (returns list)
        # Pass source_root for class file fallback
        functions = self.db.get_function_by_identifier(func_request, source_root=self.source_root)
        
        if not functions:
            # Fallback: library semantics index
            if self._semantics is not None:
                semantics = self._semantics.lookup(func_request)
                if semantics:
                    return semantics
            return None
        
        if len(functions) == 1:
            # Single match - return as before
            function_info = functions[0]
            source_code = self.db.get_function_source_code(function_info, self.source_root)
            if source_code:
                result = [f"File: {function_info['file_path']}"]
                
                # Add router info if available
                if 'router_info' in function_info:
                    router_info = function_info['router_info']
                    result.append(f"Router Definition: {router_info['router_definition_id']}")
                    result.append(f"Router Source:\n{router_info['router_source_code']}")
                    result.append("")  # Empty line separator
                
                result.append(source_code)
                return "\n".join(result)
        else:
            # Multiple matches - return all with clear separation
            results = []
            results.append(f"Found {len(functions)} functions matching '{func_request}':\n")
            
            for i, function_info in enumerate(functions, 1):
                source_code = self.db.get_function_source_code(function_info, self.source_root)
                if source_code:
                    results.append(f"=== Match {i}: {function_info['function_id']} ===")
                    results.append(f"File: {function_info['file_path']}")
                    
                    # Add router info if available
                    if 'router_info' in function_info:
                        router_info = function_info['router_info']
                        results.append(f"Router Definition: {router_info['router_definition_id']}")
                        results.append(f"Router Source:\n{router_info['router_source_code']}")
                        results.append("")  # Empty line separator
                    
                    results.append(source_code)
                    results.append("")  # Empty line separator
            
            if len(results) > 1:  # More than just the header
                return "\n".join(results)

        # Fallback: library semantics index
        if self._semantics is not None:
            semantics = self._semantics.lookup(func_request)
            if semantics:
                return semantics

        return None
    
    
    async def validate_flow_groups_concurrent(self, flow_file: Path, max_groups: Optional[int] = None, max_concurrent_groups: int = 3, max_iterations: int = 5) -> None:
        """Main validation pipeline with concurrent group processing"""
        flow_file = Path(flow_file)
        print(f"Loading flow data from: {flow_file}")
        
        flow_data = self.load_flow_data(flow_file)
        grouped_flows = flow_data.get('grouped_flows', {})
        metadata = flow_data.get('metadata', {})
        
        # Convert grouped flows to list format
        flow_groups = []
        for group_key, flows in grouped_flows.items():
            flow_groups.append({
                'group_key': group_key,
                'flows': flows
            })
        
        if max_groups:
            flow_groups = flow_groups[:max_groups]
            print(f"Limiting analysis to first {max_groups} groups")
        
        print(f"Analyzing {len(flow_groups)} flow groups with {max_concurrent_groups} concurrent groups...")
        
        # Create semaphore to limit concurrent groups (for rate limiting)
        semaphore = asyncio.Semaphore(max_concurrent_groups)
        
        async def validate_single_group(group_data: Dict[str, Any], group_index: int) -> Dict[str, Any]:
            """Validate a single group with rate limiting"""
            async with semaphore:
                print(f"Starting group {group_index+1}/{len(flow_groups)}: {group_data['group_key']}")
                
                # Run the sequential group validation in thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                validation = await loop.run_in_executor(
                    None,
                    self.validate_flow_group_sequentially,
                    group_data,
                    group_index,
                    max_iterations
                )
                
                # Save individual validation
                group_file = self.output_dir / f"group_{group_index:03d}_validation.json"
                with open(group_file, 'w', encoding='utf-8') as f:
                    json.dump(validation, f, indent=2)
                
                print(f"Completed group {group_index+1}: {group_data['group_key']}")
                return validation
        
        # Create tasks for all groups
        tasks = [
            validate_single_group(group_data, i) 
            for i, group_data in enumerate(flow_groups)
        ]
        
        # Execute all groups concurrently (with semaphore limiting)
        validations = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions and create clean validation list
        successful_validations = []
        for i, result in enumerate(validations):
            if isinstance(result, Exception):
                print(f"ERROR: Group {i} ({flow_groups[i]['group_key']}) failed: {result}")
                # Create error result for consistency
                error_validation = {
                    'group_index': i,
                    'group_key': flow_groups[i]['group_key'],
                    'success': False,
                    'error': str(result),
                    'flow_analyses': [],
                    'requested_function_ids': [],
                    'total_iterations': 0
                }
                successful_validations.append(error_validation)
            else:
                successful_validations.append(result)
        
        print("Generating validation summary...")
        summary_report = self.create_group_summary_report(successful_validations, metadata)
        
        # Save detailed summary
        summary_file = self.output_dir / "validation_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary_report, f, indent=2)
        
        # Save only positive vulnerabilities
        self.save_positive_vulnerabilities_sink(successful_validations, self.output_dir)
        
        print(f"\nConcurrent flow validation complete!")
        print(f"Results saved to: {self.output_dir}")
        
        # Print summary stats
        successful_groups = sum(1 for v in successful_validations if v.get('success', False))
        failed_groups = len(successful_validations) - successful_groups
        print(f"Successfully processed: {successful_groups}/{len(flow_groups)} groups")
        if failed_groups > 0:
            print(f"Failed groups: {failed_groups}")


    def validate_flow_groups(self, flow_file: Path, max_groups: Optional[int] = None, max_iterations: int = 5) -> None:
        """Main validation pipeline for flow groups with sequential flow analysis"""
        flow_file = Path(flow_file)
        print(f"Loading flow data from: {flow_file}")
        
        flow_data = self.load_flow_data(flow_file)
        grouped_flows = flow_data.get('grouped_flows', {})
        metadata = flow_data.get('metadata', {})
        
        # Convert grouped flows to list format
        flow_groups = []
        for group_key, flows in grouped_flows.items():
            flow_groups.append({
                'group_key': group_key,
                'flows': flows
            })
        
        if max_groups:
            flow_groups = flow_groups[:max_groups]
            print(f"Limiting analysis to first {max_groups} groups")
        
        print(f"Analyzing {len(flow_groups)} flow groups sequentially...")
        
        validations = []
        for i, group_data in enumerate(flow_groups):
            print(f"Validating group {i+1}/{len(flow_groups)}: {group_data['group_key']}")

            validation = self.validate_flow_group_sequentially(group_data, i, max_iterations)
            validations.append(validation)
            
            # Save individual validation
            group_file = self.output_dir / f"group_{i:03d}_validation.json"
            with open(group_file, 'w', encoding='utf-8') as f:
                json.dump(validation, f, indent=2)

        print("Generating validation summary...")
        summary_report = self.create_group_summary_report(validations, metadata)
        
        # Save detailed summary
        summary_file = self.output_dir / "validation_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary_report, f, indent=2)
        
        # Save only positive vulnerabilities
        # we deduplicate by the sinks (sources all considered as one)
        self.save_positive_vulnerabilities_sink(validations, self.output_dir)
        
        print(f"\nSequential flow validation complete!")
        print(f"Results saved to: {self.output_dir}")


    def validate_flow_group_sequentially(self, group_data: Dict[str, Any], group_index: int, max_iterations: int = 5) -> Dict[str, Any]:
        """Validate a flow group by analyzing each flow sequentially in the same conversation"""
        group_key = group_data.get('group_key', f'group_{group_index}')
        flows = group_data.get('flows', [])

        if not flows:
            return {
                'group_index': group_index,
                'group_key': group_key,
                'success': False,
                'error': 'No flows in group',
                'flow_analyses': [],
                'requested_function_ids': []  # Add empty list for consistency
            }

        print(f"  Starting sequential analysis for group: {group_key} ({len(flows)} flows)")

        conversation_history = []  # Fresh context for this group
        flow_analyses = []
        total_iterations = 0

        # Track all requested function IDs for this group
        group_requested_function_ids = []

        # Create summary log for this group
        group_dir = self.llm_logs_dir / f"group_{group_index:03d}"
        group_dir.mkdir(parents=True, exist_ok=True)
        summary_file = group_dir / "interaction_summary.txt"
        summary_lines = []
        summary_lines.append("=" * 100)
        summary_lines.append(f"LLM INTERACTION SUMMARY - Group {group_index}")
        summary_lines.append(f"Group Key: {group_key}")
        summary_lines.append(f"Total Flows: {len(flows)}")
        summary_lines.append("=" * 100)
        summary_lines.append("")
        
        try:
            for flow_idx, flow_data in enumerate(flows):
                print(f"    Analyzing flow {flow_idx + 1}/{len(flows)}: {flow_data.get('flow_id', 'unknown')}")
                
                # Create prompt for this flow
                is_first_flow = (flow_idx == 0)
                flow_prompt = self.create_flow_analysis_prompt(flow_data, flow_idx, len(flows), is_first_flow)

                # Send initial analysis request
                response = self.llm.messages_create(
                    history=conversation_history,  # Shared context within group
                    message=[{"role": "user", "content": flow_prompt}],
                    max_tokens=4000,
                    temperature=0.1
                )

                response_text = response.content[0].text.strip()
                conversation_history.append({"role": "user", "content": flow_prompt})
                conversation_history.append({"role": "assistant", "content": response_text})

                # Save LLM interaction to log files
                self.save_llm_interaction(
                    group_index=group_index,
                    flow_index=flow_idx,
                    iteration=0,
                    interaction_type='initial',
                    prompt=flow_prompt,
                    response=response_text
                )

                # Add to summary
                summary_lines.append(f"Flow {flow_idx} - Iteration 0 (Initial):")
                summary_lines.append(f"  Prompt length: {len(flow_prompt)} chars")
                summary_lines.append(f"  Response length: {len(response_text)} chars")
                summary_lines.append("")
                
                # Track requested function IDs for this flow
                flow_requested_function_ids = []
                
                # Handle iterative function requests for this flow
                flow_iterations = 0
                while flow_iterations < max_iterations:
                    function_requests = self.parse_function_requests(response_text)
                    
                    if not function_requests:
                        # No more function requests, this flow analysis is complete
                        break
                    
                    print(f"      Flow {flow_idx + 1} iteration {flow_iterations + 1}: Requesting {len(function_requests)} function requests")
                    
                    # Add function requests to flow and group tracking
                    flow_requested_function_ids.extend(function_requests)
                    group_requested_function_ids.extend(function_requests)
                    
                    # Resolve requested functions
                    requested_functions = {}
                    for func_request in function_requests:
                        func_code = self.resolve_function_request(func_request)
                        if func_code:
                            requested_functions[func_request] = func_code
                            print(f"        {func_request}")
                        else:
                            requested_functions[func_request] = "FUNCTION IS NOT FOUND\n"
                            print(f"        !!!!{func_request} NOT RESOLVED!!!!")
                    
                    # Send follow-up with function definitions
                    follow_up_prompt = self.create_iterative_analysis_prompt(group_data, conversation_history, requested_functions)

                    response = self.llm.messages_create(
                        history=conversation_history,  # Same conversation continues
                        message=[{"role": "user", "content": follow_up_prompt}],
                        max_tokens=4000,
                        temperature=0.1
                    )

                    response_text = response.content[0].text.strip()
                    conversation_history.append({"role": "user", "content": follow_up_prompt})
                    conversation_history.append({"role": "assistant", "content": response_text})

                    # Save LLM interaction to log files (with function code)
                    self.save_llm_interaction(
                        group_index=group_index,
                        flow_index=flow_idx,
                        iteration=flow_iterations + 1,
                        interaction_type='followup',
                        prompt=follow_up_prompt,
                        response=response_text,
                        requested_functions=requested_functions
                    )

                    # Add to summary
                    summary_lines.append(f"Flow {flow_idx} - Iteration {flow_iterations + 1} (Follow-up):")
                    summary_lines.append(f"  Functions requested: {len(requested_functions)}")
                    summary_lines.append(f"  Prompt length: {len(follow_up_prompt)} chars")
                    summary_lines.append(f"  Response length: {len(response_text)} chars")
                    summary_lines.append("")

                    flow_iterations += 1
                    total_iterations += 1
                

                assessment = self.parse_assessment(response_text).strip()
                reasoning =  self.parse_reasoning(response_text).strip()
                constraints = self.parse_constraints(response_text).strip()

                if assessment == 'True Positive':
                    z3_ret = check_z3_constraints(constraints)
                else:
                    z3_ret = {'valid_syntax': False, 'satisfiable': 'skipped', 'errors': [], 'model': {}}
                # Parse results for this individual flow
                flow_analysis = {
                    'flow_index': flow_idx,
                    'flow_id': flow_data.get('flow_id', f'flow_{flow_idx}'),
                    'source_location': flow_data.get('source_location', 'unknown'),
                    'sink_location': flow_data.get('sink_location', 'unknown'),
                    'vulnerability_assessment': assessment,
                    'reasoning': reasoning,
                    'constraints': constraints,
                    'constraints_solver': z3_ret,
                    'iterations_used': flow_iterations,
                    'requested_function_ids': flow_requested_function_ids,  # Add requested function IDs per flow
                    'raw_response': response_text
                }

                
                flow_analyses.append(flow_analysis)
            
            # Remove duplicates from group-level function ID tracking
            group_requested_function_ids = list(set(group_requested_function_ids))
            
            # Create summary for the group
            true_positives = sum(1 for f in flow_analyses if f['vulnerability_assessment'] == 'True Positive')
            false_positives = sum(1 for f in flow_analyses if f['vulnerability_assessment'] == 'False Positive')
            unknowns = sum(1 for f in flow_analyses if f['vulnerability_assessment'] == 'Unknown')
            needs_context = sum(1 for f in flow_analyses if f['vulnerability_assessment'] == 'Needs More Context')
            
            # Categorize flow IDs by assessment
            tp_flow_ids = [f['flow_id'] for f in flow_analyses if f['vulnerability_assessment'] == 'True Positive']
            fp_flow_ids = [f['flow_id'] for f in flow_analyses if f['vulnerability_assessment'] == 'False Positive']
            nc_flow_ids = [f['flow_id'] for f in flow_analyses if f['vulnerability_assessment'] == 'Needs More Context']
            unknown_flow_ids = [f['flow_id'] for f in flow_analyses if f['vulnerability_assessment'] == 'Unknown']
            
            # Write summary file
            summary_lines.append("=" * 100)
            summary_lines.append("GROUP RESULTS SUMMARY")
            summary_lines.append("=" * 100)
            summary_lines.append(f"True Positives: {true_positives}")
            summary_lines.append(f"False Positives: {false_positives}")
            summary_lines.append(f"Needs More Context: {needs_context}")
            summary_lines.append(f"Unknown: {unknowns}")
            summary_lines.append(f"Total Iterations: {total_iterations}")
            summary_lines.append(f"Average Iterations per Flow: {round(total_iterations / len(flows), 1) if flows else 0}")
            summary_lines.append(f"Total Unique Functions Requested: {len(group_requested_function_ids)}")
            summary_lines.append("=" * 100)

            with open(summary_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(summary_lines))

            group_result = {
                'group_index': group_index,
                'group_key': group_key,
                'success': True,
                'total_flows': len(flows),
                'flow_analyses': flow_analyses,  # Individual TP/FP results for each flow
                'requested_function_ids': group_requested_function_ids,  # Add group-level requested function IDs
                'group_summary': {
                    'true_positives': true_positives,
                    'false_positives': false_positives,
                    'needs_more_context': needs_context,
                    "unknowns": unknowns,
                    'total_iterations': total_iterations,
                    'avg_iterations_per_flow': round(total_iterations / len(flows), 1) if flows else 0,
                    'total_requested_functions': len(group_requested_function_ids),  # Add count of unique requested functions
                    'flow_ids_by_assessment': {
                        'true_positive_flows': tp_flow_ids,
                        'false_positive_flows': fp_flow_ids,
                        'needs_context_flows': nc_flow_ids,
                        'unknown_flows': unknown_flow_ids
                    }
                },
                'conversation_history': conversation_history
            }
            return group_result
            
        except Exception as e:
            print(f"DEBUG: Exception in group validation: {e}")
            print(f"DEBUG: Exception type: {type(e)}")
            import traceback
            traceback.print_exc()
            return {
                'group_index': group_index,
                'group_key': group_key,
                'success': False,
                'error': str(e),
                'flow_analyses': flow_analyses,  # Partial results
                'requested_function_ids': group_requested_function_ids,  # Add even for failed groups
                'total_iterations': total_iterations
            }
    
    def create_group_summary_report(self, validations: List[Dict[str, Any]], metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create summary report of sequential flow validation results"""
        total_groups = len(validations)
        total_flows = 0
        total_true_positives = 0
        total_false_positives = 0
        total_needs_context = 0
        total_unknown = 0
        errors = sum(1 for v in validations if not v.get('success', True))
        total_iterations = 0
        z3_tp_counts = {
            'sat': 0,
            'unsat': 0,
            'unknown': 0,
            'error': 0,
        }
        
        # Collect all flow IDs by category across all groups
        all_tp_flows = []
        all_fp_flows = []
        all_nc_flows = []
        all_unknown_flows = []
        z3_tp_flow_ids = {
            'sat': [],
            'unsat': [],
            'unknown': [],
            'error': [],
        }
        
        # Collect all requested function IDs across all groups
        all_requested_function_ids = []
        
        # Aggregate flow-level results
        for validation in validations:
            if validation.get('success'):
                total_flows += validation.get('total_flows', 0)
                group_summary = validation.get('group_summary', {})

                total_true_positives += group_summary.get('true_positives', 0)
                all_tp_flows.extend(group_summary.get('flow_ids_by_assessment', {}).get('true_positive_flows', []))

                total_false_positives += group_summary.get('false_positives', 0)
                all_fp_flows.extend(group_summary.get('flow_ids_by_assessment', {}).get('false_positive_flows', []))

                total_unknown += group_summary.get('unknowns', 0)
                all_unknown_flows.extend(group_summary.get('flow_ids_by_assessment', {}).get('unknown_flows', []))

                total_needs_context += group_summary.get('needs_more_context', 0)
                all_nc_flows.extend(group_summary.get('flow_ids_by_assessment', {}).get('needs_context_flows', []))
                
                total_iterations += group_summary.get('total_iterations', 0)
                
                # Collect requested function IDs from this group
                group_function_ids = validation.get('requested_function_ids', [])
                all_requested_function_ids.extend(group_function_ids)

                for flow_analysis in validation.get('flow_analyses', []):
                    if flow_analysis.get('vulnerability_assessment') != 'True Positive':
                        continue
                    z3_bucket = self._classify_z3_true_positive(flow_analysis.get('constraints_solver', {}))
                    z3_tp_counts[z3_bucket] += 1
                    z3_tp_flow_ids[z3_bucket].append(flow_analysis.get('flow_id'))
        
        # Remove duplicates from function IDs across all groups
        unique_requested_function_ids = list(set(all_requested_function_ids))
        
        # Average iterations per flow
        avg_iterations = total_iterations / max(total_flows, 1)
        
        return {
            'summary': {
                'total_groups_analyzed': total_groups,
                'total_flows_analyzed': total_flows,
                'true_positives': total_true_positives,
                'pre_z3_true_positives': total_true_positives,
                'post_z3_true_positives': (
                    total_true_positives if os.getenv("Z3_PRUNE_UNSAT", "1") == "0"
                    else total_true_positives - z3_tp_counts['unsat']
                ),
                'z3_pruned_true_positives': (
                    0 if os.getenv("Z3_PRUNE_UNSAT", "1") == "0" else z3_tp_counts['unsat']
                ),
                'false_positives': total_false_positives,
                'needs_more_context': total_needs_context,
                'analysis_errors': errors,
                'vulnerability_rate': round((total_true_positives / max(total_flows, 1)) * 100, 1),
                'false_positive_rate': round((total_false_positives / max(total_flows, 1)) * 100, 1),
                'average_iterations_per_flow': round(avg_iterations, 1),
                'total_unique_requested_functions': len(unique_requested_function_ids),  # Add summary stat
                'source_metadata': metadata,
                'llm_model': self.llm.get_model_name(),
                'flow_ids_by_assessment': {
                    'true_positive_flows': all_tp_flows,
                    'false_positive_flows': all_fp_flows,
                    'needs_context_flows': all_nc_flows,
                    'unknown_flows': all_unknown_flows
                },
                'z3_true_positive_breakdown': {
                    'sat': z3_tp_counts['sat'],
                    'unsat': z3_tp_counts['unsat'],
                    'unknown': z3_tp_counts['unknown'],
                    'error': z3_tp_counts['error'],
                    'sat_flow_ids': z3_tp_flow_ids['sat'],
                    'unsat_flow_ids': z3_tp_flow_ids['unsat'],
                    'unknown_flow_ids': z3_tp_flow_ids['unknown'],
                    'error_flow_ids': z3_tp_flow_ids['error'],
                },
                'all_requested_function_ids': unique_requested_function_ids  # Add global list of requested function IDs
            }
        }

    @staticmethod
    def _classify_z3_true_positive(constraints_solver: Dict[str, Any]) -> str:
        """Bucket a true-positive flow by its Z3 outcome."""
        satisfiable = constraints_solver.get('satisfiable')
        valid_syntax = constraints_solver.get('valid_syntax', False)

        if valid_syntax and satisfiable == 'sat':
            return 'sat'
        if valid_syntax and satisfiable == 'unsat':
            return 'unsat'
        if valid_syntax and satisfiable == 'unknown':
            return 'unknown'
        return 'error'

    @staticmethod
    def _z3_prunes_flow(flow_analysis: Dict[str, Any]) -> bool:
        """
        True when the path-constraint check proved this True-Positive infeasible.

        Per the paper (§4.4): an *unsatisfiable* constraint set means the flow
        cannot actually be exercised, so it is dropped as a false positive.
        Only a confidently `unsat` result prunes — `unknown` / `error` / `empty`
        (e.g. a Z3 timeout, or the LLM declining to model a complex path) are
        kept, i.e. the check is conservative.  Set ``Z3_PRUNE_UNSAT=0`` to
        record the verdict without acting on it.
        """
        if os.getenv("Z3_PRUNE_UNSAT", "1") == "0":
            return False
        cs = flow_analysis.get('constraints_solver', {}) or {}
        return bool(cs.get('valid_syntax')) and cs.get('satisfiable') == 'unsat'

    def save_positive_vulnerabilities_sink(self, validations: List[Dict[str, Any]], output_dir: Path) -> None:
        """Save only true positive vulnerabilities after validation, grouped by sink"""
        
        # Extract sinks that have at least one TP flow
        tp_vulnerabilities = {}
        pruned_by_z3: List[str] = []

        for validation in validations:
            if not validation.get('success'):
                continue
                
            for flow_analysis in validation.get('flow_analyses', []):
                if flow_analysis['vulnerability_assessment'] != 'True Positive':
                    continue

                if self._z3_prunes_flow(flow_analysis):
                    pruned_by_z3.append(flow_analysis['flow_id'])
                    print(f"  [z3] dropping {flow_analysis['flow_id']} — path constraints UNSAT")
                    continue

                source = flow_analysis['source_location']
                sink = flow_analysis['sink_location']
                flow_id = flow_analysis['flow_id']

                # Use only sink as the key
                if sink not in tp_vulnerabilities:
                    tp_vulnerabilities[sink] = {
                        "sink": sink,
                        "sources": set(),
                        "tp_flows": []
                    }
                tp_vulnerabilities[sink]["sources"].add(source)
                tp_vulnerabilities[sink]["tp_flows"].append(flow_id)
        
        # Create final vulnerability list
        vulnerabilities = [
            {
                "id": f"V{i:03d}",
                "sink": vuln["sink"],
                "sources": list(vuln["sources"]),  # Convert set to list for JSON serialization
                "flows": vuln["tp_flows"]
            }
            for i, vuln in enumerate(tp_vulnerabilities.values(), 1)
        ]

        result = {
            "total_vulnerabilities": len(vulnerabilities),
            "vulnerabilities": vulnerabilities,
            "z3_pruned_flows": pruned_by_z3,
        }

        # Save to file
        output_file = output_dir / "vulnerabilities.json"
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)

        print(f"Found {len(vulnerabilities)} vulnerabilities"
              + (f" ({len(pruned_by_z3)} pruned by Z3 as infeasible)" if pruned_by_z3 else ""))
        if vulnerabilities:
            print("VULNERABILITIES DETECTED - see vulnerabilities.json")


    def save_positive_vulnerabilities(self, validations: List[Dict[str, Any]], output_dir: Path) -> None:
        """Save only true positive vulnerabilities after validation"""
        
        # Extract source-sink pairs that have at least one TP flow
        tp_vulnerabilities = {}
        
        for validation in validations:
            if not validation.get('success'):
                continue
                
            for flow_analysis in validation.get('flow_analyses', []):
                if flow_analysis['vulnerability_assessment'] != 'True Positive':
                    continue
                    
                source = flow_analysis['source_location']
                sink = flow_analysis['sink_location']
                flow_id = flow_analysis['flow_id']
                
                key = f"{source} → {sink}"
                if key not in tp_vulnerabilities:
                    tp_vulnerabilities[key] = {
                        "source": source,
                        "sink": sink,
                        "tp_flows": []
                    }
                tp_vulnerabilities[key]["tp_flows"].append(flow_id)
        
        # Create final vulnerability list
        vulnerabilities = [
            {
                "id": f"V{i:03d}",
                "source": vuln["source"],
                "sink": vuln["sink"],
                "flows": vuln["tp_flows"]
            }
            for i, vuln in enumerate(tp_vulnerabilities.values(), 1)
        ]
        
        result = {
            "total_vulnerabilities": len(vulnerabilities),
            "vulnerabilities": vulnerabilities
        }
        
        # Save to file
        output_file = output_dir / "vulnerabilities.json"
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        print(f"Found {len(vulnerabilities)} vulnerabilities")
        if vulnerabilities:
            print("VULNERABILITIES DETECTED - see vulnerabilities.json")


def validate_flow_main(llm_client: LLMClient, appname: str, max_validation_group: Optional[int] = None) -> bool:

    if check_status(appname, AnalysisStatus.VALIDATE_FLOWS):
        print(f"{AnalysisStatus.VALIDATE_FLOWS} is already done")
        return 0

    if max_validation_group is None:
        env_cap = os.getenv("MAX_VALIDATION_GROUPS")
        if env_cap:
            try:
                max_validation_group = int(env_cap)
                print(f"MAX_VALIDATION_GROUPS={max_validation_group} (from env)")
            except ValueError:
                pass
    
    
    codebase = get_app_source_dir(appname)
    database = get_app_database_dir(appname)
    if not codebase.exists():
        print(f"Error: Source root not found: {codebase}")
        return 1
    

    if not check_status(appname, AnalysisStatus.FIND_FLOWS):
        print(f" Find flow has not been done, do that first!")
        return 1
    
    if not check_status(appname, AnalysisStatus.DUCKDB):
        # do duck
        from duck_db.create_duckdb import duckdb_main
        if duckdb_main(database, codebase, appname):
            update_status(appname, AnalysisStatus.DUCKDB)

    _duckdb = get_app_duckdb_file(appname)
    flows = get_flow2sink_json_file(appname)
    
    if not flows.exists():
        print(f"Error: Flow file not found: {flows}")
        return 1
    

    
    db = CallGraphDatabase(_duckdb)
    output_dir = get_flow2sink_validation_dir(appname)
    validator = IterativeFlowValidator(llm_client, db, codebase, output_dir)
    
    max_concurrent_groups = int(os.getenv('MAX_CONCURRENT_GROUPS', '3'))
    max_iterations = int(os.getenv('MAX_ITERATIONS', '5'))
    print(f"Using max_iterations: {max_iterations} (set via MAX_ITERATIONS env var, default: 5)")
    asyncio.run(validator.validate_flow_groups_concurrent(flows, max_validation_group, max_concurrent_groups, max_iterations))
    
    db.close()
    update_status(appname, AnalysisStatus.VALIDATE_FLOWS)
    return 0
    
