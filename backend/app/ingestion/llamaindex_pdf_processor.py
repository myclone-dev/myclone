"""
PDF processor using native LlamaIndex readers with interface pattern
This uses LlamaIndex's built-in PDF reading capabilities following the same patterns
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PDFReaderInterface(ABC):
    """Interface for PDF readers"""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this reader is available"""
        pass

    @abstractmethod
    async def process(self, file_path: str) -> Dict[str, Any]:
        """Process PDF file and return content"""
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Get reader name"""
        pass

    @abstractmethod
    def get_quality(self) -> str:
        """Get extraction quality level"""
        pass


class PyMuPDFReaderAdapter(PDFReaderInterface):
    """PyMuPDF reader adapter"""

    def __init__(self):
        self._available = None
        self._reader_class = None

    def is_available(self) -> bool:
        if self._available is None:
            try:
                from llama_index.readers.file import PyMuPDFReader

                self._reader_class = PyMuPDFReader
                self._available = True
                logger.info("✅ LlamaIndex PyMuPDFReader available - high quality parsing")
            except ImportError:
                self._available = False
                logger.info("ℹ️ PyMuPDFReader not available - requires PyMuPDF: pip install PyMuPDF")
        return self._available

    async def process(self, file_path: str) -> Dict[str, Any]:
        if not self.is_available():
            raise RuntimeError("PyMuPDFReader not available")

        # Get page count using PyMuPDF directly
        page_count = 0
        try:
            import fitz  # PyMuPDF

            with fitz.open(file_path) as pdf_doc:
                page_count = len(pdf_doc)
        except Exception as e:
            logger.warning(f"Could not extract page count with PyMuPDF: {e}")

        reader = self._reader_class()
        documents = reader.load_data(file_path)

        content_parts = []
        total_metadata = {}

        for doc in documents:
            content_parts.append(doc.text)
            if hasattr(doc, "metadata") and doc.metadata:
                total_metadata.update(doc.metadata)

        return {
            "content": "\n\n".join(content_parts),
            "documents": len(documents),
            "reader": self.get_name(),
            "metadata": {
                **total_metadata,
                "page_count": page_count,
                "extraction_quality": self.get_quality(),
                "llamaindex_reader": True,
            },
        }

    def get_name(self) -> str:
        return "PyMuPDFReader"

    def get_quality(self) -> str:
        return "high"


class PDFReaderAdapter(PDFReaderInterface):
    """Standard PDF reader adapter"""

    def __init__(self):
        self._available = None
        self._reader_class = None

    def is_available(self) -> bool:
        if self._available is None:
            try:
                from llama_index.readers.file import PDFReader

                self._reader_class = PDFReader
                self._available = True
                logger.info("✅ LlamaIndex PDFReader available - reliable parsing")
            except ImportError:
                self._available = False
                logger.info(
                    "⚠️ PDFReader not available - check llama-index-readers-file installation"
                )
        return self._available

    async def process(self, file_path: str) -> Dict[str, Any]:
        if not self.is_available():
            raise RuntimeError("PDFReader not available")

        # Try to get page count
        page_count = 0
        try:
            # Try using pypdf to get page count
            from pypdf import PdfReader

            with open(file_path, "rb") as f:
                pdf = PdfReader(f)
                page_count = len(pdf.pages)
        except Exception as e:
            logger.warning(f"Could not extract page count with pypdf: {e}")

        reader = self._reader_class()
        documents = reader.load_data(file_path)

        content_parts = []
        total_metadata = {}

        for doc in documents:
            content_parts.append(doc.text)
            if hasattr(doc, "metadata") and doc.metadata:
                total_metadata.update(doc.metadata)

        return {
            "content": "\n\n".join(content_parts),
            "documents": len(documents),
            "reader": self.get_name(),
            "metadata": {
                **total_metadata,
                "page_count": page_count,
                "extraction_quality": self.get_quality(),
                "llamaindex_reader": True,
            },
        }

    def get_name(self) -> str:
        return "PDFReader"

    def get_quality(self) -> str:
        return "good"


class SimpleDirectoryReaderAdapter(PDFReaderInterface):
    """Simple directory reader adapter"""

    def __init__(self):
        self._available = None
        self._reader_class = None

    def is_available(self) -> bool:
        if self._available is None:
            try:
                from llama_index.core import SimpleDirectoryReader

                self._reader_class = SimpleDirectoryReader
                self._available = True
                logger.info("✅ LlamaIndex SimpleDirectoryReader available - general file reader")
            except ImportError:
                self._available = False
                logger.info("⚠️ SimpleDirectoryReader not available")
        return self._available

    async def process(self, file_path: str) -> Dict[str, Any]:
        if not self.is_available():
            raise RuntimeError("SimpleDirectoryReader not available")

        # SimpleDirectoryReader doesn't provide page count easily
        # We'll default to 0 and let the caller handle it
        page_count = 0

        reader = self._reader_class(input_files=[file_path])
        documents = reader.load_data()

        content_parts = []
        total_metadata = {}

        for doc in documents:
            content_parts.append(doc.text)
            if hasattr(doc, "metadata") and doc.metadata:
                total_metadata.update(doc.metadata)

        return {
            "content": "\n\n".join(content_parts),
            "documents": len(documents),
            "reader": self.get_name(),
            "metadata": {
                **total_metadata,
                "page_count": page_count,
                "extraction_quality": self.get_quality(),
                "llamaindex_reader": True,
            },
        }

    def get_name(self) -> str:
        return "SimpleDirectoryReader"

    def get_quality(self) -> str:
        return "standard"


class LlamaIndexPDFProcessor:
    """
    PDF processor using LlamaIndex native PDF readers with interface pattern
    Uses the same approach as your existing LlamaIndex setup - local processing only
    """

    def __init__(self):
        """Initialize with available PDF reader adapters"""
        self.readers: List[PDFReaderInterface] = [
            PyMuPDFReaderAdapter(),
            PDFReaderAdapter(),
            SimpleDirectoryReaderAdapter(),
        ]
        self.available_readers = []
        self._initialize_available_readers()

    def _initialize_available_readers(self):
        """Initialize and discover available PDF readers"""
        for reader in self.readers:
            if reader.is_available():
                self.available_readers.append(reader.get_name())

    async def process_pdf(
        self, file_path: str, metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process PDF using the best available LlamaIndex reader

        Args:
            file_path: Path to the PDF file
            metadata: Optional metadata to include

        Returns:
            Dict containing extracted content and metadata
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Check file extension as first validation
        if not path.suffix.lower() == ".pdf":
            raise ValueError(f"File does not have .pdf extension: {file_path}")

        # Check PDF magic bytes for content-based validation
        try:
            with open(file_path, "rb") as f:
                header = f.read(5)
                if header != b"%PDF-":
                    raise ValueError(
                        f"Invalid PDF file content (missing PDF magic bytes): {file_path}"
                    )
        except IOError as e:
            raise ValueError(f"Cannot read file for validation: {file_path}") from e

        # Try readers in initialization order (already ordered by preference: highest quality first)
        available_readers = [reader for reader in self.readers if reader.is_available()]

        if not available_readers:
            raise Exception("No LlamaIndex PDF readers available")

        last_error = None
        for reader in available_readers:
            try:
                logger.info(f"📄 Processing PDF with LlamaIndex {reader.get_name()}: {path.name}")
                result = await reader.process(file_path)

                # Add common metadata
                result.update(
                    {
                        "source": path.name,
                        "file_type": ".pdf",
                        "parser": "llamaindex_" + reader.get_name().lower(),
                        "metadata": {
                            **(metadata or {}),
                            **result.get("metadata", {}),
                            "file_size": path.stat().st_size,
                            "extracted_at": datetime.utcnow().isoformat(),
                            "extraction_method": f"llamaindex_{reader.get_name().lower()}",
                            "api_required": False,
                            "local_processing": True,
                        },
                    }
                )

                logger.info(
                    f"✅ Successfully processed with {reader.get_name()}: {len(result['content'])} characters"
                )
                return result

            except Exception as e:
                logger.warning(f"⚠️ {reader.get_name()} failed: {e}")
                last_error = e
                continue

        # If all readers failed
        raise Exception(f"All LlamaIndex PDF readers failed. Last error: {last_error}")

    def get_reader_info(self) -> Dict[str, Any]:
        """Get information about available LlamaIndex readers"""
        reader_types = {}
        installation_notes = {}

        for reader in self.readers:
            reader_types[reader.get_name()] = f"{reader.get_quality().title()} quality extraction"
            if not reader.is_available():
                if reader.get_name() == "PyMuPDFReader":
                    installation_notes["PyMuPDF_required"] = "pip install PyMuPDF"
                elif reader.get_name() == "PDFReader":
                    installation_notes["readers_file_required"] = (
                        "pip install llama-index-readers-file"
                    )
            else:
                installation_notes[f"{reader.get_name()}_status"] = "✅ Installed"

        return {
            "available_readers": self.available_readers,
            "reader_types": reader_types,
            "installation_notes": installation_notes,
        }


def get_llamaindex_pdf_processor() -> LlamaIndexPDFProcessor:
    """
    Get a configured LlamaIndexPDFProcessor instance

    Returns:
        Processor using available LlamaIndex readers
    """
    processor = LlamaIndexPDFProcessor()

    if not processor.available_readers:
        logger.warning("❌ No LlamaIndex PDF readers available")
    else:
        logger.info(
            f"📄 LlamaIndex PDF processing ready with: {', '.join(processor.available_readers)}"
        )

    return processor
