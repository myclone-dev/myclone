import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class FileProcessor:
    def __init__(self):
        self.supported_extensions = {
            ".txt": self.process_text,
            ".json": self.process_json,
            ".md": self.process_markdown,
        }

    async def process_file(
        self, file_path: str, metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        extension = path.suffix.lower()

        if extension not in self.supported_extensions:
            raise ValueError(f"Unsupported file type: {extension}")

        processor = self.supported_extensions[extension]
        content = await processor(file_path)

        return {
            "content": content,
            "source": path.name,
            "file_type": extension,
            "metadata": {
                **(metadata or {}),
                "file_size": path.stat().st_size,
                "modified_date": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
                "extracted_at": datetime.utcnow().isoformat(),
            },
        }

    async def process_text(self, file_path: str) -> str:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            return self.clean_text(content)
        except Exception as e:
            logger.error(f"Error processing text file {file_path}: {e}")
            raise

    async def process_json(self, file_path: str) -> str:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, list):
                content = []
                for item in data:
                    if isinstance(item, dict):
                        if "text" in item:
                            content.append(item["text"])
                        elif "content" in item:
                            content.append(item["content"])
                        elif "message" in item:
                            content.append(item["message"])
                        else:
                            content.append(json.dumps(item))
                    else:
                        content.append(str(item))
                return self.clean_text("\n".join(content))
            elif isinstance(data, dict):
                if "text" in data:
                    return self.clean_text(data["text"])
                elif "content" in data:
                    return self.clean_text(data["content"])
                else:
                    return self.clean_text(json.dumps(data, indent=2))
            else:
                return self.clean_text(str(data))
        except Exception as e:
            logger.error(f"Error processing JSON file {file_path}: {e}")
            raise

    async def process_markdown(self, file_path: str) -> str:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            content = re.sub(r"^#{1,6}\s+", "", content, flags=re.MULTILINE)
            content = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", content)
            content = re.sub(r"[*_]{1,2}([^*_]+)[*_]{1,2}", r"\1", content)
            content = re.sub(r"```[^`]*```", "", content, flags=re.DOTALL)
            content = re.sub(r"`([^`]+)`", r"\1", content)

            return self.clean_text(content)
        except Exception as e:
            logger.error(f"Error processing Markdown file {file_path}: {e}")
            raise

    def clean_text(self, text: str) -> str:
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = text.strip()
        return text


class TranscriptProcessor:
    def __init__(self):
        self.speaker_patterns = [
            r"^([A-Z][^:]+):\s*(.+)$",
            r"^\[([^\]]+)\]\s*(.+)$",
            r"^<([^>]+)>\s*(.+)$",
        ]

    async def process_transcript(self, content: str, format: str = "auto") -> List[Dict[str, str]]:
        lines = content.split("\n")
        messages = []
        current_speaker = None
        current_text = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            speaker_found = False
            for pattern in self.speaker_patterns:
                match = re.match(pattern, line)
                if match:
                    if current_speaker and current_text:
                        messages.append(
                            {"speaker": current_speaker, "text": " ".join(current_text)}
                        )
                    current_speaker = match.group(1)
                    current_text = [match.group(2)]
                    speaker_found = True
                    break

            if not speaker_found and current_speaker:
                current_text.append(line)
            elif not speaker_found:
                messages.append({"speaker": "Unknown", "text": line})

        if current_speaker and current_text:
            messages.append({"speaker": current_speaker, "text": " ".join(current_text)})

        return messages
