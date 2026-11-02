import type { ContactStatus } from "@/lib/types";

const STATUS_LABELS: Record<Exclude<ContactStatus, "unavailable">, string> = {
  verified: "Verified",
  unverified: "Unverified",
  unknown: "Not stated",
};

interface Props {
  value: string | null;
  status: ContactStatus;
  kind: "email" | "phone";
}

/** Shows a contact detail with the verification status the provider reported, never an invented one. */
export function ContactValue({ value, status, kind }: Props) {
  if (!value || status === "unavailable") {
    return <span className="contact-unavailable">Not available</span>;
  }
  const href = kind === "email" ? `mailto:${value}` : `tel:${value.replace(/[^\d+]/g, "")}`;
  return (
    <span className="contact-value">
      <a href={href}>{value}</a>
      <span className={`status-badge status-${status}`} title={`Provider status: ${STATUS_LABELS[status]}`}>
        {STATUS_LABELS[status]}
      </span>
    </span>
  );
}
