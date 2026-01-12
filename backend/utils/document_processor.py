"""
Document processing utilities using LlamaIndex.
Converts PDFs and other documents to markdown when Backboard processing fails.
"""

from pathlib import Path
from llama_index.core import SimpleDirectoryReader
from llama_index.readers.file import (
    PDFReader,
    DocxReader,
)


# Supported file types and their LlamaIndex readers
# Note: PptxReader requires torch (2GB+), skipping for now
SUPPORTED_EXTENSIONS = {
    ".pdf": PDFReader(),
    ".docx": DocxReader(),
    ".doc": DocxReader(),
    ".txt": None,  # Built-in support
    ".md": None,   # Built-in support
}


def extract_text_with_llamaindex(file_path: str | Path) -> str:
    """
    Extract text from a document using LlamaIndex readers.
    Supports PDF, DOCX, PPTX, TXT, MD files.

    Args:
        file_path: Path to the document file

    Returns:
        Extracted text content as a string
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    ext = file_path.suffix.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext}")

    # Use SimpleDirectoryReader which auto-detects file type
    reader = SimpleDirectoryReader(
        input_files=[str(file_path)],
        file_extractor=SUPPORTED_EXTENSIONS
    )

    documents = reader.load_data()

    # Combine all document text
    all_text = []
    for doc in documents:
        if doc.text.strip():
            all_text.append(doc.text)

    return "\n\n".join(all_text)


def convert_to_markdown(file_path: str | Path, original_filename: str) -> str:
    """
    Convert a document to markdown format using LlamaIndex.

    Args:
        file_path: Path to the document file
        original_filename: Original filename for title

    Returns:
        Markdown formatted string
    """
    file_path = Path(file_path)

    # Extract text using LlamaIndex
    text_content = extract_text_with_llamaindex(file_path)

    # Format as markdown
    title = Path(original_filename).stem.replace("_", " ").replace("-", " ")

    markdown_parts = [
        f"# {title}",
        "",
        text_content
    ]

    return "\n".join(markdown_parts)


def convert_document_to_markdown(file_path: str | Path, original_filename: str) -> tuple[str, bytes]:
    """
    Convert a document to markdown format.
    Supports PDF, DOCX, PPTX, TXT, MD files via LlamaIndex.

    Args:
        file_path: Path to the document file
        original_filename: Original filename for extension detection

    Returns:
        Tuple of (new_filename, markdown_content_bytes)
    """
    markdown_content = convert_to_markdown(file_path, original_filename)

    # Generate new filename
    new_filename = Path(original_filename).stem + ".md"

    return new_filename, markdown_content.encode("utf-8")


def can_convert(original_filename: str) -> bool:
    """
    Check if a file type can be converted to markdown.
    """
    ext = Path(original_filename).suffix.lower()
    return ext in SUPPORTED_EXTENSIONS
