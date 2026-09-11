"""
Library Semantics Index

Provides natural-language behavioral descriptions for well-known JAR methods
that cannot be resolved from the application's CodeQL database. Used as a
fallback in resolve_function_request() to prevent LLM hallucination of
library semantics during Z3 constraint generation.
"""

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def extract_fqn_from_request(func_request: str) -> Optional[str]:
    """
    Extract a fully-qualified method name from a func_request string.

    Handles four formats emitted by parse_function_requests():
      1. Dotted (no @):           "org.apache.commons.io.FilenameUtils.getBaseName"
                                   → returned as-is
      2. JAR @ path:              "getBaseName@/path/commons-io.jar!/org/.../FilenameUtils.class:0"
                                   → "org.apache.commons.io.FilenameUtils.getBaseName"
      3. Source @ path            "doFilter@src/main/java/Filter.java:10"
         (plain method name):      → None  (app code; handled by DuckDB, not this index)
      4. Source @ path            "FilenameUtils.getBaseName@src/main/java/FileUploadUtils.java:97"
         (ClassName.method):       → "FilenameUtils.getBaseName"
                                   (library ref via source call site; suffix-matched by index)

    Returns None for unrecognised or empty input.
    """
    if not func_request:
        return None

    if "@" not in func_request:
        # Dotted class-qualified format — use as-is
        return func_request

    method_name, path_part = func_request.split("@", 1)

    # Strip line number suffix if present
    if ":" in path_part:
        path_part = path_part.rsplit(":", 1)[0]

    if ".jar!" not in path_part:
        # Source file path. If method_name contains a dot it encodes
        # ClassName.method — return it so the index can do a suffix match.
        # Plain method names (no dot) are app-defined; skip them.
        if "." in method_name:
            return method_name
        return None

    # JAR path format: /path/to/lib.jar!/org/pkg/ClassName.class
    # Extract the class path from inside the JAR
    class_path = path_part.split(".jar!", 1)[1]
    class_path = class_path.lstrip("/")

    # Strip .class suffix
    if class_path.endswith(".class"):
        class_path = class_path[: -len(".class")]

    # Convert path separators to dots
    class_fqn = class_path.replace("/", ".")

    return f"{class_fqn}.{method_name}"


class LibrarySemanticsIndex:
    """
    In-memory index of library method FQN → natural language semantics.

    Loaded once from a JSON file at construction. Provides lookup() which
    accepts the same func_request strings as resolve_function_request() and
    returns a formatted semantics string on a hit, or None on a miss.
    """

    PREFIX = "[LIBRARY SEMANTICS]"

    def __init__(self, path: Path) -> None:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Library semantics index not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        # Drop comment/metadata keys (start with _)
        self._index: dict[str, str] = {
            k: v for k, v in raw.items() if not k.startswith("_")
        }
        logger.info("Loaded library semantics index: %d entries from %s", len(self._index), path)

    def lookup(self, func_request: str) -> Optional[str]:
        """
        Look up semantics for a func_request.

        Resolution order:
          1. Extract FQN from request (returns None for app source files)
          2. Exact FQN match in index
          3. Suffix match on "ClassName.method" portion

        Returns "[LIBRARY SEMANTICS] <description>" on hit, None on miss.
        """
        fqn = extract_fqn_from_request(func_request)
        if fqn is None:
            return None

        # 1. Exact match
        if fqn in self._index:
            logger.info("Library semantics hit (exact): %s", fqn)
            return f"{self.PREFIX} {self._index[fqn]}"

        # 2. Suffix match: check if any index key ends with ".{fqn}"
        #    e.g. input "FilenameUtils.getBaseName" matches index key
        #    "org.apache.commons.io.FilenameUtils.getBaseName" because
        #    that key ends with ".FilenameUtils.getBaseName".
        dotted_suffix = f".{fqn}"
        matched_key = None
        for key in self._index:
            if key.endswith(dotted_suffix):
                matched_key = key
                break

        if matched_key is not None:
            # Check for ambiguity: warn if any other key also ends with the same suffix
            other_matches = [k for k in self._index if k != matched_key and k.endswith(dotted_suffix)]
            if other_matches:
                logger.warning(
                    "Library semantics suffix ambiguity for '%s': matched '%s' but also matches %s; "
                    "returning first match — consider using a fully-qualified name.",
                    fqn,
                    matched_key,
                    other_matches,
                )
            logger.info("Library semantics hit (suffix match '%s' via key '%s')", fqn, matched_key)
            return f"{self.PREFIX} {self._index[matched_key]}"

        return None
