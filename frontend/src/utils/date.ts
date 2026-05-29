import dayjs from "dayjs";

export function oneYearAgoDate() {
  return dayjs().subtract(1, "year").format("YYYYMMDD");
}
