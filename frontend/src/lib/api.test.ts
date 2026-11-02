import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiJson, navigation } from "./api";

function mockFetch(response: Response) {
  const fetchMock = vi.fn().mockResolvedValue(response);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function headersOf(fetchMock: ReturnType<typeof vi.fn>): Record<string, string> {
  return fetchMock.mock.calls[0][1].headers as Record<string, string>;
}

beforeEach(() => {
  document.cookie = "ilf_csrf=csrf-123; path=/";
});

describe("apiJson", () => {
  it("sends the CSRF token on state-changing requests", async () => {
    const fetchMock = mockFetch(new Response(JSON.stringify({ ok: true }), { status: 200 }));

    await apiJson("/api/leads", { method: "POST", body: { leads: [] } });

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/leads");
    expect(init.credentials).toBe("same-origin");
    expect(init.body).toBe(JSON.stringify({ leads: [] }));
    expect(headersOf(fetchMock)["X-CSRF-Token"]).toBe("csrf-123");
    expect(headersOf(fetchMock)["Content-Type"]).toBe("application/json");
  });

  it("does not send the CSRF token on GET requests", async () => {
    const fetchMock = mockFetch(new Response("{}", { status: 200 }));

    await apiJson("/api/leads");

    expect(headersOf(fetchMock)["X-CSRF-Token"]).toBeUndefined();
  });

  it("surfaces the backend error message", async () => {
    mockFetch(new Response(JSON.stringify({ detail: "Invalid email or password" }), { status: 401 }));

    await expect(apiJson("/api/auth/login", { method: "POST", body: {} })).rejects.toEqual(
      new ApiError(401, "Invalid email or password"),
    );
  });

  it("joins validation errors into one message", async () => {
    const detail = [{ msg: "Value error, Enter at least one search criterion" }, { msg: "Field required" }];
    mockFetch(new Response(JSON.stringify({ detail }), { status: 422 }));

    await expect(apiJson("/api/search", { method: "POST", body: {} })).rejects.toThrow(
      "Enter at least one search criterion; Field required",
    );
  });

  it("redirects to the login page when the session has expired", async () => {
    const toLogin = vi.spyOn(navigation, "toLogin").mockImplementation(() => {});
    mockFetch(new Response(JSON.stringify({ detail: "Not authenticated" }), { status: 401 }));

    await expect(apiJson("/api/leads")).rejects.toBeInstanceOf(ApiError);
    expect(toLogin).toHaveBeenCalledOnce();
  });
});
