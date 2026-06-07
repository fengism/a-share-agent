from types import SimpleNamespace

from app.adapters.feishu import client


class _Response:
    status_code = 200

    def __init__(self, payload):
        """Store payload and serialise it as text for json/text accessors.

        Param:
            payload: arbitrary JSON-serialisable value returned by the mock HTTP call.
        Return:
            None
        """
        self._payload = payload
        self.text = str(payload)

    def json(self):
        """Return the pre-stored JSON payload.

        Return:
            the payload object passed during construction.
        """
        return self._payload


def _settings():
    """Return a minimal settings stub with folder/space tokens.

    Return:
        a SimpleNamespace exposing feishu_wiki_space_id and feishu_folder_token attributes.
    """
    return SimpleNamespace(
        feishu_wiki_space_id="",
        feishu_folder_token="default-folder",
    )


def test_create_doc_writes_drive_document(monkeypatch):
    """create_doc writes blocks to Drive when no wiki_space_id is provided."""
    posts = []

    def fake_post(url, **kwargs):
        posts.append((url, kwargs))
        if url == client._DOC_URL:
            return _Response({"code": 0, "data": {"document": {"document_id": "doc-source"}}})
        return _Response({"code": 0, "data": {"children": []}})

    monkeypatch.setattr(client, "_validate_settings", _settings)
    monkeypatch.setattr(client, "_auth_headers", lambda: {})
    monkeypatch.setattr(client.requests, "post", fake_post)

    result = client.create_doc("标题", [{"block_type": 2}], folder_token="folder-a")

    assert result == {"url": "https://feishu.cn/docx/doc-source", "node_token": ""}
    assert posts[0][1]["json"] == {"title": "标题", "folder_token": "folder-a"}
    assert posts[1][0].endswith("/doc-source/blocks/doc-source/children")


def test_create_doc_wiki_writes_wiki_obj_token_and_deletes_source(monkeypatch):
    """create_doc moves the doc to Wiki and deletes the intermediate Drive file."""
    posts = []
    deletes = []

    def fake_post(url, **kwargs):
        posts.append((url, kwargs))
        if url == client._DOC_URL:
            return _Response({"code": 0, "data": {"document": {"document_id": "doc-source"}}})
        if url == client._WIKI_NODE_URL.format(space_id="space-a"):
            return _Response({"code": 0, "data": {"node": {"node_token": "wiki-node", "obj_token": "wiki-doc"}}})
        return _Response({"code": 0, "data": {"children": []}})

    def fake_delete(url, **kwargs):
        deletes.append((url, kwargs))
        return _Response({"code": 0})

    monkeypatch.setattr(client, "_validate_settings", _settings)
    monkeypatch.setattr(client, "_auth_headers", lambda: {})
    monkeypatch.setattr(client.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(client.requests, "post", fake_post)
    monkeypatch.setattr(client.requests, "delete", fake_delete)

    result = client.create_doc("标题", [{"block_type": 2}], folder_token="folder-a", wiki_space_id="space-a", wiki_parent_node_token="parent-a")

    assert result == {"url": "https://feishu.cn/wiki/wiki-node", "node_token": "wiki-node"}
    assert posts[0][1]["json"] == {"title": "标题"}
    assert posts[1][1]["json"] == {
        "obj_type": "docx",
        "obj_token": "doc-source",
        "node_type": "origin",
        "title": "标题",
        "parent_node_token": "parent-a",
    }
    assert posts[2][0].endswith("/wiki-doc/blocks/wiki-doc/children")
    assert deletes == [
        (
            client._DRIVE_FILE_URL.format(file_token="doc-source"),
            {"headers": {}, "params": {"type": "docx"}, "timeout": 10},
        )
    ]
