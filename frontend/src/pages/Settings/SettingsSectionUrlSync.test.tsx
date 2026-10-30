import { render, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import SettingsSectionUrlSync from "./SettingsSectionUrlSync";
import type { SettingsSectionKey } from "./settingsSections";

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="search">{location.search}</output>;
}

function renderSync(initialEntry: string, section: SettingsSectionKey, onChange = vi.fn()) {
  render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route
          path="*"
          element={(
            <>
              <SettingsSectionUrlSync section={section} onChange={onChange} />
              <LocationProbe />
            </>
          )}
        />
      </Routes>
    </MemoryRouter>,
  );
  return { onChange };
}

describe("SettingsSectionUrlSync", () => {
  it("restores the section from the URL on first mount", async () => {
    const { onChange } = renderSync("/settings?section=admin", "account");

    await waitFor(() => expect(onChange).toHaveBeenCalledWith("admin"));
  });

  it("ignores unknown or missing section values", async () => {
    const { onChange } = renderSync("/settings?section=not-a-section", "account");

    await waitFor(() => expect(onChange).not.toHaveBeenCalled());
  });

  it("writes the active section back into the URL", async () => {
    renderSync("/settings", "ai");

    await waitFor(() => expect(screen().search).toBe("?section=ai"));
  });

  it("keeps the default section out of the URL", async () => {
    renderSync("/settings?section=ai", "account");

    await waitFor(() => expect(screen().search).toBe(""));
  });
});

function screen() {
  const node = document.querySelector("[data-testid='search']");
  return { search: node?.textContent ?? "" };
}
