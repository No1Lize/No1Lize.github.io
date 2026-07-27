export type ChannelUpdateDatePrecision = "exact" | "approximate" | "undated";

export type NormalizedChannelUpdateDate = {
  displayDate: string;
  originalDate: string;
  precision: ChannelUpdateDatePrecision;
  sortAt: string;
};

export const UNDATED_CHANNEL_UPDATE_SORT_AT = "0000-01-01T00:00:00.000Z";

const ONGOING_DATE_MARKERS = new Set([
  "持续更新",
  "长期更新",
  "ongoing",
  "updated regularly",
]);

function validDate(value: Date) {
  return !Number.isNaN(value.getTime());
}

function referenceDate(value: string) {
  const parsed = new Date(value);
  return validDate(parsed) ? parsed : new Date("1970-01-01T00:00:00.000Z");
}

function daysInUtcMonth(year: number, month: number) {
  return new Date(Date.UTC(year, month + 1, 0)).getUTCDate();
}

function subtractUtcMonths(value: Date, months: number) {
  const totalMonths = value.getUTCFullYear() * 12 + value.getUTCMonth() - months;
  const year = Math.floor(totalMonths / 12);
  const month = ((totalMonths % 12) + 12) % 12;
  const day = Math.min(value.getUTCDate(), daysInUtcMonth(year, month));
  return new Date(
    Date.UTC(
      year,
      month,
      day,
      value.getUTCHours(),
      value.getUTCMinutes(),
      value.getUTCSeconds(),
      value.getUTCMilliseconds(),
    ),
  );
}

function subtractUtcYears(value: Date, years: number) {
  return subtractUtcMonths(value, years * 12);
}

function exactDateFromText(value: string) {
  const calendarMatch = value.match(
    /^(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})(?:日)?(?:[ T].*)?$/u,
  );
  if (calendarMatch) {
    const year = Number(calendarMatch[1]);
    const month = Number(calendarMatch[2]);
    const day = Number(calendarMatch[3]);
    const parsed = new Date(Date.UTC(year, month - 1, day));
    if (
      parsed.getUTCFullYear() === year &&
      parsed.getUTCMonth() === month - 1 &&
      parsed.getUTCDate() === day
    ) {
      return parsed;
    }
  }

  if (/^\d{4}-\d{2}-\d{2}T/u.test(value)) {
    const parsed = new Date(value);
    if (validDate(parsed)) return parsed;
  }

  return null;
}

function relativeDateFromText(value: string, anchor: Date) {
  if (value === "刚刚" || value === "今天") return anchor;
  if (value === "昨天") return new Date(anchor.getTime() - 24 * 60 * 60 * 1000);
  if (value === "前天") return new Date(anchor.getTime() - 2 * 24 * 60 * 60 * 1000);

  const chineseMatch = value.match(
    /^(\d+)\s*(年|个月|月|周|星期|天|小时|分钟|秒)前$/u,
  );
  if (chineseMatch) {
    const amount = Number(chineseMatch[1]);
    const unit = chineseMatch[2];
    if (unit === "年") return subtractUtcYears(anchor, amount);
    if (unit === "个月" || unit === "月") return subtractUtcMonths(anchor, amount);
    const milliseconds =
      unit === "周" || unit === "星期"
        ? amount * 7 * 24 * 60 * 60 * 1000
        : unit === "天"
          ? amount * 24 * 60 * 60 * 1000
          : unit === "小时"
            ? amount * 60 * 60 * 1000
            : unit === "分钟"
              ? amount * 60 * 1000
              : amount * 1000;
    return new Date(anchor.getTime() - milliseconds);
  }

  const englishMatch = value.match(
    /^(\d+)\s*(year|month|week|day|hour|minute|second)s?\s+ago$/iu,
  );
  if (englishMatch) {
    const amount = Number(englishMatch[1]);
    const unit = englishMatch[2].toLocaleLowerCase("en-US");
    if (unit === "year") return subtractUtcYears(anchor, amount);
    if (unit === "month") return subtractUtcMonths(anchor, amount);
    const milliseconds =
      unit === "week"
        ? amount * 7 * 24 * 60 * 60 * 1000
        : unit === "day"
          ? amount * 24 * 60 * 60 * 1000
          : unit === "hour"
            ? amount * 60 * 60 * 1000
            : unit === "minute"
              ? amount * 60 * 1000
              : amount * 1000;
    return new Date(anchor.getTime() - milliseconds);
  }

  return null;
}

export function normalizeChannelUpdateDate(
  rawValue: string | undefined,
  referenceValue: string,
): NormalizedChannelUpdateDate {
  const originalDate = String(rawValue || "").trim();
  const normalizedMarker = originalDate.toLocaleLowerCase("en-US");

  if (!originalDate || ONGOING_DATE_MARKERS.has(normalizedMarker)) {
    return {
      displayDate: originalDate || "日期未标明",
      originalDate,
      precision: "undated",
      sortAt: UNDATED_CHANNEL_UPDATE_SORT_AT,
    };
  }

  const exact = exactDateFromText(originalDate);
  if (exact) {
    return {
      displayDate: exact.toISOString().slice(0, 10),
      originalDate,
      precision: "exact",
      sortAt: exact.toISOString(),
    };
  }

  const relative = relativeDateFromText(originalDate, referenceDate(referenceValue));
  if (relative && validDate(relative)) {
    return {
      displayDate: `约 ${relative.toISOString().slice(0, 10)}`,
      originalDate,
      precision: "approximate",
      sortAt: relative.toISOString(),
    };
  }

  return {
    displayDate: "日期未标明",
    originalDate,
    precision: "undated",
    sortAt: UNDATED_CHANNEL_UPDATE_SORT_AT,
  };
}
