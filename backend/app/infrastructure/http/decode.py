"""Charset-aware decoding for HTML responses.

``lxml.etree.fromstring``/``lxml.html.fromstring`` fall back to **latin-1** when
handed raw ``bytes`` without an explicit encoding argument, so UTF-8 pages decode
into mojibake (``贵州`` → ``è´µå·``) even when the server and the document both
declare UTF-8. Always decode to ``str`` first, then parse.
"""

import codecs
import re
from typing import Any

_CHARSET = re.compile(br"charset\s*=\s*[\"']?\s*([a-zA-Z0-9._-]+)", re.I)


def decode_html_response(response: Any) -> str:
    """Decode a ``requests``-like response body to text without charset guessing errors.

    Honors charset declarations (header, then in-document ``<meta>``) and valid
    UTF-8 before falling back to statistical detection, because GBK pages were
    otherwise guessed as Korean.

    Param:
        response: object exposing ``content``/``headers`` and optionally
            ``encoding``/``text``, i.e. a ``requests.Response``.
    Return:
        Decoded text; never raises on undecodable bytes (falls back to replacement).
    """
    raw = getattr(response, "content", None)
    if not isinstance(raw, bytes):
        return str(response.text)
    declared = []
    header = str(response.headers.get("content-type") or "").encode("ascii", "ignore")
    for source in (header, raw[:4096]):
        match = _CHARSET.search(source)
        if match:
            declared.append(match[1].decode("ascii"))
    candidates = [*declared, "utf-8", getattr(response, "apparent_encoding", None)]
    for encoding in candidates:
        if not encoding:
            continue
        try:
            codecs.lookup(encoding)
            return raw.decode(encoding, "strict")
        except (LookupError, UnicodeDecodeError):
            continue
    return raw.decode("utf-8", "replace")
