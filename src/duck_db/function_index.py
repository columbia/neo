"""
``function_id -> function_info`` index with a line -> function reverse map.

Split out of the (removed) tree-sitter ``function_mapper.py`` so the flow
extractor can consume a prebuilt ``function_mapping.json`` without pulling in a
parser dependency.  Nothing here builds the mapping — that is done by CodeQL
(:mod:`duck_db.codeql_function_mapper`); this only loads and queries it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional


class OptimizedFunctionIndex:
    """Clean key-value mapping: function_id -> function_info."""

    def __init__(self):
        self.functions: Dict[str, dict] = {}                    # function_id -> info
        self.line_to_function: Dict[tuple, str] = {}            # (file_path, line) -> function_id

    def add_functions(self, functions) -> None:
        """
        Register functions in the index.  Accepts objects with ``.function_id``
        / ``.to_dict()`` / ``.start_line`` / ``.end_line`` / ``.file_path``
        (``codeql_function_mapper.EnhancedFunction``) or plain dicts with those
        keys.
        """
        for func in functions:
            if hasattr(func, "to_dict"):
                fid = func.function_id
                info = func.to_dict()
                start, end = func.start_line, func.end_line
                fpath = str(func.file_path)
            else:
                fid = func["function_id"]
                info = dict(func)
                start, end = func["start_line"], func["end_line"]
                fpath = str(func["file_path"])
            self.functions[fid] = info
            for line in range(start, end + 1):
                self.line_to_function[(fpath, line)] = fid

    def get_function_by_id(self, function_id: str) -> Optional[dict]:
        return self.functions.get(function_id)

    def get_function_containing_line(self, file_path, line: int) -> Optional[str]:
        return self.line_to_function.get((str(file_path), line))

    def get_stats(self) -> dict:
        files = {info["file_path"] for info in self.functions.values()}
        return {
            "total_functions": len(self.functions),
            "total_files": len(files),
            "total_line_mappings": len(self.line_to_function),
            "files": sorted(files),
        }

    def save_optimized_mapping(self, output_file: Path) -> dict:
        data = {
            "function_definitions": self.functions,
            "metadata": {
                "total_functions": len(self.functions),
                "total_files": len({i["file_path"] for i in self.functions.values()}),
                "mapping_type": "function_id_to_info",
            },
        }
        Path(output_file).write_text(json.dumps(data, indent=2))
        return data

    @classmethod
    def load_from_file(cls, input_file: Path) -> "OptimizedFunctionIndex":
        input_file = Path(input_file)
        if not input_file.exists():
            raise FileNotFoundError(f"Index file not found: {input_file}")

        data = json.loads(input_file.read_text())
        if "function_definitions" not in data:
            raise ValueError("Invalid index file format: missing 'function_definitions'")

        index = cls()
        index.functions = data["function_definitions"]
        for function_id, info in index.functions.items():
            for line in range(info["start_line"], info["end_line"] + 1):
                index.line_to_function[(info["file_path"], line)] = function_id
        return index


def load_function_index(input_file: Path) -> OptimizedFunctionIndex:
    return OptimizedFunctionIndex.load_from_file(input_file)
