import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ContactValue } from "./ContactValue";

describe("ContactValue", () => {
  it("shows verified emails with a Verified badge", () => {
    render(<ContactValue value="a@b.example" status="verified" kind="email" />);

    expect(screen.getByRole("link", { name: "a@b.example" })).toHaveAttribute("href", "mailto:a@b.example");
    expect(screen.getByText("Verified")).toBeInTheDocument();
  });

  it("labels unverified values distinctly", () => {
    render(<ContactValue value="+1 410-555-0100" status="unverified" kind="phone" />);

    expect(screen.getByRole("link")).toHaveAttribute("href", "tel:+14105550100");
    expect(screen.getByText("Unverified")).toBeInTheDocument();
  });

  it("does not claim a status the provider did not give", () => {
    render(<ContactValue value="a@b.example" status="unknown" kind="email" />);

    expect(screen.queryByText("Verified")).not.toBeInTheDocument();
    expect(screen.getByText("Not stated")).toBeInTheDocument();
  });

  it("shows Not available instead of inventing a value", () => {
    render(<ContactValue value={null} status="unavailable" kind="email" />);

    expect(screen.getByText("Not available")).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
});
