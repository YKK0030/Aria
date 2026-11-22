from __future__ import annotations

import base64
import io
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from agent_core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class VisionConfig:
    model: str = "llava:7b"  # Ollama model for vision
    max_image_size: int = 10 * 1024 * 1024  # 10MB
    supported_formats: tuple = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif")
    ollama_host: str = "http://host.docker.internal:11434"


@dataclass
class ImageAnalysis:
    description: str
    objects: list[str] = None
    text_content: str = ""
    ui_elements: list[dict] = None
    code_snippets: list[str] = None
    diagrams: list[dict] = None
    charts: list[dict] = None
    error: str = ""

    def __post_init__(self):
        if self.objects is None:
            self.objects = []
        if self.ui_elements is None:
            self.ui_elements = []
        if self.code_snippets is None:
            self.code_snippets = []
        if self.diagrams is None:
            self.diagrams = []
        if self.charts is None:
            self.charts = []

    def to_dict(self) -> dict[str, Any]:
        return {
            "description": self.description,
            "objects": self.objects,
            "text_content": self.text_content,
            "ui_elements": self.ui_elements,
            "code_snippets": self.code_snippets,
            "diagrams": self.diagrams,
            "charts": self.charts,
            "error": self.error,
        }


class VisionEngine:
    def __init__(self, config: VisionConfig | None = None):
        self.config = config or VisionConfig()
        self._ollama_client = None
        self._init_client()

    def _init_client(self):
        try:
            import ollama
            self._ollama_client = ollama.Client(host=self.config.ollama_host)
            logger.info("Vision engine initialized with Ollama at %s", self.config.ollama_host)
        except ImportError:
            logger.warning("Ollama client not available. Install ollama package.")
            self._ollama_client = None

    def analyze_image(
        self,
        image_data: bytes | str,
        prompt: str | None = None,
        is_base64: bool = True,
    ) -> ImageAnalysis:
        """Analyze an image and return structured analysis."""
        if not self._ollama_client:
            return ImageAnalysis(
                description="",
                error="Vision engine not available (ollama not installed)",
            )

        # Prepare image
        if isinstance(image_data, str) and Path(image_data).exists():
            # File path
            with open(image_data, "rb") as f:
                img_bytes = f.read()
            image_b64 = base64.b64encode(img_bytes).decode()
        elif is_base64 and isinstance(image_data, str):
            # Already base64
            image_b64 = image_data
        else:
            # Raw bytes
            image_b64 = base64.b64encode(image_data).decode() if isinstance(image_data, bytes) else ""

        if not image_b64:
            return ImageAnalysis(description="", error="No valid image data provided")

        # Check size
        if len(image_b64) > self.config.max_image_size * 4/3:  # base64 overhead
            return ImageAnalysis(description="", error="Image too large")

        # Default comprehensive prompt
        if prompt is None:
            prompt = """Analyze this image in detail. Provide:
1. A comprehensive description of what you see
2. List all visible objects/elements
3. Extract any text content (OCR)
4. Identify UI elements (buttons, forms, menus, etc.)
5. Find any code snippets or technical content
6. Describe any diagrams, charts, or visualizations
7. Note any errors, warnings, or notable UI states

Be thorough and structured in your response."""

        try:
            response = self._ollama_client.chat(
                model=self.config.model,
                messages=[{
                    "role": "user",
                    "content": prompt,
                    "images": [image_b64],
                }],
                options={"temperature": 0.1},
            )

            content = response.get("message", {}).get("content", "")
            return self._parse_analysis(content)
        except Exception as e:
            logger.error("Vision analysis failed: %s", e)
            return ImageAnalysis(description="", error=str(e))

    def _parse_analysis(self, content: str) -> ImageAnalysis:
        """Parse the model's response into structured analysis."""
        # Simple parsing - in production, use structured output
        lines = content.split("\n")
        description = content

        # Extract sections if model follows format
        objects = []
        text_content = ""
        ui_elements = []
        code_snippets = []
        diagrams = []
        charts = []

        current_section = None
        for line in lines:
            line = line.strip()
            if not line:
                continue

            lower = line.lower()
            if "object" in lower and ":" in lower:
                current_section = "objects"
            elif "text" in lower and "content" in lower:
                current_section = "text"
            elif "ui" in lower and "element" in lower:
                current_section = "ui"
            elif "code" in lower and "snippet" in lower:
                current_section = "code"
            elif "diagram" in lower:
                current_section = "diagrams"
            elif "chart" in lower:
                current_section = "charts"
            elif line.startswith("-") or line.startswith("•"):
                item = line.lstrip("-• ").strip()
                if current_section == "objects":
                    objects.append(item)
                elif current_section == "ui":
                    ui_elements.append({"description": item})
                elif current_section == "code":
                    code_snippets.append(item)
                elif current_section == "diagrams":
                    diagrams.append({"description": item})
                elif current_section == "charts":
                    charts.append({"description": item})
            elif current_section == "text":
                text_content += line + "\n"

        return ImageAnalysis(
            description=description,
            objects=objects,
            text_content=text_content.strip(),
            ui_elements=ui_elements,
            code_snippets=code_snippets,
            diagrams=diagrams,
            charts=charts,
        )

    async def analyze_image_async(
        self,
        image_data: bytes | str,
        prompt: str | None = None,
        is_base64: bool = True,
    ) -> ImageAnalysis:
        import asyncio
        return await asyncio.get_event_loop().run_in_executor(
            None, self.analyze_image, image_data, prompt, is_base64
        )

    def analyze_screenshot(self, image_data: bytes | str, is_base64: bool = True) -> ImageAnalysis:
        """Specialized analysis for screenshots."""
        prompt = """This is a screenshot. Analyze it for:
1. Application/window title and type
2. All visible UI elements (buttons, inputs, menus, tabs, etc.)
3. Any text content, error messages, or notifications
4. Code editors, terminals, or IDE content
5. Browser URL bar and page content
6. File explorers, directory structures
7. Any diagrams, charts, or data visualizations
8. Color themes, layout structure

Provide a structured analysis suitable for a developer assistant to understand the user's context."""
        return self.analyze_image(image_data, prompt, is_base64)

    def analyze_diagram(self, image_data: bytes | str, is_base64: bool = True) -> ImageAnalysis:
        """Specialized analysis for diagrams/charts."""
        prompt = """This is a diagram, chart, or technical drawing. Analyze:
1. Type of diagram (flowchart, sequence, architecture, ERD, UML, etc.)
2. All components/nodes and their relationships
3. Labels, annotations, and text
4. Data flow or process flow
5. Any legends, keys, or color coding
6. Technical specifications visible
7. Mermaid/PlantUML representation if applicable

Provide a detailed technical description."""
        return self.analyze_image(image_data, prompt, is_base64)

    def extract_text(self, image_data: bytes | str, is_base64: bool = True) -> str:
        """OCR - extract all text from image."""
        prompt = "Extract ALL text from this image. Preserve formatting, line breaks, and structure. Include code, UI text, labels, everything readable."
        result = self.analyze_image(image_data, prompt, is_base64)
        return result.text_content

    def is_available(self) -> bool:
        return self._ollama_client is not None


# Global instance
vision_engine = VisionEngine()
