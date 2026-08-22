const SHANGHAI_TIMEZONE = "Asia/Shanghai";
const SHANGHAI_UTC_OFFSET_MINUTES = 8 * 60;
const MINUTE_MS = 60 * 1000;
const DAY_MS = 24 * 60 * MINUTE_MS;

const SESSION_RANGES = [
  { start: 9 * 60 + 15, end: 11 * 60 + 30 },
  { start: 13 * 60, end: 15 * 60 + 10 },
] as const;

const SESSION_BOUNDARIES = [
  SESSION_RANGES[0].start,
  SESSION_RANGES[0].end + 1,
  SESSION_RANGES[1].start,
  SESSION_RANGES[1].end + 1,
] as const;

const shanghaiClockFormatter = new Intl.DateTimeFormat("en-US", {
  timeZone: SHANGHAI_TIMEZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  weekday: "short",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

interface ShanghaiClock {
  year: number;
  month: number;
  day: number;
  weekday: string;
  minutes: number;
}

function getShanghaiClock(now: Date): ShanghaiClock {
  const values = Object.fromEntries(
    shanghaiClockFormatter
      .formatToParts(now)
      .filter((part) => part.type !== "literal")
      .map((part) => [part.type, part.value]),
  );
  const hour = Number(values.hour);
  const minute = Number(values.minute);
  return {
    year: Number(values.year),
    month: Number(values.month),
    day: Number(values.day),
    weekday: values.weekday,
    minutes: hour * 60 + minute,
  };
}

function isWeekday(weekday: string) {
  return weekday !== "Sat" && weekday !== "Sun";
}

export function isAStockAutoRefreshTime(now = new Date()) {
  const clock = getShanghaiClock(now);
  return isWeekday(clock.weekday) && SESSION_RANGES.some(
    ({ start, end }) => clock.minutes >= start && clock.minutes <= end,
  );
}

export function millisecondsUntilNextAStockSessionBoundary(now = new Date()) {
  const clock = getShanghaiClock(now);
  const currentDateEpoch = Date.UTC(clock.year, clock.month - 1, clock.day);
  const currentEpoch = now.getTime();

  for (let dayOffset = 0; dayOffset <= 7; dayOffset += 1) {
    const candidateDate = new Date(currentDateEpoch + dayOffset * DAY_MS);
    const weekday = candidateDate.getUTCDay();
    if (weekday === 0 || weekday === 6) continue;

    for (const boundaryMinutes of SESSION_BOUNDARIES) {
      const boundaryEpoch = candidateDate.getTime()
        + (boundaryMinutes - SHANGHAI_UTC_OFFSET_MINUTES) * MINUTE_MS;
      if (boundaryEpoch > currentEpoch) return boundaryEpoch - currentEpoch;
    }
  }

  return DAY_MS;
}
