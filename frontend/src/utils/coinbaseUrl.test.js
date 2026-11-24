import { describe, expect, it } from "vitest";
import coinbaseSpotUrl, { getCoinbaseAdvancedSpotUrl, getExternalAlertSourceUrl } from "./coinbaseUrl";

describe("getCoinbaseAdvancedSpotUrl", () => {
  it.each([
    "RENDER", "RENDER-USD", "render/usd", "RENDER-USDC", " render ",
    { product_id: "render-usdc" },
    { symbol: "RENDER/USD" },
    { base_currency: "render" },
    { productId: "RENDER" },
    { product_id: "RENDER-USD", symbol: "BTC" },
    { symbol: "RENDER", trade_url: "https://www.coinbase.com/advanced-trade" },
    { symbol: "RENDER", tradeUrl: "https://www.coinbase.com/advanced-trade/spot/BTC" },
  ])("normalizes %j to the exact USD spot page", (coin) => {
    expect(getCoinbaseAdvancedSpotUrl(coin)).toBe(
      "https://www.coinbase.com/advanced-trade/spot/RENDER-USD",
    );
    expect(coinbaseSpotUrl(coin)).toBe(getCoinbaseAdvancedSpotUrl(coin));
  });

  it.each(["BTC", "BTC-USD", "BTC/USD", "BTC-USDC", { base_currency: "btc" }])(
    "supports BTC identity %j",
    (coin) => {
      expect(getCoinbaseAdvancedSpotUrl(coin)).toBe(
        "https://www.coinbase.com/advanced-trade/spot/BTC-USD",
      );
    },
  );

  it.each([null, undefined, {}, "", " ", "https://www.coinbase.com/advanced-trade"])(
    "does not invent a trade destination for %j",
    (coin) => expect(getCoinbaseAdvancedSpotUrl(coin)).toBeNull(),
  );
});


describe("getExternalAlertSourceUrl", () => {
  it("preserves a legitimate news link", () => {
    const url = "https://example.com/story?coin=SOL";
    expect(getExternalAlertSourceUrl(url)).toBe(url);
  });

  it.each([
    "javascript:alert(1)",
    "data:text/html,test",
    "https://www.coinbase.com?tracking=true",
    "https://coinbase.com./advanced-trade/spot/BTC",
    "https://coinbase.com@other.example/story",
  ])("does not use %s as a news destination", (value) => {
    expect(getExternalAlertSourceUrl(value)).toBeNull();
  });
});
