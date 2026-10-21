"""百度 7×24 快讯单元测试。"""

from __future__ import annotations

from unittest.mock import MagicMock

from app.infrastructure.providers.baidu import news as baidu_news


def test_fetch_market_kuaixun_uses_standard_transport() -> None:
    transport = MagicMock()
    transport.get_json.return_value = {
        "ResultCode": "0",
        "Result": {
            "content": {
                "list": [
                    {
                        "title": "测试快讯标题",
                        "content": {"items": [{"data": "测试快讯正文内容"}]},
                        "publish_time": 1729482000,
                        "third_url": "https://example.com/news/1",
                        "author": "百度财经",
                        "read_count": 100,
                        "comment_count": 10,
                    }
                ]
            }
        },
    }

    def dummy_parser(ts):
        return "2026-10-21 11:40:00"

    items = baidu_news.fetch_market_kuaixun(transport, dummy_parser)

    # 验证使用的是相对路径，且未强行覆盖 headers，交由 transport 自行注入 acs-token 与默认头
    transport.get_json.assert_called_once_with(
        "/selfselect/expressnews",
        params={
            "rn": "20",
            "pn": "0",
            "tag": "",
            "filterByUserStocks": "0",
            "finClientType": "pc",
        },
    )
    assert len(items) == 1
    assert items[0].title == "测试快讯标题"
    assert items[0].content == "测试快讯正文内容"
    assert items[0].source == "百度 7x24 快讯"
    assert items[0].publish_time == "2026-10-21 11:40:00"


def test_baidu_transport_get_json_merges_headers() -> None:
    from app.infrastructure.providers.baidu.transport import BaiduTransport

    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ResultCode": "0"}
    mock_session.get.return_value = mock_resp

    transport = BaiduTransport(
        credentials_provider=lambda: ("dummy_cookie", "dummy_token"),
        session=mock_session,
    )

    transport.get_json("/test", params={"k": "v"}, headers={"Custom-Header": "foo"})

    call_args = mock_session.get.call_args
    assert call_args is not None
    sent_headers = call_args[1]["headers"]
    assert sent_headers["acs-token"] == "dummy_token"
    assert sent_headers["Custom-Header"] == "foo"
    assert sent_headers["Host"] == "finance.pae.baidu.com"

