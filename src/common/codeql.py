import subprocess
import os
from pathlib import Path
from typing import Optional


def _get_codeql_env():
    """Load CodeQL configuration from .env file"""
    codeql_bin = os.getenv('CODEQL_BIN')
    from .helper import get_codeql_lib_dir
    codeql_lib = get_codeql_lib_dir()
    timeout = int(os.getenv('CODEQL_TIMEOUT', '300'))  # Default 5 minutes
    
    assert codeql_bin, "CODEQL_BIN must be set in .env file"
    
    return Path(codeql_bin), Path(codeql_lib), timeout


def check_query_syntax(query_path: Path, query_wd: Optional[Path] = None) -> bool:
    """Check syntax of a CodeQL query without executing it
    
    Args:
        query_path: Path to the CodeQL query file
        query_wd: Optional working directory for the query execution
    
    Returns:
        bool: True if syntax is valid, False otherwise
    """
    print(f"🔍 Checking syntax: {query_path}")
    
    # Ensure we have Path objects

    if query_wd is not None:
        query_wd = Path(query_wd)
    
    # Check if paths exist
    if not query_path.exists():
        print(f"Query file does not exist: {query_path}")
        return False
        
    if query_wd and not query_wd.exists():
        print(f"Working directory does not exist: {query_wd}")
        return False

    # Get CodeQL configuration
    command, search_path, timeout = _get_codeql_env()

    try:
        cmd = [str(command), "query", "compile",
               "--search-path", str(search_path),
               "--check-only", str(query_path)]
        
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=timeout, 
            cwd=str(query_wd) if query_wd else None
        )
        
        if result.returncode != 0:
            print(f"Syntax error in {query_path}:")
            print(result.stderr)
            return False
        
        print(f"\tSyntax check passed for {query_path}")
        return True
        
    except subprocess.TimeoutExpired:
        print(f"Syntax check timed out for {query_path}")
        return False
    except Exception as e:
        print(f"Error checking syntax: {e}")
        return False


def execute_query(query_path: Path, database_path: Path, query_wd: Optional[Path], output_file: Path,
                  rerun: bool = True) -> bool:
    """Execute a CodeQL query against a database and save results to file

    Args:
        query_path: Path to the CodeQL query file
        database_path: Path to the CodeQL database
        query_wd: Optional working directory for the query execution
        output_file: Path where to save the query results
        rerun: pass ``--rerun`` (force re-evaluation, ignore the result cache).
               Set False for read-only / repeatedly-issued queries (e.g. the
               agent's code-search primitives) so CodeQL can reuse cached
               results — a large speedup for iterative analysis.

    Returns:
        bool: True if execution succeeded, False otherwise
    """
    # print(f"\tExecuting query: {query_path}")
    
    # Check if paths exist
    if not query_path.exists():
        print(f"Query file does not exist: {query_path}")
        return False
    
    if not database_path.exists():
        print(f"Database path does not exist: {database_path}")
        return False
        
    if query_wd and not query_wd.exists():
        print(f"Working directory does not exist: {query_wd}")
        return False

    # Create output directory if it doesn't exist
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Get CodeQL configuration
    command, search_path, timeout = _get_codeql_env()

    try:
        cmd = [str(command), "database", "analyze", str(database_path),
               "--search-path", str(search_path),
               "--threat-model", "remote",
               "--format", "sarif-latest",
               "--output", str(output_file),
               str(query_path)]
        if rerun:
            cmd.insert(-1, "--rerun")  # ignore the result cache

        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=timeout, 
            cwd=str(query_wd) if query_wd else None
        )

        if result.returncode != 0:
            print(f"Query execution failed:")
            print(result.stderr)
            return False
        
        # print(f"\tQuery executed successfully, results saved to: {output_file}")
        return True
        
    except subprocess.TimeoutExpired:
        print(f"Query execution timed out")
        return False
    except Exception as e:
        print(f"Error executing query: {e}")
        return False