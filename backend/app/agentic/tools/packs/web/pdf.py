"""网页 PDF 内容识别与提取。"""

import io
import logging
from typing import Any

logger = logging.getLogger(__name__)


def detect_content_type(content_type_header: str | None) -> str:
    """Normalize an HTTP Content-Type header."""
    if not content_type_header:
        return "unknown"
    content_type = content_type_header.split(";")[0].strip().lower()
    if "html" in content_type:
        return "html"
    if "pdf" in content_type:
        return "pdf"
    if "json" in content_type:
        return "json"
    if "xml" in content_type:
        return "xml"
    return "text"


def handle_pdf_response(response: Any, url: str) -> dict[str, Any]:
    """Extract text from the first five PDF pages when possible."""
    pdf_bytes = response.content
    text = ""
    try:
        import pdfplumber

        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pages_text = []
            for index, page in enumerate(pdf.pages):
                if index >= 5:
                    break
                if page_text := page.extract_text():
                    pages_text.append(page_text)
            text = "\n\n".join(pages_text)
    except ImportError:
        pass
    except Exception as error:
        logger.info("pdfplumber 提取失败: %s", error)

    if not text:
        try:
            from PyPDF2 import PdfReader

            reader = PdfReader(io.BytesIO(pdf_bytes))
            pages_text = []
            for index, page in enumerate(reader.pages):
                if index >= 5:
                    break
                if page_text := page.extract_text():
                    pages_text.append(page_text)
            text = "\n\n".join(pages_text)
        except ImportError:
            pass
        except Exception as error:
            logger.info("PyPDF2 提取失败: %s", error)

    if text:
        return {
            "url": url,
            "title": text[:60].split("\n")[0].strip(),
            "content": text,
            "content_type": "pdf",
        }
    return {
        "url": url,
        "title": "",
        "content": f"[PDF 文档，共 {len(pdf_bytes)} 字节。无法直接提取文本内容，请下载后阅读。]",
        "content_type": "pdf",
    }
