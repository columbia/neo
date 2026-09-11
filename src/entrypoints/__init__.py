"""
Entry Point Classifier Module

Detects and classifies entry points in target applications as external or internal.
Uses ONLY gateway YAML files for detection. Returns empty results if no gateway files found.
"""

from pathlib import Path
from typing import Optional, List

from .models import (
    EntryPoint,
    EntryPointClassification,
    Protocol,
    DetectionMethod,
    DetectionResult
)
from .gateway_finder import GatewayYAMLFinder
from .gateway_scanner import GatewayScanner


def detect_entry_points(
    codebase_root: Path,
    llm_client=None,
    common_paths: Optional[List[str]] = None
) -> DetectionResult:
    """
    Detect and classify entry points using ONLY gateway YAML files.

    Args:
        codebase_root: Root directory of target codebase
        llm_client: Optional LLM client for intelligent classification
        common_paths: Optional list of common gateway file paths to check

    Returns:
        DetectionResult with entry points if gateway YAML found, empty result otherwise
    """
    # Default common gateway paths
    if common_paths is None:
        common_paths = [
            'gateway.yaml',
            'gateway.yml',
            'application-gateway.yaml',
            'application-gateway.yml',
            'src/main/resources/application.yaml',
            'src/main/resources/application.yml',
            'src/main/resources/bootstrap.yaml',
            'src/main/resources/bootstrap.yml',
            'config/gateway.yaml',
            'config/gateway.yml',
        ]

    # Find gateway YAML files
    finder = GatewayYAMLFinder(
        codebase_root=codebase_root,
        common_paths=common_paths,
        recursive=True,
        max_depth=10
    )

    gateway_files = finder.find_all_gateway_yamls()

    # If no gateway files found, return empty result
    if not gateway_files:
        return DetectionResult(
            entry_points=[],
            detection_method=DetectionMethod.GATEWAY_YAML,
            languages_detected=[],
            verbose_mode=False,
            warnings=["No gateway YAML files found in codebase"]
        )

    # Scan the first gateway file found
    scanner = GatewayScanner(
        gateway_yaml_path=gateway_files[0],
        llm_client=llm_client
    )

    return scanner.scan()


__all__ = [
    'EntryPoint',
    'EntryPointClassification',
    'Protocol',
    'DetectionMethod',
    'DetectionResult',
    'detect_entry_points'
]
