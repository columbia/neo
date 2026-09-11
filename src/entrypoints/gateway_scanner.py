"""
Gateway YAML scanner using LLM classification only
"""
from pathlib import Path
import json
from typing import List, Dict

from pydantic import BaseModel, Field

from entrypoints.models import (
    EntryPoint,
    EntryPointClassification,
    Protocol,
    DetectionMethod,
    DetectionResult
)
from entrypoints.prompts.gateway_classification_prompt import GATEWAY_CLASSIFICATION_PROMPT
from entrypoints.prompts.gateway_classification_examples import GATEWAY_EXAMPLES

from langchain_core.prompts import ChatPromptTemplate, FewShotChatMessagePromptTemplate


class GatewayConfig(BaseModel):
    """Pydantic model for LLM output"""
    external_entries: list[str] = Field(
        description="A list of all user-accessible (externally exposed) entry point paths."
    )
    internal_entries: list[str] = Field(
        description="A list of all internal (not externally exposed) entry point paths."
    )


class GatewayScanner:
    """Scans gateway YAML files to classify entry points"""

    @classmethod
    def _load_prompt_template(cls) -> str:
        """Load the gateway classification prompt template"""
        return GATEWAY_CLASSIFICATION_PROMPT

    @classmethod
    def _load_examples(cls) -> List[Dict[str, str]]:
        """Load the gateway classification examples"""
        return GATEWAY_EXAMPLES

    def __init__(self, gateway_yaml_path: Path, llm_client):
        """
        Initialize gateway scanner

        Args:
            gateway_yaml_path: Path to gateway YAML file
            llm_client: LLM client (from neo common.llms) - REQUIRED
        """
        if llm_client is None:
            raise ValueError("LLM client is required for gateway scanning")

        self.gateway_yaml_path = Path(gateway_yaml_path)
        self.llm_client = llm_client

        # Load prompt template and examples
        self.prompt_template = self._load_prompt_template()
        self.examples = self._load_examples()

    def scan(self) -> DetectionResult:
        """
        Scan gateway YAML and classify entry points using LLM

        Returns:
            DetectionResult with classified entry points
        """
        # Read gateway YAML
        with open(self.gateway_yaml_path, 'r') as f:
            gateway_content = f.read()

        # Use LLM for classification
        return self._llm_classification(gateway_content)

    def _llm_classification_direct(self, gateway_content: str) -> DetectionResult:
        """
        Direct LLM classification using common.llms.LLMClient (without langchain)
        """
        # Build prompt with examples
        prompt = self._build_classification_prompt(gateway_content)

        # Call LLM
        response = self.llm_client.messages_create(
            history=[],
            message=[{"role": "user", "content": prompt}],
            max_tokens=2000,
            temperature=0.1
        )

        # Parse JSON response
        response_text = response.content[0].text

        # Extract JSON from response (handle markdown code blocks)
        json_text = response_text
        if "```json" in response_text:
            json_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            json_text = response_text.split("```")[1].split("```")[0].strip()

        try:
            result_dict = json.loads(json_text)
            result = GatewayConfig(**result_dict)
        except (json.JSONDecodeError, ValueError) as e:
            # Return error in DetectionResult if parsing fails
            return DetectionResult(
                entry_points=[],
                detection_method=DetectionMethod.GATEWAY_YAML,
                languages_detected=['yaml'],
                verbose_mode=False,
                gateway_file=str(self.gateway_yaml_path),
                errors=[f"Failed to parse LLM response: {e}"]
            )

        # Convert to EntryPoint objects
        entry_points = []

        for idx, path in enumerate(result.external_entries):
            entry = EntryPoint(
                function_id=f"gateway_external_{idx}@{self.gateway_yaml_path.name}",
                type=EntryPointClassification.EXTERNAL,
                protocol=Protocol.HTTP,
                file_path=str(self.gateway_yaml_path),
                line_range=(0, 0),
                path=path,
                confidence=0.95
            )
            entry_points.append(entry)

        for idx, path in enumerate(result.internal_entries):
            entry = EntryPoint(
                function_id=f"gateway_internal_{idx}@{self.gateway_yaml_path.name}",
                type=EntryPointClassification.INTERNAL,
                protocol=Protocol.HTTP,
                file_path=str(self.gateway_yaml_path),
                line_range=(0, 0),
                path=path,
                confidence=0.95
            )
            entry_points.append(entry)

        return DetectionResult(
            entry_points=entry_points,
            detection_method=DetectionMethod.GATEWAY_YAML,
            languages_detected=['yaml'],
            verbose_mode=False,
            gateway_file=str(self.gateway_yaml_path)
        )

    def _build_classification_prompt(self, gateway_content: str) -> str:
        """Build prompt with few-shot examples"""
        prompt = self.prompt_template.format(input=self.examples[0]["input"])
        prompt += f"\n\nAssistant: {self.examples[0]['output']}\n\n"
        prompt += "Human: " + self.prompt_template.format(input=gateway_content)
        prompt += '\n\nPlease respond with a JSON object in the format: {"external_entries": [...], "internal_entries": [...]}'
        return prompt

    def _llm_classification(self, gateway_content: str) -> DetectionResult:
        """
        LLM-based classification using langchain structured output
        """
        # Create few-shot prompt
        example_prompt = ChatPromptTemplate.from_messages([
            ("human", self.prompt_template),
            ("ai", "{output}")
        ])

        few_shot_prompt = FewShotChatMessagePromptTemplate(
            examples=self.examples,
            example_prompt=example_prompt
        )

        final_prompt = ChatPromptTemplate.from_messages([
            few_shot_prompt,
            ("human", self.prompt_template)
        ])

        # Get structured output from LLM
        structured_llm = self.llm_client.with_structured_output(GatewayConfig)
        chain = final_prompt | structured_llm

        # Invoke chain
        result: GatewayConfig = chain.invoke({"input": gateway_content})

        # Convert to EntryPoint objects
        entry_points = []

        for idx, path in enumerate(result.external_entries):
            entry = EntryPoint(
                function_id=f"gateway_external_{idx}@{self.gateway_yaml_path.name}",
                type=EntryPointClassification.EXTERNAL,
                protocol=Protocol.HTTP,
                file_path=str(self.gateway_yaml_path),
                line_range=(0, 0),  # Unknown line numbers
                path=path,
                confidence=0.95  # High confidence for LLM
            )
            entry_points.append(entry)

        for idx, path in enumerate(result.internal_entries):
            entry = EntryPoint(
                function_id=f"gateway_internal_{idx}@{self.gateway_yaml_path.name}",
                type=EntryPointClassification.INTERNAL,
                protocol=Protocol.HTTP,
                file_path=str(self.gateway_yaml_path),
                line_range=(0, 0),
                path=path,
                confidence=0.95
            )
            entry_points.append(entry)

        return DetectionResult(
            entry_points=entry_points,
            detection_method=DetectionMethod.GATEWAY_YAML,
            languages_detected=['yaml'],
            verbose_mode=False,
            gateway_file=str(self.gateway_yaml_path)
        )
