import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { UiButton, UiCard, UiCheckbox, UiField } from "./DesignSystem.jsx";

describe("Moonwalking design system primitives", () => {
  it("renders a native button with stable variant and loading states", () => {
    render(<UiButton variant="primary" loading>Save</UiButton>);
    const button = screen.getByRole("button", { name: "Save" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
    expect(button).toHaveClass("ui-button--primary");
  });

  it("associates field labels, hints, and errors with the control", () => {
    render(<UiField label="Email" hint="Account email" error="Required" />);
    const input = screen.getByLabelText("Email");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input.getAttribute("aria-describedby")).toContain("hint");
    expect(input.getAttribute("aria-describedby")).toContain("error");
  });

  it("forwards checkbox changes through the labeled control", () => {
    const onChange = vi.fn();
    render(<UiCheckbox label="Remember this device" onChange={onChange} />);
    fireEvent.click(screen.getByLabelText("Remember this device"));
    expect(onChange).toHaveBeenCalledOnce();
  });

  it("renders semantic card elements without forcing nested cards", () => {
    render(<UiCard as="article"><h2>Market context</h2></UiCard>);
    expect(screen.getByRole("article")).toHaveClass("ui-card--default");
  });

  it("blocks disabled links and forwards clicks for active links", () => {
    const onClick = vi.fn();
    const { rerender } = render(<UiButton as="a" href="#target" disabled onClick={onClick}>Open</UiButton>);
    fireEvent.click(screen.getByRole("link", { name: "Open" }));
    expect(onClick).not.toHaveBeenCalled();
    expect(screen.getByRole("link")).toHaveAttribute("aria-disabled", "true");
    rerender(<UiButton as="a" href="#target" onClick={onClick}>Open</UiButton>);
    fireEvent.click(screen.getByRole("link", { name: "Open" }));
    expect(onClick).toHaveBeenCalledOnce();
  });
});
