import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import BotJobManagerCard from "./BotJobManagerCard";

const mocks = vi.hoisted(() => ({
  refetch: vi.fn(),
  retry: vi.fn(),
}));

vi.mock("../../api/queries", () => ({
  useBotJobs: () => ({
    data: {
      counts: { pending: 2, running: 1, succeeded: 8, failed: 1 },
      jobs: [{
        id: "job-12345678",
        event_id: "event-1",
        platform: "feishu",
        request_user_id: "ou_admin",
        command_name: "analyze",
        status: "failed",
        attempts: 3,
        max_attempts: 3,
        last_error: "analysis timeout",
        created_at: 1_700_000_000,
        updated_at: 1_700_000_100,
        completed_at: 1_700_000_100,
      }],
    },
    isLoading: false,
    error: null,
    refetch: mocks.refetch,
    isFetching: false,
  }),
  useRetryBotJob: () => ({
    mutate: mocks.retry,
    isPending: false,
    variables: undefined,
  }),
}));

vi.mock("antd", async () => {
  const actual = await vi.importActual<typeof import("antd")>("antd");
  return {
    ...actual,
    message: {
      ...actual.message,
      error: vi.fn(),
      success: vi.fn(),
    },
  };
});

describe("BotJobManagerCard", () => {
  afterEach(() => vi.clearAllMocks());

  it("shows failed task details and retries the selected job", () => {
    mocks.retry.mockImplementation((_jobId, options) => options.onSuccess());
    render(<BotJobManagerCard />);

    expect(screen.getByText("等待 2")).toBeInTheDocument();
    expect(screen.getByText("失败 1")).toBeInTheDocument();
    expect(screen.getByText(/analysis timeout/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /重试/ }));

    expect(mocks.retry).toHaveBeenCalledWith("job-12345678", expect.objectContaining({
      onSuccess: expect.any(Function),
      onError: expect.any(Function),
    }));
    expect(mocks.refetch).toHaveBeenCalledTimes(1);
  });
});
