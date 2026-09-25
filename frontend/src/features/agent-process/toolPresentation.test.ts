import { describe, expect, it } from "vitest";
import { toolDisplayName } from "./toolPresentation";

describe("web tool presentation", () => {
  it("labels the canonical single-page tool separately from batch fetching", () => {
    expect(toolDisplayName("web_fetch")).toBe("网页正文");
    expect(toolDisplayName("fetch_urls")).toBe("批量网页正文");
  });

  it("does not advertise the retired single-page tool alias", () => {
    expect(toolDisplayName("fetch_url")).toBe("fetch_url");
  });
});

it("labels discovery and measured scope without promising spot or commodity exports", () => {
  expect(toolDisplayName("get_stock_documents")).toBe("公告与研报目录");
  expect(toolDisplayName("get_commodity_spot_prices")).toBe("大宗商品期货行情");
  expect(toolDisplayName("get_customs_trade_data")).toBe("全国进出口总量");
});
