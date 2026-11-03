# Contact-data providers

The backend talks to contact-data sources through one provider-neutral interface
(`backend/app/providers/base.py`). The frontend never talks to a provider and never sees
provider credentials; it only calls this application's `/api/search` endpoint.

## Current status

| Provider | Status |
|----------|--------|
| `mock` | Implemented. Fictional demonstration data, marked `is_demo` and shown with a **DEMO** badge. Emails use the reserved `.example` domain and phones the reserved 555-01xx range. |
| Apollo.io | **Not implemented.** Selecting it fails at startup. |
| Hunter.io | **Not implemented.** |

No real-provider search has been implemented or tested yet. Do not describe results as real
contact data until a real provider is implemented, configured, and tested.

## The interface

A provider subclasses `ProspectProvider` and implements one method:

```python
class MyProvider(ProspectProvider):
    name = "myprovider"                 # value of CONTACT_PROVIDER
    display_name = "My Provider"
    is_demo = False
    sort_fields = ("company_name",)    # only fields the provider can sort server-side
    filters = ()                       # optional provider-specific filters (shown in the UI)
    contact_search_fields = ()         # subset of first_name, last_name, email, phone

    def search(self, query: ProspectQuery) -> ProspectPage: ...
```

Rules for implementations:

- Return `Prospect` objects containing **only data the provider returned**. Leave unknown fields `None`.
- Set `email_status` / `phone_status` to `verified` or `unverified` **only** when the provider states it;
  otherwise use `unknown`. Missing values automatically become `unavailable`.
- Raise `ProviderRateLimitedError` on provider rate limits (HTTP 429), `ProviderNotConfiguredError` when
  credentials are missing, and `ProviderError` for other failures. Never include credentials in exception
  messages; the API shows users a generic message and logs only the error type.
- Read credentials from environment variables (e.g. `APOLLO_API_KEY` in `.env`) via `app/config.py`.
  Never hard-code them or send them to the frontend.
- Use official APIs only. Do not scrape websites or bypass access controls. Respect the provider's
  rate limits, licensing terms, and permitted uses of contact data.
- Set `contact_search_fields` only for criteria the provider can actually filter. The API rejects a
  first name, last name, email, or phone search that is not in that list. Do not drop unsupported
  contact criteria and return company-only results. Imported spreadsheets are searched separately
  from `saved_leads`, which already stores those four columns.

The mock provider includes all four contact fields because its generated records contain them.
Apollo.io and Hunter.io are not implemented, so they are not searched.

Register the provider in `build_provider()` in `backend/app/providers/__init__.py`, add tests with
mocked HTTP responses (no real API calls in tests), then set `CONTACT_PROVIDER=<name>`.

## Notes for Apollo.io (to verify against current documentation before building)

From the planning discussion, Apollo's people-search endpoint can find prospects without consuming
credits but does not return email addresses or phone numbers; retrieving those requires enrichment
calls that can consume credits. To control cost, a likely design is:

1. `search()` uses people search to list matching prospects (no emails/phones yet, so they show as
   "Not available").
2. A separate, explicit "Reveal contact details" action enriches only the leads a user selects,
   with per-user limits and an audit event per enrichment.

Before implementing, confirm current API access for your plan, pricing, rate limits, and data-use
terms, and test with a small number of credits.
