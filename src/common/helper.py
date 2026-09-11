"""
Helper functions for path manipulation and app name extraction
"""

from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from enum import StrEnum
import yaml
import re

def load_env_file():
    """Load .env file into environment variables from src directory or its parent"""
    src_path = Path(__file__).parent.parent  # src directory
    
    # Try src directory first
    src_env = src_path / '.env'
    if src_env.exists():
        load_dotenv(src_env)
        return
    
    # Try src's parent directory
    parent_env = src_path.parent / '.env'
    if parent_env.exists():
        load_dotenv(parent_env)
        return
    
    print("Warning: No .env file found in src or its parent directory")
    exit(1)


def get_appname_from_database(database_path: Path) -> str:
    """
    Extract app name from database path
    Example: databases/myapp -> myapp
             /path/to/databases/myapp -> myapp
    """
    path = Path(database_path)
    return path.name


def get_appname_from_codebase(codebase_path: Path) -> str:
    """
    Extract app name from codebase path
    Example: codebases/myapp -> myapp
             /path/to/codebases/myapp -> myapp
    """
    path = Path(codebase_path)
    return path.name


def get_codebase_from_database(database_path: Path) -> Path:
    """
    Convert database path to corresponding codebase path
    Example: databases/myapp -> codebases/myapp
    """
    database_path = Path(database_path)
    
    # Navigate up to parent and switch to codebases
    parent_dir = database_path.parent.parent
    codebase_path = parent_dir / "codebases" / database_path.name
    
    return codebase_path


def get_database_from_codebase(codebase_path: Path) -> Path:
    """
    Convert codebase path to corresponding database path
    Example: codebases/myapp -> databases/myapp
    """
    codebase_path = Path(codebase_path)
    
    # Navigate up to parent and switch to databases
    parent_dir = codebase_path.parent.parent
    database_path = parent_dir / "databases" / codebase_path.name
    
    return database_path


def validate_path_structure(path: Path, expected_type: str) -> bool:
    """
    Validate if path follows expected structure
    
    Args:
        path: Path to validate
        expected_type: Either 'database' or 'codebase'
    
    Returns:
        True if path structure is valid, False otherwise
    """
    path = Path(path)
    path_parts = path.parts
    
    if len(path_parts) < 2:
        return False
    
    if expected_type == "database":
        return "databases" in path_parts
    elif expected_type == "codebase":
        return "codebases" in path_parts
    else:
        return False


def ensure_directory_exists(path: Path) -> None:
    """Create directory if it doesn't exist"""
    path.mkdir(parents=True, exist_ok=True)

def get_query_dir() -> Path:
    return Path(__file__).parent.parent.parent / "queries"

def get_datasets_dir() -> Path:
    return Path(__file__).parent.parent.parent / "databases"

def get_prompt_dir() -> Path:
    return Path(__file__).parent.parent / "prompts"

def get_codebases_dir() -> Path:
     return Path(__file__).parent.parent.parent / "codebases"

def get_models() -> dict:
    models_path = Path(__file__).parent.parent / "models.json"
    import json
    with open(models_path, 'r') as f:
        return json.load(f)
    return None

def get_codeql_lib_dir() -> Path:
     # the CodeQL standard library lives in ./codeql-lib (scripts/install_codeql_lib.sh)
     return Path(__file__).parent.parent.parent / "codeql-lib"

# Services declared in a manifest by explicit ``source:``/``database:`` paths do
# not have a ``codebases/<name>`` entry.  ``register_app_dirs`` lets the
# multi-service driver map such a key to its real source/database dirs so the
# ``get_app_*`` family (workdir, function map, sarif, duckdb, …) keeps working.
_APP_DIR_OVERRIDES: dict = {}


def register_app_dirs(appname: str, source_dir=None, database_dir=None) -> None:
    entry = _APP_DIR_OVERRIDES.setdefault(appname, {})
    if source_dir is not None:
        entry["source"] = Path(source_dir)
    if database_dir is not None:
        entry["database"] = Path(database_dir)


def get_app_source_dir(appname: str) -> Path:
    if appname in _APP_DIR_OVERRIDES and "source" in _APP_DIR_OVERRIDES[appname]:
        return _APP_DIR_OVERRIDES[appname]["source"]
    dir = get_codebases_dir() / appname
    assert dir.exists(), f"App source directory does not exist: {dir}"
    return dir

def get_app_database_dir(appname: str) -> Path:
    if appname in _APP_DIR_OVERRIDES and "database" in _APP_DIR_OVERRIDES[appname]:
        return _APP_DIR_OVERRIDES[appname]["database"]
    dir = get_datasets_dir() / appname
    assert dir.exists(), f"App database directory does not exist: {dir}"
    return dir


def get_app_function_map_file(appname: str) -> Path:
    f = get_app_workdir(appname) / "function_mapping.json"
    # assert f.exists(), f"Function map does not exist: {f}"
    return f


def get_app_classes_json_file(appname: str) -> Path:
    f = get_app_workdir(appname) / "classes.json"
    return f


def get_app_duckdb_file(appname: str) -> Path:
    f =get_app_workdir(appname) / "callgraph.duckdb"
    # assert f.exists(), f"Callsite file does not exist: {f}"
    return f

def create_app_workdir(appname: str):
    dir = get_app_source_dir(appname) / "neo-workdir"
    ensure_directory_exists(dir)

def get_app_workdir(appname: str):
    return get_app_source_dir(appname) / "neo-workdir"

def get_app_tmp_dir(appname: str) -> Path:
    dir = get_app_workdir(appname) / "tmp"
    ensure_directory_exists(dir)
    return dir

def get_sarif_path_from_database(database_path: Path, query_name: str) -> Path:
    """Generate output file path: databases/app -> codebases/app/queryname.sarif"""
    database_path = Path(database_path)
    
    # Navigate up to parent and switch to codebases
    parent_dir = database_path.parent.parent
    codebase_dir = parent_dir / "codebases" / database_path.name
    sarif_path = codebase_dir / f"{query_name}.sarif"
    
    return sarif_path

def get_query_tmp_dir(language: str) -> Path:
    dir = get_query_dir() / language / "tmp"
    ensure_directory_exists(dir)
    return dir


### query templates
def get_template_op_query(language: str) -> Path:
    return get_query_dir() / language / "templateSinkOp.qll"

def get_template_checked_op_query(language: str) -> Path:
    return get_query_dir() / language / "templateSinkCheckedOp.qll"

def get_template_flow2sink_query(language: str) -> Path:
    return get_query_dir() / language / "templateFlowSource2Sink.ql" # it is .ql not .qll

## get queries
def get_base_sink_query(language: str) -> Path:
    return get_query_dir() / language / "libSink.qll"

def get_callsite_query(language: str) -> Path:
    return get_query_dir() / language / "callsites.ql"

def get_base_check_query(language: str) -> Path:
    return get_query_dir() / language / "sinkBaseCheck.ql"

def get_flow2out_query(language: str) -> Path:
    return get_query_dir() / language / "flowSource2OutBound.ql"

# sanitize the app's name so that they can be imported in codeql
def san_appname(appname: str) -> str:
    return appname.replace("-", "").replace("_", "").replace(".", "")

def get_customize_op_query(language: str, appname: str) -> Path:
    appname = san_appname(appname)
    return get_query_tmp_dir(language) / f"{appname}SinkOp.qll"

def get_customize_checked_op_query(language: str, appname: str) -> Path:
    appname = san_appname(appname)
    return get_query_tmp_dir(language) / f"{appname}SinkCheckedOp.qll"

def get_flow2sink_query(language: str, appname: str) -> Path:
    appname = san_appname(appname)
    return get_query_tmp_dir(language) / f"{appname}FlowSource2Sink.ql"


### get per app sarif and json, if needed
def get_app_base_check_json_file(appname: str) -> Path:
    f = get_app_workdir(appname) / "sinkBaseCheck.json"
    return f

def get_app_base_check_sarif_file(appname: str) -> Path:
    f = get_app_workdir(appname) / "sinkBaseCheck.sarif"
    return f

def get_app_callsites_sarif_file(appname: str) -> Path:
    f = get_app_workdir(appname)/ "callsites.sarif"
    return f 

def get_app_callsite_json_file(appname: str) -> Path:
    f = get_app_workdir(appname) / "callsites.json"
    # assert f.exists(), f"Callsite file does not exist: {f}"
    return f

def get_app_decorators_sarif_file(appname: str) -> Path:
    """Get decorator SARIF file path for app"""
    return get_app_workdir(appname) / "decorator.sarif"

def get_app_decorator_json_file(appname: str) -> Path:
    f = get_app_workdir(appname) / "decorator.json"
    # assert f.exists(), f"Callsite file does not exist: {f}"
    return f

def get_app_customize_op_sarif_file(appname: str) -> Path:
    f = get_app_workdir(appname) / "SinkOp.sarif"
    return f

def get_flow2sink_sarif_file(appname: str) -> Path:
    f =get_app_workdir(appname) / "FlowSourceSink.sarif"
    return f

def get_flow2sink_json_file(appname: str) -> Path:
    f =get_app_workdir(appname) / "FlowSourceSink.json"
    return f

def get_flow2out_sarif_file(appname: str) -> Path:
    f = get_app_workdir(appname) / "Flow2Out.sarif"
    return f

def get_flow2out_json_file(appname: str) -> Path:
    f = get_app_workdir(appname) / "Flow2Out.json"
    return f


def get_flow2sink_validation_dir(appname: str) -> Path:
    dir = get_app_workdir(appname) / "validation"
    ensure_directory_exists(dir)
    return dir


### cross-service / cross-language (Qinter + Qglobalflow)

def get_interservice_query(language: str) -> Path:
    """CodeQL query that lists outbound inter-service calls + their channel identifiers."""
    return get_query_dir() / language / "interservice.ql"

def get_endpoints_query(language: str) -> Path:
    """CodeQL query that lists inbound endpoints (routes / consumers) + their handlers."""
    return get_query_dir() / language / "endpoints.ql"

def get_app_interservice_sarif_file(appname: str) -> Path:
    return get_app_workdir(appname) / "interservice.sarif"

def get_app_interservice_json_file(appname: str) -> Path:
    return get_app_workdir(appname) / "interservice.json"

def get_app_endpoints_sarif_file(appname: str) -> Path:
    return get_app_workdir(appname) / "endpoints.sarif"

def get_app_endpoints_json_file(appname: str) -> Path:
    return get_app_workdir(appname) / "endpoints.json"

def get_global_workdir(manifest_name: str) -> Path:
    """Shared work directory for a multi-service application, keyed by manifest name.

    Kept outside ``codebases/`` (a git submodule) so cross-service artifacts do
    not dirty the submodule working tree.
    """
    dir = Path(__file__).parent.parent.parent / "global_work" / manifest_name
    ensure_directory_exists(dir)
    return dir

def get_global_flow_json_file(manifest_name: str) -> Path:
    return get_global_workdir(manifest_name) / "GlobalFlowSourceSink.json"

def get_global_graph_json_file(manifest_name: str) -> Path:
    return get_global_workdir(manifest_name) / "global_reachability_graph.json"

def get_global_validation_dir(manifest_name: str) -> Path:
    dir = get_global_workdir(manifest_name) / "validation"
    ensure_directory_exists(dir)
    return dir

def get_app_description(appname: str) -> str:
    base_path = get_codebases_dir() / appname
    
    # Try common readme formats
    for name in ["README.md", "README.rst", "README.txt", "README",
                 "readme.md", "readme.rst", "readme.txt", "readme",
                 "Readme.md", "Readme.rst", "Readme.txt", "Readme"]:
        f = base_path / name
        if f.exists():
            content = f.read_text(encoding='utf-8', errors='ignore')
            # Return first 400 chars, break at word boundary
            if len(content) <= 400:
                return content
            return content[:400].rsplit(' ', 1)[0] + "..."
    
    return ""


class AnalysisStatus(StrEnum):
    FIND_SINKS = "FIND_SINKS"
    SINKS_CHECKEDOP = "SINKS_CHECKEDOP" # finishing this does not mean the query is generated because there may be no result
    FIND_FLOWS = "FIND_FLOWS"
    VALIDATE_FLOWS = "VALIDATE_FLOWS"

    DUCKDB = "DUCKDB"
    WRITE_CUSTOMEOP = "WRITE_CUSTOMEOP" # this query has been written
    WRITE_CHECKEDOP = "WRITE_CHECKEDOP" # this query has been written

    # cross-service / cross-language analysis (Qinter + Qglobalflow, Algorithm 1)
    INTERSERVICE = "INTERSERVICE"     # outbound call + channel-id extraction done for a service
    ENDPOINTS = "ENDPOINTS"           # inbound endpoint + route extraction done for a service
    GLOBAL_FLOWS = "GLOBAL_FLOWS"     # cross-service reachability graph + stitched flows built
    VALIDATE_GLOBAL_FLOWS = "VALIDATE_GLOBAL_FLOWS"



def get_status_dir() -> Path:
    return Path(__file__).parent.parent.parent / "status"

def check_status(appname: str, status: str) -> bool:
    f = get_status_dir() / f"{appname}.{status}"
    return f.exists()

def update_status(appname: str, status: str):
    f = get_status_dir() / f"{appname}.{status}"
    f.write_text("") 
    
def clean_status(appname: str, status: str):
    f = get_status_dir() / f"{appname}.{status}"
    f.unlink(missing_ok=True)

def clean_all_status(language: str, appname: str):
    for status in AnalysisStatus:
        f = get_status_dir() / f"{appname}.{status.value}"
        f.unlink(missing_ok=True)

    f = get_customize_checked_op_query(language, appname)
    f.unlink(missing_ok=True)

    f = get_flow2sink_query(language, appname)
    f.unlink(missing_ok=True)
    
    f = get_customize_op_query(language, appname)
    f.unlink(missing_ok=True)
    


###### prompts 

def load_customize_sink_prompt() -> Optional[str]:
    f = get_prompt_dir() / "customize_sink.md"
    return f.read_text()

def load_validate_flow_prompt() -> Optional[str]:
    f = get_prompt_dir() / "validate_flow.md"
    return f.read_text()

def load_validate_next_flow_prompt() -> Optional[str]:
    f = get_prompt_dir() / "validate_next_flow.md"
    return f.read_text()


def load_validate_global_flow_prompt() -> Optional[str]:
    f = get_prompt_dir() / "validate_global_flow.md"
    return f.read_text()


def load_validate_global_next_flow_prompt() -> Optional[str]:
    f = get_prompt_dir() / "validate_global_next_flow.md"
    return f.read_text()


def load_validate_check_prompt() -> Optional[str]:
    f = get_prompt_dir() / "validate_check.md"
    return f.read_text()

#### codeql


def get_database_language(database: Path) -> str:
    metadata_file = database / "codeql-database.yml"
    
    if not metadata_file.exists():
        raise FileNotFoundError(f"Database metadata file not found: {metadata_file}")
    
    try:
        with open(metadata_file, 'r') as f:
            metadata = yaml.safe_load(f)
        
        # Try to get primary language first
        primary_language = metadata.get('primaryLanguage')
        if primary_language:
            return primary_language.lower()
        
        # Fallback to first language in languages list
        languages = metadata.get('languages', [])
        if languages:
            return languages[0].lower()
        
        raise ValueError(f"No language information found in {metadata_file}")
        
    except yaml.YAMLError as e:
        raise ValueError(f"Failed to parse YAML file {metadata_file}: {e}")
    except Exception as e:
        raise RuntimeError(f"Error reading database metadata: {e}")



def extract_function_name(call_string):
    """Extract function name from various method call patterns"""

    # Pattern to match: object.method(), object->method(), Class::method()
    # Captures the function name (group 1)
    pattern = r'(?:[\w$]+(?:\.|\->|::)\s*)?(\w+)\s*\('

    match = re.search(pattern, call_string)
    if match:
        return match.group(1)
    return None


# def get_database_languages(database: Path) -> list[str]:
#     metadata_file = database / "codeql-database.yml"
    
#     if not metadata_file.exists():
#         raise FileNotFoundError(f"Database metadata file not found: {metadata_file}")
    
#     try:
#         with open(metadata_file, 'r') as f:
#             metadata = yaml.safe_load(f)
        
#         # Get languages list
#         languages = metadata.get('languages', [])
#         if languages:
#             return [i.lower() for i in languages]
        
#         # Fallback to primary language if languages key doesn't exist
#         primary_language = metadata.get('primaryLanguage')
#         if primary_language:
#             return [primary_language.lower()]
        
#         raise ValueError(f"No language information found in {metadata_file}")
        
#     except yaml.YAMLError as e:
#         raise ValueError(f"Failed to parse YAML file {metadata_file}: {e}")
#     except Exception as e:
#         raise RuntimeError(f"Error reading database metadata: {e}")

