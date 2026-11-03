import type { SearchCriteria } from "./types";

export const LIMITS = {
  listItems: 10,
  shortText: 100,
  keyword: 50,
  companyName: 200,
  maxEmployees: 10_000_000,
} as const;

export interface SearchFormValues {
  industry: string;
  jobTitles: string;
  locations: string;
  employeeMin: string;
  employeeMax: string;
  keywords: string;
  companyName: string;
  fullName: string;
  firstName: string;
  lastName: string;
  email: string;
  phone: string;
  providerFilters: Record<string, boolean>;
}

export const EMPTY_FORM: SearchFormValues = {
  industry: "",
  jobTitles: "",
  locations: "",
  employeeMin: "",
  employeeMax: "",
  keywords: "",
  companyName: "",
  fullName: "",
  firstName: "",
  lastName: "",
  email: "",
  phone: "",
  providerFilters: {},
};

// Titles and keywords are comma-separated. Locations use semicolons because
// place names such as "Washington, D.C." contain commas.
const COMMA_LIST = /[,;\n]/;
const LOCATION_LIST = /[;\n]/;

export function parseList(input: string, separator: RegExp = COMMA_LIST): string[] {
  const seen = new Set<string>();
  const items: string[] = [];
  for (const raw of input.split(separator)) {
    const item = raw.trim();
    if (item && !seen.has(item.toLowerCase())) {
      seen.add(item.toLowerCase());
      items.push(item);
    }
  }
  return items;
}

function parseCount(label: string, value: string, errors: string[]): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  if (!/^\d+$/.test(trimmed)) {
    errors.push(`${label} must be a whole number`);
    return null;
  }
  const n = Number(trimmed);
  if (n < 1 || n > LIMITS.maxEmployees) {
    errors.push(`${label} must be between 1 and ${LIMITS.maxEmployees.toLocaleString()}`);
    return null;
  }
  return n;
}

function optionalText(label: string, value: string, maxLength: number, errors: string[]): string | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  if (trimmed.length > maxLength) {
    errors.push(`${label} must be ${maxLength} characters or fewer`);
    return null;
  }
  return trimmed;
}

function checkList(label: string, items: string[], maxLength: number, errors: string[]): void {
  if (items.length > LIMITS.listItems) errors.push(`${label}: enter at most ${LIMITS.listItems} values`);
  if (items.some((i) => i.length > maxLength)) errors.push(`${label}: each value must be ${maxLength} characters or fewer`);
}

export function buildCriteria(values: SearchFormValues): { criteria: SearchCriteria; errors: string[] } {
  const errors: string[] = [];
  const industry = values.industry.trim();
  const companyName = values.companyName.trim();
  const jobTitles = parseList(values.jobTitles);
  const locations = parseList(values.locations, LOCATION_LIST);
  const keywords = parseList(values.keywords);

  if (industry.length > LIMITS.shortText) errors.push(`Industry must be ${LIMITS.shortText} characters or fewer`);
  if (companyName.length > LIMITS.companyName) {
    errors.push(`Company name must be ${LIMITS.companyName} characters or fewer`);
  }
  checkList("Job titles", jobTitles, LIMITS.shortText, errors);
  checkList("Locations", locations, LIMITS.shortText, errors);
  checkList("Keywords", keywords, LIMITS.keyword, errors);

  const fullName = optionalText("Full name", values.fullName, LIMITS.companyName, errors);
  const firstName = optionalText("First name", values.firstName, LIMITS.shortText, errors);
  const lastName = optionalText("Last name", values.lastName, LIMITS.shortText, errors);
  const email = optionalText("Email address", values.email, 320, errors);
  const phone = optionalText("Phone number", values.phone, 50, errors);
  if (phone && !/\d/.test(phone)) errors.push("Phone number must include digits");

  const employeeMin = parseCount("Minimum employees", values.employeeMin, errors);
  const employeeMax = parseCount("Maximum employees", values.employeeMax, errors);
  if (employeeMin !== null && employeeMax !== null && employeeMin > employeeMax) {
    errors.push("Minimum employees must be less than or equal to maximum employees");
  }

  const providerFilters = Object.fromEntries(Object.entries(values.providerFilters).filter(([, on]) => on));

  const criteria: SearchCriteria = {
    industry: industry || null,
    job_titles: jobTitles,
    locations: locations,
    employee_min: employeeMin,
    employee_max: employeeMax,
    keywords,
    company_name: companyName || null,
    full_name: fullName,
    first_name: firstName,
    last_name: lastName,
    email,
    phone,
    provider_filters: providerFilters,
  };

  const hasCriterion =
    !!industry || jobTitles.length > 0 || locations.length > 0 || employeeMin !== null ||
    employeeMax !== null || keywords.length > 0 || !!companyName ||
    !!fullName || !!firstName || !!lastName || !!email || !!phone;
  if (!hasCriterion && errors.length === 0) errors.push("Enter at least one search criterion");

  return { criteria, errors };
}

export function criteriaToForm(criteria: SearchCriteria): SearchFormValues {
  const filters: Record<string, boolean> = {};
  for (const [key, value] of Object.entries(criteria.provider_filters ?? {})) {
    if (typeof value === "boolean") filters[key] = value;
  }
  return {
    industry: criteria.industry ?? "",
    jobTitles: (criteria.job_titles ?? []).join(", "),
    locations: (criteria.locations ?? []).join("; "),
    employeeMin: criteria.employee_min ? String(criteria.employee_min) : "",
    employeeMax: criteria.employee_max ? String(criteria.employee_max) : "",
    keywords: (criteria.keywords ?? []).join(", "),
    companyName: criteria.company_name ?? "",
    fullName: criteria.full_name ?? "",
    firstName: criteria.first_name ?? "",
    lastName: criteria.last_name ?? "",
    email: criteria.email ?? "",
    phone: criteria.phone ?? "",
    providerFilters: filters,
  };
}

export function describeCriteria(criteria: SearchCriteria): string {
  const parts: string[] = [];
  if (criteria.industry) parts.push(criteria.industry);
  if (criteria.job_titles?.length) parts.push(criteria.job_titles.join(", "));
  if (criteria.locations?.length) parts.push(criteria.locations.join("; "));
  if (criteria.employee_min || criteria.employee_max) {
    const min = criteria.employee_min?.toLocaleString() ?? "any";
    const max = criteria.employee_max?.toLocaleString() ?? "any";
    parts.push(`${min}–${max} employees`);
  }
  if (criteria.keywords?.length) parts.push(`keywords: ${criteria.keywords.join(", ")}`);
  if (criteria.company_name) parts.push(`company: ${criteria.company_name}`);
  if (criteria.full_name) parts.push(`name: ${criteria.full_name}`);
  if (criteria.first_name) parts.push(`first name: ${criteria.first_name}`);
  if (criteria.last_name) parts.push(`last name: ${criteria.last_name}`);
  if (criteria.email) parts.push(`email: ${criteria.email}`);
  if (criteria.phone) parts.push(`phone: ${criteria.phone}`);
  return parts.join(" · ") || "(no criteria)";
}
