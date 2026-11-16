import { describe, expect, it } from "vitest";
import coinbaseSpotUrl, { getCoinbaseAdvancedSpotUrl } from "./coinbaseUrl";

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
