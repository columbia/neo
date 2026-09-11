"""
To find sinks, there are three strategies
1) a base sink query that identifies operations
2) a check based query that identifies checks
3) an optional LLM-generated query: LLM analyzes the documentation of the app to derive customized operations
"""

import re
from pathlib import Path
from typing import List

# Import your existing modules
from common.llms import LLMClient
from common.helper import *
from common.codeql import execute_query
from genquery.gen_callsite import gen_callsite_query
from .find_checked_op import find_checked_op_main


def parse_llm_function_names(llm_response: str) -> List[str]:
    function_patterns = []
    
    # Extract content between <function-name> and </function-name> tags
    pattern = r'<function-name>(.*?)</function-name>'
    matches = re.findall(pattern, llm_response, re.DOTALL | re.IGNORECASE)
    
    for match in matches:
        # Clean up the extracted pattern
        cleaned_pattern = match.strip()
        if cleaned_pattern:  # Only add non-empty patterns
            function_patterns.append(cleaned_pattern)
    
    print(f"Extracted {len(function_patterns)} function patterns from LLM response:")
    
    return function_patterns


def get_customize_op(llm_client: LLMClient, language: str, appname: str, description: str):
    """
    Send the query to LLM and ask if there are others to add, particularly for privilege escalation, 
    and focus on function name in call sites. It may output regular expressions to match these function names.
    In the prompt, we should ask the model to separate output each regex within <function-name> and </function-name> tags using codeql acceptable regex
    """
    
    base_query = get_base_sink_query(language)

    prompt_template = load_customize_sink_prompt()
    prompt = prompt_template.format(language=language, base_query=base_query, description=description)

    history = []
    message = [{"role": "user", "content": prompt}]
    
    response = llm_client.messages_create(history=history, message=message, max_tokens=10000, temperature=0.1)
    return parse_llm_function_names(response.content[0].text)




def find_sinks_main(llm_client: LLMClient, appname: str, skip_customize_op: bool = False):

    if check_status(appname, AnalysisStatus.FIND_SINKS):
        print(f"{AnalysisStatus.FIND_SINKS} is already done")
        return

    database = get_app_database_dir(appname)
    language = get_database_language(database)

    # the agent (src/agent/run.py) may have already produced + merged a
    # customized-sink query; don't clobber it, even across separate invocations.
    if not skip_customize_op and (get_app_workdir(appname) / "agent_privileged_ops.json").exists():
        skip_customize_op = True

    if skip_customize_op:
        # the agent (src/agent/run.py) already produced + merged the customized
        # sink query; don't run the one-shot LLM step or clobber it.
        print("Skipping one-shot customize-op step (agent-provided sinks in use)")
    else:
        print("Generate customize sinks....")
        description = get_app_description(appname)
        additional_calls = get_customize_op(llm_client, language, appname, description)

        clean_status(appname, AnalysisStatus.WRITE_CUSTOMEOP) # assume we haven't write the query
        if additional_calls:
            gen_callsite_query(additional_calls, language, appname)
            update_status(appname, AnalysisStatus.WRITE_CUSTOMEOP)

    find_checked_op_main(llm_client, appname)

    # mark done with sinks
    update_status(appname, AnalysisStatus.FIND_SINKS)