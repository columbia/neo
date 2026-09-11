#!/usr/bin/env python3
"""
There are three sarif files are input so we parse them and validate them
We output a json file and generate sink query lib that can be imported by flow.ql
"""
import json
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

from common.llms import LLMClient
from common.helper import *
from common.codeql import execute_query
from genquery.gen_checked_op import gen_checked_op_query
from .parse_sarif_check import parse_check


class AuthCheckValidator:
    """Validates authentication check JSON using LLM analysis"""
    
    def __init__(self, llm_client: LLMClient, output_dir: str):
        self.llm = llm_client
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def add_line_numbers_and_mark_auth_checks(self, source_code: str, start_line: int, auth_checks: List, file_path: str) -> str:
        """Add line numbers and mark auth check lines with comments"""
        lines = source_code.split('\n')
        numbered_lines = []
        
        # Create set of auth check line numbers for quick lookup
        auth_lines = set()
        for check in auth_checks:
            if hasattr(check, 'line'):
                auth_lines.add(check.line)
            elif isinstance(check, dict) and 'line' in check:
                auth_lines.add(check['line'])
        
        for i, line in enumerate(lines):
            line_number = start_line + i
            if line_number in auth_lines:
                numbered_lines.append(f"{line_number:4d}: {line}  // <-- Potential authN/authZ check")
            else:
                numbered_lines.append(f"{line_number:4d}: {line}")
        
        return '\n'.join(numbered_lines)

    def load_auth_data(self, json_file: str) -> Dict[str, Any]:
        """Load authentication check JSON data"""
        with open(json_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def create_validation_prompt(self, method_data: Dict[str, Any], method_index: int) -> str:
        """Create LLM prompt for validating authentication checks and privileged operations"""
        
        file_path = method_data.get('method_location', {}).get('file', 'Unknown')
        
        findings_details = f"\nFinding {method_index}:\n"
        findings_details += f"Method Location: Lines {method_data.get('method_location', {}).get('start_line', '?')}-{method_data.get('method_location', {}).get('end_line', '?')}\n"
        findings_details += f"Source Code with Line Numbers:\n```\n{method_data.get('method_source_with_lines', 'Source not available')}\n```\n"
        findings_details += f"Identified Potential Checks:\n"
        
        for i, check in enumerate(method_data.get('auth_checks', []), 1):
            findings_details += f"Check {i}: Line {check.get('line', '?')} - `{check.get('expression', 'Unknown')}`\n"
        

        prompt = load_validate_check_prompt().format(file_path=file_path, findings_details=findings_details)
        return prompt

    def parse_structured_response(self, response_text: str, method_id: str, file_path: str) -> Dict[str, Any]:
        """Parse the simplified structured response from the LLM analysis"""
        
        result = {
            'method_id': method_id,
            'raw_response': response_text,
            'file_path': file_path,
            'check_results': [],
            'summary': {
                'total_checks_analyzed': 0,
                'genuine_auth_checks': 0,
                'not_auth_checks': 0,
                'privileged_operations_found': 0
            }
        }
        
        # Parse the simplified format
        lines = response_text.split('\n')
        current_check = {}
        
        for line in lines:
            line = line.strip()
            
            if line.startswith('Check Line:'):
                # Save previous check if exists
                if current_check:
                    result['check_results'].append(current_check)
                    
                # Start new check
                try:
                    check_line = int(line.split(':', 1)[1].strip())
                    current_check = {'check_line': check_line}
                    result['summary']['total_checks_analyzed'] += 1
                except:
                    current_check = {'check_line': None}
                    
            elif line.startswith('Check Type:'):
                check_type = line.split(':', 1)[1].strip()
                current_check['check_type'] = check_type
                
                if check_type in ['Authentication Check', 'Authorization Check']:
                    result['summary']['genuine_auth_checks'] += 1
                elif check_type == 'Not AuthN/AuthZ Check':
                    result['summary']['not_auth_checks'] += 1
                    
            elif line.startswith('Guarded Operations:'):
                operations_str = line.split(':', 1)[1].strip()
                current_check['guarded_operations'] = operations_str
                
                # Count operations
                if operations_str and operations_str != 'N/A':
                    operations = [op.strip() for op in operations_str.split('|') if op.strip()]
                    result['summary']['privileged_operations_found'] += len(operations)
                    
            elif line.startswith('Reason:'):
                reason = line.split(':', 1)[1].strip()
                current_check['reason'] = reason
        
        # Add last check
        if current_check:
            result['check_results'].append(current_check)
        
        return result

    def validate_method(self, method_data: Dict[str, Any], method_index: int) -> Dict[str, Any]:
        """Validate a single method using LLM with structured prompt"""
        
        prompt = self.create_validation_prompt(method_data, method_index)
        method_id = method_data.get('id', f'method_{method_index}')
        
        try:
            response = self.llm.messages_create(
                history=[],
                message=[{"role": "user", "content": prompt}],
                max_tokens=3000,
                temperature=0.1
            )
            file_path = method_data.get('method_location', {}).get('file', 'Unknown')
            response_text = response.content[0].text.strip()
            result = self.parse_structured_response(response_text, method_id, file_path)
            return result
            
        except Exception as e:
            return {
                'method_id': method_id,
                'error': str(e),
                'check_analyses': [],
                'summary': {
                    'total_checks_analyzed': 0,
                    'genuine_auth_checks': 0,
                    'not_security_checks': 0,
                    'privileged_operations_found': 0
                }
            }

    def create_summary_report(self, validations: List[Dict[str, Any]], metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create summary report focused on check-operation pairs"""
        
        total_methods = len(validations)
        total_checks_analyzed = sum(v.get('summary', {}).get('total_checks_analyzed', 0) for v in validations)
        
        check_operation_pairs = []
        all_privileged_operations = []
        genuine_security_checks = 0
        false_positives = 0
        
        for validation in validations:
            method_id = validation.get('method_id', 'unknown')
            
            for check in validation.get('check_results', []):
                if check.get('check_type') in ['Authentication Check', 'Authorization Check']:
                    genuine_security_checks += 1
                    
                    guarded_ops = check.get('guarded_operations', '')
                    if guarded_ops and guarded_ops != 'N/A':
                        # Parse operations in format: operation1@line | operation2@line
                        operations = []
                        for op_str in guarded_ops.split('|'):
                            op_str = op_str.strip()
                            if '@' in op_str:
                                operation, line_str = op_str.split('@', 1)
                                try:
                                    line_number = int(line_str.strip())
                                except:
                                    line_number = None
                            else:
                                operation = op_str
                                line_number = None
                            
                            if operation:
                                pair = {
                                    'method_id': method_id,
                                    'check_type': check.get('check_type'),
                                    'check_line': check.get('check_line'),
                                    'operation': operation.strip(),
                                    'operation_line': line_number
                                }
                                check_operation_pairs.append(pair)
                                all_privileged_operations.append(operation.strip())
                            
                elif check.get('check_type') == 'Not AuthN/AuthZ Check':
                    false_positives += 1
        
        operation_counts = {}
        for op in all_privileged_operations:
            operation_counts[op] = operation_counts.get(op, 0) + 1
        
        pairs_by_operation = {}
        for pair in check_operation_pairs:
            op = pair['operation']
            if op not in pairs_by_operation:
                pairs_by_operation[op] = []
            pairs_by_operation[op].append(pair)
        
        pairs_by_check_type = {}
        for pair in check_operation_pairs:
            check_type = pair['check_type']
            if check_type not in pairs_by_check_type:
                pairs_by_check_type[check_type] = []
            pairs_by_check_type[check_type].append(pair)
        
        return {
            'summary': {
                'total_methods_analyzed': total_methods,
                'total_checks_analyzed': total_checks_analyzed,
                'genuine_security_checks': genuine_security_checks,
                'false_positives': false_positives,
                'check_operation_pairs_found': len(check_operation_pairs),
                'unique_privileged_operations': len(set(all_privileged_operations)),
                'source_metadata': metadata,
                'llm_model': self.llm.get_model_name()
            },
            'check_operation_analysis': {
                'total_pairs': len(check_operation_pairs),
                'accuracy_rate': round((genuine_security_checks / max(total_checks_analyzed, 1)) * 100, 1),
                'false_positive_rate': round((false_positives / max(total_checks_analyzed, 1)) * 100, 1),
                'pairs_by_operation': {op: len(pairs) for op, pairs in pairs_by_operation.items()},
                'pairs_by_check_type': {ct: len(pairs) for ct, pairs in pairs_by_check_type.items()}
            },
            'privileged_operations': {
                'operation_frequency': dict(sorted(operation_counts.items(), key=lambda x: x[1], reverse=True)),
                'most_protected_operations': dict(sorted(operation_counts.items(), key=lambda x: x[1], reverse=True)[:10])
            },
            'check_operation_pairs': check_operation_pairs,
            'detailed_validations': validations
        }


    def validate_auth_checks(self, check_file: str, max_methods: Optional[int] = None) -> None:
        """Main validation pipeline focused on check-operation pairs"""
        print(f"Loading authentication data from: {check_file}")
        
        auth_data = self.load_auth_data(check_file)
        methods = auth_data.get('methods_with_auth', [])
        metadata = auth_data.get('metadata', {})
        
        if max_methods:
            methods = methods[:max_methods]
            print(f"Limiting analysis to first {max_methods} methods")
        
        # print(f"Analyzing {len(methods)} methods for check-operation pairs...")
        
        validations = []
        for i, method_data in enumerate(methods, 1):
            print(f"Validating method {i}/{len(methods)}: {method_data.get('id', 'unknown')}")
            
            validation = self.validate_method(method_data, i)
            validations.append(validation)
            
            method_file = self.output_dir / f"method_{i:03d}_validation.json"
            with open(method_file, 'w', encoding='utf-8') as f:
                json.dump(validation, f, indent=2)
        
        # print("Generating check-operation pair analysis...")
        summary_report = self.create_summary_report(validations, metadata)
        
        summary_file = self.output_dir / "validation_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary_report, f, indent=2)
        
        # self.save_readable_report(summary_report)
        
        print(f"\nValidation complete!")
        print(f"Results saved to: {self.output_dir}")
        print(f"Check-operation pairs found: {summary_report['summary']['check_operation_pairs_found']}")
        print(f"Unique privileged operations: {summary_report['summary']['unique_privileged_operations']}")
        print(f"Accuracy rate: {summary_report['check_operation_analysis']['accuracy_rate']}%")


def execute_base_check_query(appname: str, database: Path, language: str) -> Path:
    query = get_base_check_query(language)
    output_file = get_app_base_check_sarif_file(appname)

    try:
        execute_query(
            query_path = query, 
            database_path = database, 
            output_file = output_file,
            query_wd = query.parent
        )
        return output_file
    except Exception as e:
        print(f"    execute_base_check_query failed: {e}")
        return False


def extract_guarded_operations(input_path: Path) -> List[Tuple[str, Optional[str], Optional[int]]]:
    """Extract all guarded operations from JSON files."""
    
    all_operations = []
    
    if input_path.is_file():
        # Single file
        json_files = [input_path]
    else:
        # Directory
        json_files = [f for f in input_path.iterdir() if f.suffix == '.json']
    
    for json_file in json_files:
        try:
            with json_file.open('r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Extract file path
            file_path = data.get('file_path', "unknown_file")
            
            # Process check_results
            check_results = data.get('check_results', [])
            
            for check_result in check_results:
                guarded_ops = check_result.get('guarded_operations', '')
                
                if guarded_ops and guarded_ops.strip():
                    # Parse guarded operations (format: "operation1@line1 | operation2@line2")
                    operations = [op.strip() for op in guarded_ops.split('|')]
                    
                    for operation in operations:
                        if '@' in operation:
                            func_name, line_str = operation.rsplit('@', 1)
                            func_name = func_name.strip()
                            try:
                                line_num = int(line_str.strip())
                            except ValueError:
                                line_num = None
                        else:
                            func_name = operation.strip()
                            line_num = None
                        
                        if func_name:  # Only add if we have a function name
                            func_name = extract_function_name(func_name) # in case the class/object is kept so remove
                            all_operations.append((func_name, file_path, line_num, None)) # we don't know the class name here so set it empty

        except Exception as e:
            print(f"Warning: Failed to process {json_file}: {e}")
            continue
    
    return all_operations


def find_checked_op_main(llm_client: LLMClient, appname: str):

    if check_status(appname, AnalysisStatus.SINKS_CHECKEDOP):
        print(f"{AnalysisStatus.SINKS_CHECKEDOP} is already done")
        return

    database = get_app_database_dir(appname)
    language = get_database_language(database)

    print("Sinks: generate checked op....")
    sarif_file = execute_base_check_query(appname, database, language)

    parsed_file = parse_check(sarif_file, appname)

    if not parsed_file:
        return 
    
    output_dir = get_app_tmp_dir(appname)
    validator = AuthCheckValidator(llm_client, output_dir)
    validator.validate_auth_checks(parsed_file, 10)

    guarded_operations = extract_guarded_operations(output_dir)
    
    # Simple deduplication
    unique_operations = list(set(guarded_operations))

    # Generate the CodeQL query
    print(f"Sinks: generated {len(unique_operations)} checked op query")
    clean_status(appname, AnalysisStatus.WRITE_CHECKEDOP)
    if unique_operations:
        gen_checked_op_query(language, unique_operations, appname)
        update_status(appname, AnalysisStatus.WRITE_CHECKEDOP)

    update_status(appname, AnalysisStatus.SINKS_CHECKEDOP)