"""
Data models for entry point classification
"""
from enum import Enum
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field
from datetime import datetime


class EntryPointClassification(str, Enum):
    """Classification of entry point exposure"""
    EXTERNAL = "external"
    INTERNAL = "internal"


class Protocol(str, Enum):
    """Supported communication protocols"""
    HTTP = "http"
    GRPC = "grpc"
    GRAPHQL = "graphql"
    WEBSOCKET = "websocket"
    KAFKA = "kafka"
    RABBITMQ = "rabbitmq"
    REDIS = "redis"
    UNKNOWN = "unknown"


class DetectionMethod(str, Enum):
    """Method used to detect entry points"""
    GATEWAY_YAML = "gateway_yaml"
    TREE_SITTER = "tree_sitter"
    HYBRID = "hybrid"


class EntryPoint(BaseModel):
    """Represents a single entry point in the codebase"""
    function_id: str = Field(description="Unique identifier: function@file:line")
    type: EntryPointClassification = Field(description="External or internal classification")
    protocol: Protocol = Field(description="Communication protocol used")
    file_path: str = Field(description="Relative path to source file")
    line_range: Tuple[int, int] = Field(description="Start and end line numbers")

    # Optional fields
    confidence: Optional[float] = Field(default=None, description="Classification confidence (0-1)")
    path: Optional[str] = Field(default=None, description="API path/route if applicable")
    method: Optional[str] = Field(default=None, description="HTTP method if applicable")
    code_snippet: Optional[str] = Field(default=None, description="Extracted code snippet")
    decorators: Optional[List[str]] = Field(default=None, description="Decorators/annotations")

    def to_dict(self) -> dict:
        """Convert to dictionary with enum values as strings"""
        data = self.model_dump()
        data['type'] = self.type.value
        data['protocol'] = self.protocol.value
        return data


class DetectionResult(BaseModel):
    """Complete result of entry point detection"""
    entry_points: List[EntryPoint] = Field(description="List of detected entry points")
    detection_method: DetectionMethod = Field(description="Method used for detection")
    languages_detected: List[str] = Field(description="Programming languages found")
    verbose_mode: bool = Field(default=False, description="Whether verbose mode was enabled")
    timestamp: datetime = Field(default_factory=datetime.now, description="Detection timestamp")
    gateway_file: Optional[str] = Field(default=None, description="Path to gateway YAML file if used")
    errors: Optional[List[str]] = Field(default=None, description="Errors encountered")
    warnings: Optional[List[str]] = Field(default=None, description="Warnings generated")

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "entry_points": [ep.to_dict() for ep in self.entry_points],
            "metadata": {
                "detection_method": self.detection_method.value,
                "languages_detected": self.languages_detected,
                "verbose_mode": self.verbose_mode,
                "timestamp": self.timestamp.isoformat(),
                "gateway_file": self.gateway_file,
                "errors": self.errors,
                "warnings": self.warnings
            }
        }
