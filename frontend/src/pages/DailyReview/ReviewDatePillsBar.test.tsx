import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import ReviewDatePillsBar from "./ReviewDatePillsBar";

describe("ReviewDatePillsBar", () => {
  const dates = ["2026-11-04", "2026-11-03", "2026-11-02", "2026-10-30", "2026-10-29"];

  it("renders date pills and marks current date as active", () => {
    const handleSelect = vi.fn();
    render(
      <ReviewDatePillsBar
        currentDate="2026-11-04"
        availableDates={dates}
        onSelectDate={handleSelect}
      />,
    );

    expect(screen.getByText("回看历史:")).toBeInTheDocument();
    expect(screen.getByText("11-04 (最新)")).toBeInTheDocument();
    expect(screen.getByText("11-03")).toBeInTheDocument();
    expect(screen.getByText("11-02")).toBeInTheDocument();
    // Does not show return button when on latest
    expect(screen.queryByText(/回最新/)).not.toBeInTheDocument();
  });

  it("shows return button when viewing historical date and handles click", () => {
    const handleSelect = vi.fn();
    render(
      <ReviewDatePillsBar
        currentDate="2026-11-02"
        availableDates={dates}
        onSelectDate={handleSelect}
      />,
    );

    const returnBtn = screen.getByText(/回最新/);
    expect(returnBtn).toBeInTheDocument();

    fireEvent.click(returnBtn);
    expect(handleSelect).toHaveBeenCalledWith("2026-11-04");
  });

  it("calls onSelectDate when a date pill is clicked", () => {
    const handleSelect = vi.fn();
    render(
      <ReviewDatePillsBar
        currentDate="2026-11-04"
        availableDates={dates}
        onSelectDate={handleSelect}
      />,
    );

    const pill = screen.getByText("11-03");
    fireEvent.click(pill);
    expect(handleSelect).toHaveBeenCalledWith("2026-11-03");
  });
});
