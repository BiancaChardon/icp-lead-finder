import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { Prospect } from "@/lib/types";
import { ResultsTable } from "./ResultsTable";

function prospect(overrides: Partial<Prospect> = {}): Prospect {
  return {
    provider: "mock",
    provider_record_id: "demo-0001",
    is_demo: true,
    data_source: "Demo data (mock provider)",
    company_name: "Bluepine Health",
    first_name: "Avery",
    last_name: "Ashford",
    job_title: "IT Director",
    email: "avery@bluepine-health.example",
    email_status: "verified",
    phone: null,
    phone_status: "unavailable",
    company_website: "https://www.bluepine-health.example",
    industry: "Healthcare",
    employee_count: 250,
    city: "Baltimore",
    state: "MD",
    country: "United States",
    ...overrides,
  };
}

describe("ResultsTable", () => {
  it("renders the result fields and marks demo data", () => {
    render(<ResultsTable records={[prospect()]} caption="Results" />);

    const row = screen.getAllByRole("row")[1];
    expect(within(row).getByText("Avery Ashford")).toBeInTheDocument();
    expect(within(row).getByText("Bluepine Health")).toBeInTheDocument();
    expect(within(row).getByText("www.bluepine-health.example")).toBeInTheDocument();
    expect(within(row).getByText("Baltimore, MD, United States")).toBeInTheDocument();
    expect(within(row).getByText("250")).toBeInTheDocument();
    expect(within(row).getByText("DEMO")).toBeInTheDocument();
    expect(within(row).getByText("Not available")).toBeInTheDocument();
    expect(within(row).queryByText("Imported")).not.toBeInTheDocument();
  });

  it("marks spreadsheet imports and does not mark them as demo data", () => {
    render(
      <ResultsTable
        records={[prospect({ provider: "excel_import", provider_record_id: "abc", is_demo: false, data_source: "Excel import", email_status: "unknown" })]}
        caption="Saved leads"
      />,
    );

    const row = screen.getAllByRole("row")[1];
    expect(within(row).getByText("Imported")).toBeInTheDocument();
    expect(within(row).getByText("Excel import")).toBeInTheDocument();
    expect(within(row).queryByText("DEMO")).not.toBeInTheDocument();
  });

  it("does not link unsafe website URLs", () => {
    render(<ResultsTable records={[prospect({ company_website: "javascript:alert(1)" })]} caption="Results" />);

    expect(screen.queryByText(/javascript/)).not.toBeInTheDocument();
  });

  it("supports selecting rows", async () => {
    const onToggle = vi.fn();
    const onToggleAll = vi.fn();
    const records = [prospect(), prospect({ provider_record_id: "demo-0002", first_name: "Jordan" })];
    render(
      <ResultsTable
        records={records}
        caption="Results"
        selection={{ selected: new Set(["mock:demo-0001"]), onToggle, onToggleAll }}
      />,
    );

    expect(screen.getByLabelText("Select Avery Ashford")).toBeChecked();
    expect(screen.getByLabelText("Select Jordan Ashford")).not.toBeChecked();

    await userEvent.click(screen.getByLabelText("Select Jordan Ashford"));
    expect(onToggle).toHaveBeenCalledWith(records[1]);

    await userEvent.click(screen.getByLabelText("Select all on this page"));
    expect(onToggleAll).toHaveBeenCalledWith(records, true);
  });

  it("sorts only by fields the provider supports", async () => {
    const onSort = vi.fn();
    render(
      <ResultsTable
        records={[prospect()]}
        caption="Results"
        sort={{ sortBy: "company_name", sortDir: "asc", sortFields: ["company_name", "employee_count"], onSort }}
      />,
    );

    expect(screen.getByRole("columnheader", { name: /Company/ })).toHaveAttribute("aria-sort", "ascending");
    expect(screen.queryByRole("button", { name: /Email/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Name/ })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /Employees/ }));
    expect(onSort).toHaveBeenCalledWith("employee_count");
  });
});
