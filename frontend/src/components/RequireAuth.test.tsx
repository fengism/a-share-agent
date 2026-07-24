import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import RequireAuth from "./RequireAuth";
import { useAuthStore } from "../store/authStore";

function renderGuard() {
  return render(
    <MemoryRouter initialEntries={["/secret"]}>
      <Routes>
        <Route element={<RequireAuth />}>
          <Route path="/secret" element={<div>SECRET CONTENT</div>} />
        </Route>
        <Route path="/login" element={<div>LOGIN PAGE</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("RequireAuth", () => {
  beforeEach(() => {
    useAuthStore.setState({ user: null, bootstrapped: false });
  });

  it("shows a loading state while the token is being validated", () => {
    useAuthStore.setState({ bootstrapped: false, user: null });
    renderGuard();
    expect(screen.getByText("正在验证登录状态...")).toBeInTheDocument();
    expect(screen.queryByText("SECRET CONTENT")).toBeNull();
  });

  it("redirects to /login when unauthenticated", () => {
    useAuthStore.setState({ bootstrapped: true, user: null });
    renderGuard();
    expect(screen.getByText("LOGIN PAGE")).toBeInTheDocument();
    expect(screen.queryByText("SECRET CONTENT")).toBeNull();
  });

  it("renders the protected route when authenticated", () => {
    useAuthStore.setState({ bootstrapped: true, user: { id: 1, username: "alice", is_admin: false } });
    renderGuard();
    expect(screen.getByText("SECRET CONTENT")).toBeInTheDocument();
  });
});
