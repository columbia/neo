"""
Gateway YAML file finder with content-based detection
"""
from pathlib import Path
from typing import List, Optional
import yaml


class GatewayYAMLFinder:
    """Finds gateway YAML files in target codebase"""

    # Keywords that suggest a file contains gateway/routing configuration
    GATEWAY_KEYWORDS = {
        'routes', 'gateway', 'zuul', 'paths', 'endpoints',
        'ingress', 'api-gateway', 'routing', 'proxy'
    }

    def __init__(
        self,
        codebase_root: Path,
        common_paths: List[str],
        recursive: bool = True,
        max_depth: int = 10
    ):
        """
        Initialize gateway finder

        Args:
            codebase_root: Root directory of target codebase
            common_paths: List of common paths to check first
            recursive: Whether to search recursively if not found in common paths
            max_depth: Maximum depth for recursive search (-1 for unlimited)
        """
        self.codebase_root = Path(codebase_root)
        self.common_paths = common_paths
        self.recursive = recursive
        self.max_depth = max_depth

    def find_gateway_yaml(self) -> Optional[Path]:
        """
        Find gateway YAML file

        Returns:
            Path to gateway YAML file, or None if not found
        """
        # First, check common paths (filename-based)
        for common_path in self.common_paths:
            full_path = self.codebase_root / common_path
            if full_path.exists() and full_path.is_file():
                return full_path

        # If not found and recursive search enabled, search entire tree
        if self.recursive:
            return self._recursive_search()

        return None

    def find_all_gateway_yamls(self) -> List[Path]:
        """
        Find ALL potential gateway YAML files (content-based detection)

        Returns:
            List of paths to potential gateway YAML files
        """
        candidates = []

        # First add any files from common paths
        for common_path in self.common_paths:
            full_path = self.codebase_root / common_path
            if full_path.exists() and full_path.is_file():
                candidates.append(full_path)

        # Then search for YAML files with gateway-like content
        if self.recursive:
            candidates.extend(self._find_yaml_files_with_gateway_content())

        # Remove duplicates while preserving order
        seen = set()
        unique_candidates = []
        for path in candidates:
            if path not in seen:
                seen.add(path)
                unique_candidates.append(path)

        return unique_candidates

    def _recursive_search(self) -> Optional[Path]:
        """
        Recursively search for gateway YAML files (filename-based)

        Returns:
            First gateway YAML file found, or None
        """
        def search_dir(directory: Path, current_depth: int = 0) -> Optional[Path]:
            # Check depth limit
            if self.max_depth > 0 and current_depth > self.max_depth:
                return None

            try:
                # Look for gateway.yaml files in current directory
                for item in directory.iterdir():
                    if item.is_file() and item.name.endswith("gateway.yaml"):
                        return item

                # Recursively search subdirectories
                for item in directory.iterdir():
                    if item.is_dir() and not self._should_skip_dir(item.name):
                        result = search_dir(item, current_depth + 1)
                        if result:
                            return result
            except PermissionError:
                # Skip directories we can't access
                pass

            return None

        return search_dir(self.codebase_root)

    def _find_yaml_files_with_gateway_content(self) -> List[Path]:
        """
        Search for YAML/YML files that contain gateway-like configuration

        Returns:
            List of paths to YAML files with gateway content
        """
        gateway_files = []

        def search_dir(directory: Path, current_depth: int = 0):
            # Check depth limit
            if self.max_depth > 0 and current_depth > self.max_depth:
                return

            try:
                # Check all YAML files in current directory
                for item in directory.iterdir():
                    if item.is_file() and self._is_yaml_file(item):
                        if self._has_gateway_content(item):
                            gateway_files.append(item)

                # Recurse into subdirectories
                for item in directory.iterdir():
                    if item.is_dir() and not self._should_skip_dir(item.name):
                        search_dir(item, current_depth + 1)
            except PermissionError:
                # Skip directories we can't access
                pass

        search_dir(self.codebase_root)
        return gateway_files

    def _is_yaml_file(self, path: Path) -> bool:
        """Check if file is a YAML file"""
        return path.suffix.lower() in ['.yaml', '.yml']

    def _has_gateway_content(self, yaml_file: Path) -> bool:
        """
        Check if YAML file contains gateway-like configuration

        Args:
            yaml_file: Path to YAML file to check

        Returns:
            True if file contains gateway/routing configuration
        """
        try:
            # Skip very large files (> 1MB)
            if yaml_file.stat().st_size > 1_000_000:
                return False

            # Skip files with "docker" in the filename or full path
            if 'docker' in str(yaml_file).lower():
                return False

            with open(yaml_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # Quick text-based check first (fast)
            content_lower = content.lower()

            # Skip files containing "docker" keyword in content
            if 'docker' in content_lower:
                return False

            if any(keyword in content_lower for keyword in self.GATEWAY_KEYWORDS):
                # Verify it's valid YAML and has routing structure
                try:
                    # Try single document first
                    data = yaml.safe_load(content)
                    if data and isinstance(data, dict):
                        return self._is_gateway_config(data)
                except yaml.YAMLError:
                    # May be multi-document YAML, try loading all documents
                    try:
                        for doc in yaml.safe_load_all(content):
                            if doc and isinstance(doc, dict):
                                if self._is_gateway_config(doc):
                                    return True
                    except yaml.YAMLError:
                        # Not valid YAML
                        return False

            return False

        except Exception:
            # Error reading file
            return False

    def _is_gateway_config(self, data: dict) -> bool:
        """
        Check if parsed YAML data contains gateway configuration

        Args:
            data: Parsed YAML data as dictionary

        Returns:
            True if data looks like gateway configuration
        """
        # Exclude Docker Compose files (they have 'version' and 'services')
        if 'version' in data and 'services' in data:
            # This is a Docker Compose file, not a gateway config
            return False

        # Check for common gateway configuration patterns
        gateway_patterns = [
            # Spring Cloud Gateway
            ('spring', 'cloud', 'gateway', 'routes'),
            ('spring', 'cloud', 'gateway'),

            # Zuul
            ('zuul', 'routes'),

            # Generic routes
            ('routes',),

            # Kong
            ('services',),
            ('upstreams',),

            # Kubernetes Ingress/Gateway
            ('spec', 'rules'),
            ('spec', 'routes'),

            # Custom gateway configs
            ('gateway', 'routes'),
            ('api', 'routes'),
            ('endpoints',),
        ]

        for pattern in gateway_patterns:
            if self._has_nested_key(data, pattern):
                return True

        return False

    def _has_nested_key(self, data: dict, keys: tuple) -> bool:
        """
        Check if nested keys exist in dictionary

        Args:
            data: Dictionary to check
            keys: Tuple of nested keys to look for

        Returns:
            True if all nested keys exist
        """
        current = data
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return False
        return True

    def _should_skip_dir(self, dirname: str) -> bool:
        """Check if directory should be skipped in search"""
        skip_dirs = {
            '.git', '.svn', '__pycache__', 'node_modules',
            'target', 'build', '.gradle', 'dist', '.idea',
            '.venv', 'venv', 'env', 'bin', 'obj', 'pkg'
        }
        return dirname in skip_dirs
