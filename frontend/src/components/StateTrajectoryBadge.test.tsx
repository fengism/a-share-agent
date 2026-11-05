import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import StateTrajectoryBadge, { deriveTrajectory } from "./StateTrajectoryBadge";

describe("StateTrajectoryBadge", () => {
  it("derives trajectory from signalTypes accurately", () => {
    const breakout = deriveTrajectory(["breakout"]);
    expect(breakout.from).toBe("箱体蓄势");
    expect(breakout.to).toBe("顺势突破");

    const pullback = deriveTrajectory(["pullback"]);
    expect(pullback.from).toBe("缩量回探");
    expect(pullback.to).toBe("支撑企稳");

    const reversal = deriveTrajectory(["reversal"]);
    expect(reversal.from).toBe("超跌探底");
    expect(reversal.to).toBe("底部企稳");
  });

  it("renders trajectory badge with arrow", () => {
    render(<StateTrajectoryBadge fromState="箱体蓄势" toState="顺势突破" />);

    expect(screen.getByText("箱体蓄势")).toBeInTheDocument();
    expect(screen.getByText("顺势突破")).toBeInTheDocument();
    expect(screen.getByText("➔")).toBeInTheDocument();
  });

  it("parses combined trajectory string", () => {
    render(<StateTrajectoryBadge trajectory="均线粘合 ➔ 临界蓄势" />);

    expect(screen.getByText("均线粘合")).toBeInTheDocument();
    expect(screen.getByText("临界蓄势")).toBeInTheDocument();
  });
});
