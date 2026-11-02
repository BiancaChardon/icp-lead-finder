import { describe, expect, it } from "vitest";
import { EMPTY_FORM, buildCriteria, criteriaToForm, describeCriteria, parseList } from "./criteria";

describe("parseList", () => {
  it("splits, trims, and de-duplicates case-insensitively", () => {
    expect(parseList(" CIO, cto ,, CIO ;IT Director\n")).toEqual(["CIO", "cto", "IT Director"]);
  });
});

describe("buildCriteria", () => {
  it("builds the example ICP, keeping commas inside locations", () => {
    const { criteria, errors } = buildCriteria({
      ...EMPTY_FORM,
      industry: " Healthcare ",
      jobTitles: "CIO, CTO, IT Director",
      locations: "Maryland; Virginia; Washington, D.C.",
      employeeMin: "100",
      employeeMax: "1000",
      providerFilters: { verified_email_only: true, other: false },
    });

    expect(errors).toEqual([]);
    expect(criteria).toEqual({
      industry: "Healthcare",
      job_titles: ["CIO", "CTO", "IT Director"],
      locations: ["Maryland", "Virginia", "Washington, D.C."],
      employee_min: 100,
      employee_max: 1000,
      keywords: [],
      company_name: null,
      provider_filters: { verified_email_only: true },
    });
  });

  it("requires at least one criterion", () => {
    expect(buildCriteria(EMPTY_FORM).errors).toEqual(["Enter at least one search criterion"]);
  });

  it.each([
    [{ employeeMin: "abc" }, "Minimum employees must be a whole number"],
    [{ employeeMin: "0" }, "Minimum employees must be between 1"],
    [{ employeeMin: "500", employeeMax: "100" }, "Minimum employees must be less than or equal"],
    [{ jobTitles: Array.from({ length: 11 }, (_, i) => `t${i}`).join(",") }, "Job titles: enter at most 10"],
    [{ keywords: "k".repeat(51) }, "Keywords: each value must be 50"],
    [{ industry: "x".repeat(101) }, "Industry must be 100"],
  ])("rejects invalid input %o", (overrides, message) => {
    const { errors } = buildCriteria({ ...EMPTY_FORM, industry: "Healthcare", ...overrides });
    expect(errors.some((e) => e.startsWith(message))).toBe(true);
  });

  it("round-trips through criteriaToForm", () => {
    const original = buildCriteria({
      ...EMPTY_FORM,
      jobTitles: "CIO, CTO",
      locations: "Washington, D.C.; Maryland",
      keywords: "automation",
    }).criteria;

    expect(buildCriteria(criteriaToForm(original)).criteria).toEqual(original);
  });
});

describe("describeCriteria", () => {
  it("summarizes criteria for the history page", () => {
    const text = describeCriteria({
      industry: "Healthcare",
      job_titles: ["CIO"],
      locations: ["Maryland"],
      employee_min: 100,
      employee_max: null,
      keywords: [],
      provider_filters: {},
    });
    expect(text).toBe("Healthcare · CIO · Maryland · 100–any employees");
  });
});
