#!/usr/bin/env python3
"""
Simple Python script to fill the CodeQL template with callsite locations
Supports flexible matching: method_name only, method_name + file, or full specification
"""

from pathlib import Path
from typing import List, Tuple, Optional
from common.helper import get_customize_checked_op_query, get_template_checked_op_query

def gen_checked_op_query(language: str, callsites: List[Tuple[Optional[str], Optional[str], Optional[int], Optional[str]]], appname: str) -> Path:
    """Generate a customized CodeQL query for checked operations."""
    
    query_template = get_template_checked_op_query(language)
    
    if language == "python":
        query = _gen_checked_op_query_python(query_template, callsites)
    
    elif language == "java":
        query = _gen_checked_op_query_java(query_template, callsites)
    
    elif language == "go":
        query = _gen_checked_op_query_go(query_template, callsites)
    
    elif language in ["javascript", "js"]:
        query = _gen_checked_op_query_javascript(query_template, callsites)
    
    elif language in ["typescript", "ts"]:
        query = _gen_checked_op_query_typescript(query_template, callsites)

    elif language in ["csharp", "c#", "cs"]:
        query = _gen_checked_op_query_csharp(query_template, callsites)

    elif language.lower() in ["cpp", "c++"]:
        query = _gen_checked_op_query_cpp(query_template, callsites)

    else:
        raise ValueError(f"Unsupported language: {language}")
    
    query_file = get_customize_checked_op_query(language, appname)
    query_file.write_text(query, encoding="utf-8")
    return query_file



def _gen_checked_op_query_java(query_template: Path, callsites: List[Tuple[Optional[str], Optional[str], Optional[int], Optional[str]]]) -> str:
    """Generate CodeQL query for Java with callsite conditions."""
    
    result: List[str] = []
    
    for method_name, file_path, start_line, class_name in callsites:
        pr: List[str] = []
        
        # Ensure that callsite has four items
        if method_name is not None:
            condition_parts = f'call.getMethod().getName() = "{method_name}"'
            pr.append(condition_parts)

        if file_path is not None:
            if "/" in file_path:
                # full or partial path
                condition_parts = f'call.getFile().getRelativePath() = "{file_path}"'
            else:
                # just filename
                condition_parts = f'call.getFile().getBaseName() = "{file_path}"'
            pr.append(condition_parts)
        
        if start_line is not None:
            condition_parts = f'call.getLocation().getStartLine() = {start_line}'
            pr.append(condition_parts)
        
        if class_name is not None:
            condition_parts = f'call.getMethod().getDeclaringType().getQualifiedName() = "{class_name}"'
            pr.append(condition_parts)
            
        if pr:
            result.append("(\n        " + " and\n        ".join(pr) + "\n    )")

    all_conditions = "(\n        " + " or\n    ".join(result) + "\n    )"

    return query_template.read_text().replace("{{CALLSITE_CONDITIONS}}", all_conditions)




def _gen_checked_op_query_python(query_template: Path, callsites: List[Tuple[Optional[str], Optional[str], Optional[int], Optional[str]]]) -> str:
    """Generate CodeQL query for Python with callsite conditions."""
    
    result: List[str] = []
    
    for method_name, file_path, start_line, class_name in callsites:
        pr: List[str] = []
        
        # Method name condition
        if method_name is not None:
            condition_parts = f'call.getFunc().(Name).getId() = "{method_name}"'
            pr.append(condition_parts)

        # File path condition
        if file_path is not None:
            if "/" in file_path:
                # full or partial path
                condition_parts = f'call.getLocation().getFile().getRelativePath() = "{file_path}"'
            else:
                # just filename
                condition_parts = f'call.getLocation().getFile().getBaseName() = "{file_path}"'
            pr.append(condition_parts)
        
        # Line number condition
        if start_line is not None:
            condition_parts = f'call.getLocation().getStartLine() = {start_line}'
            pr.append(condition_parts)
        
        # Class name condition (for method calls on specific classes)
        if class_name is not None:
            # For attribute access like obj.method() where obj is of type class_name
            condition_parts = f'call.getFunc().(Attribute).getObject().pointsTo().getClass().getName() = "{class_name}"'
            pr.append(condition_parts)
            
        if pr:
            result.append("(\n        " + " and\n        ".join(pr) + "\n    )")
    
    if result:
        all_conditions = "and\n (\n        " + " or\n    ".join(result) + "\n    )"

    return query_template.read_text().replace("{{CALLSITE_CONDITIONS}}", all_conditions)

def _gen_checked_op_query_go(query_template: Path, callsites: List[Tuple[Optional[str], Optional[str], Optional[int], Optional[str]]]) -> str:
    """Generate CodeQL query for Go with callsite conditions."""
    
    result: List[str] = []
    
    for method_name, file_path, start_line, class_name in callsites:
        pr: List[str] = []
        
        # Method/function name condition
        if method_name is not None:
            condition_parts = f'call.getTarget().getName() = "{method_name}"'
            pr.append(condition_parts)

        # File path condition
        if file_path is not None:
            if "/" in file_path:
                # full or partial path
                condition_parts = f'call.getFile().getRelativePath() = "{file_path}"'
            else:
                # just filename
                condition_parts = f'call.getFile().getBaseName() = "{file_path}"'
            pr.append(condition_parts)
        
        # Line number condition
        if start_line is not None:
            condition_parts = f'call.getLocation().getStartLine() = {start_line}'
            pr.append(condition_parts)
        
        # Type/receiver name condition (for method calls on specific types)
        if class_name is not None:
            # For Go, check the receiver type name for methods
            condition_parts = f'call.getTarget().(Method).getReceiverType().getName() = "{class_name}"'
            pr.append(condition_parts)
            
        if pr:
            result.append("(\n        " + " and\n        ".join(pr) + "\n    )")
    
    if result:
        all_conditions = "and\n (\n        " + " or\n    ".join(result) + "\n    )"
    else:
        all_conditions = ""

    return query_template.read_text().replace("{{CALLSITE_CONDITIONS}}", all_conditions)

def _gen_checked_op_query_javascript(query_template: Path, callsites: List[Tuple[Optional[str], Optional[str], Optional[int], Optional[str]]]) -> str:
    """Generate CodeQL query for JavaScript with callsite conditions."""
    
    result: List[str] = []
    
    for method_name, file_path, start_line, class_name in callsites:
        pr: List[str] = []
        
        # Method/function name condition
        if method_name is not None:
            condition_parts = f'call.getCalleeName() = "{method_name}"'
            pr.append(condition_parts)

        # File path condition
        if file_path is not None:
            if "/" in file_path:
                # full or partial path
                condition_parts = f'call.getFile().getRelativePath() = "{file_path}"'
            else:
                # just filename
                condition_parts = f'call.getFile().getBaseName() = "{file_path}"'
            pr.append(condition_parts)
        
        # Line number condition
        if start_line is not None:
            condition_parts = f'call.getLocation().getStartLine() = {start_line}'
            pr.append(condition_parts)
        
        # Class name condition (for method calls on specific receiver types)
        if class_name is not None:
            # For JavaScript, check if it's a method call and the receiver has a specific type/class name
            # This checks for method calls like obj.method() where obj is of a certain class
            condition_parts = f'call.(MethodCallExpr).getReceiver().analyze().getAType().hasUnderlyingType("{class_name}")'
            pr.append(condition_parts)
            
        if pr:
            result.append("(\n        " + " and\n        ".join(pr) + "\n    )")
    
    if result:
        all_conditions = "and\n (\n        " + " or\n    ".join(result) + "\n    )"
    else:
        all_conditions = ""

    return query_template.read_text().replace("{{CALLSITE_CONDITIONS}}", all_conditions)

def _gen_checked_op_query_csharp(query_template: Path, callsites: List[Tuple[Optional[str], Optional[str], Optional[int], Optional[str]]]) -> str:
    """Generate CodeQL query for C# with callsite conditions."""

    result: List[str] = []

    for method_name, file_path, start_line, class_name in callsites:
        pr: List[str] = []

        if method_name is not None:
            pr.append(f'call.getTarget().getName() = "{method_name}"')

        if file_path is not None:
            if "/" in file_path:
                pr.append(f'call.getLocation().getFile().getRelativePath() = "{file_path}"')
            else:
                pr.append(f'call.getLocation().getFile().getBaseName() = "{file_path}"')

        if start_line is not None:
            pr.append(f'call.getLocation().getStartLine() = {start_line}')

        if class_name is not None:
            pr.append(f'call.getTarget().getDeclaringType().getName() = "{class_name}"')

        if pr:
            result.append("(\n        " + " and\n        ".join(pr) + "\n    )")

    # C# template already has 'call and {{CALLSITE_CONDITIONS}}' — no 'and' prefix needed
    if result:
        all_conditions = "(\n        " + " or\n    ".join(result) + "\n    )"
    else:
        all_conditions = ""

    return query_template.read_text().replace("{{CALLSITE_CONDITIONS}}", all_conditions)


def _gen_checked_op_query_typescript(query_template: Path, callsites: List[Tuple[Optional[str], Optional[str], Optional[int], Optional[str]]]) -> str:
    """Generate CodeQL query for TypeScript with callsite conditions."""
    
    result: List[str] = []
    
    for method_name, file_path, start_line, class_name in callsites:
        pr: List[str] = []
        
        # Method/function name condition
        if method_name is not None:
            condition_parts = f'call.getCalleeName() = "{method_name}"'
            pr.append(condition_parts)

        # File path condition
        if file_path is not None:
            if "/" in file_path:
                # full or partial path
                condition_parts = f'call.getFile().getRelativePath() = "{file_path}"'
            else:
                # just filename
                condition_parts = f'call.getFile().getBaseName() = "{file_path}"'
            pr.append(condition_parts)
        
        # Line number condition
        if start_line is not None:
            condition_parts = f'call.getLocation().getStartLine() = {start_line}'
            pr.append(condition_parts)
        
        # Class name condition (for method calls on specific types)
        if class_name is not None:
            # For TypeScript, we can use type information more reliably
            # Check if the receiver has a specific class/interface type
            condition_parts = f'call.(MethodCallExpr).getReceiver().getType().hasUnderlyingType("{class_name}")'
            pr.append(condition_parts)
            
        if pr:
            result.append("(\n        " + " and\n        ".join(pr) + "\n    )")
    
    if result:
        all_conditions = "and\n (\n        " + " or\n    ".join(result) + "\n    )"
    else:
        all_conditions = ""

    return query_template.read_text().replace("{{CALLSITE_CONDITIONS}}", all_conditions)

def _gen_checked_op_query_cpp(
    query_template: Path,
    callsites: List[Tuple[Optional[str], Optional[str], Optional[int], Optional[str]]]
) -> str:
    """Generate CodeQL query for C++ with callsite conditions."""
    result: List[str] = []
    for method_name, file_path, start_line, class_name in callsites:
        pr: List[str] = []
        if method_name is not None:
            pr.append(f'call.getTarget().getName() = "{method_name}"')
        if file_path is not None:
            if "/" in file_path:
                pr.append(f'call.getFile().getRelativePath() = "{file_path}"')
            else:
                pr.append(f'call.getFile().getBaseName() = "{file_path}"')
        if start_line is not None:
            pr.append(f'call.getLocation().getStartLine() = {start_line}')
        if class_name is not None:
            pr.append(f'call.getTarget().getDeclaringType().getName() = "{class_name}"')
        if pr:
            result.append("(\n        " + " and\n        ".join(pr) + "\n    )")
    if result:
        all_conditions = "and\n (\n        " + " or\n    ".join(result) + "\n    )"
    else:
        all_conditions = ""
    return query_template.read_text().replace("{{CALLSITE_CONDITIONS}}", all_conditions)
