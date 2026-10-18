import { describe, expect, it } from "vitest";
import source from "./tokens.json";
import { collectTokens, renderFigmaManifest, renderTokenCss } from "../../scripts/designTokens.mjs";

describe("design token pipeline", () => {
  it("keeps semantic aliases in both platform outputs", () => {
    expect(renderTokenCss(source)).toContain("--signal-positive: var(--color-amber)");
    const manifest = JSON.parse(renderFigmaManifest(source));
    const token = manifest.variables.find((entry) => entry.name === "color/semantic/positive");
    expect(token.alias).toBe("color/primitive/amber");
    expect(token.codeSyntax.WEB).toBe("var(--signal-positive)");
    expect(manifest.variables.every((entry) => entry.collection)).toBe(true);
  });

  it("converts rem dimensions to Figma pixels without changing CSS units", () => {
    const manifest = JSON.parse(renderFigmaManifest(source));
    expect(manifest.variables.find((entry) => entry.name === "typography/size/3xl").value).toBe(33.6);
    expect(renderTokenCss(source)).toContain("--text-3xl: 2.1rem");
  });

  it("rejects circular and missing aliases before generating either output", () => {
    expect(() => renderTokenCss({ $type: "number", a: { $value: "{b}" }, b: { $value: "{a}" } })).toThrow("Circular");
    expect(() => renderFigmaManifest({ $type: "number", a: { $value: "{missing}" } })).toThrow("Missing");
  });

  it("rejects duplicate CSS mappings", () => {
    const token = { $value: 1, $extensions: { "com.moonwalking.cssVariable": "--same" } };
    expect(() => renderTokenCss({ $type: "number", a: token, b: token })).toThrow("Duplicate");
  });

  it("gives every source token a resolved type", () => {
    expect([...collectTokens(source).values()].every((token) => token.$type)).toBe(true);
  });
});
