export function formatPkr(amount: number): string {
  return new Intl.NumberFormat("en-PK", {
    style: "currency",
    currency: "PKR",
    maximumFractionDigits: 0,
  }).format(amount);
}

/** Formats an amount in whatever currency the deployment's reporting currency
 * actually is (e.g. "USD", "AED"), instead of assuming PKR. Falls back to a
 * plain PKR format if a currency code isn't available yet (e.g. while the
 * /system/config request is still loading). */
export function formatCurrencyAmount(amount: number, currencyCode: string | null | undefined): string {
  if (!currencyCode) return formatPkr(amount);
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: currencyCode,
      maximumFractionDigits: 0,
    }).format(amount);
  } catch {
    // Unknown/invalid ISO code -- don't crash the page over a display format.
    return formatPkr(amount);
  }
}

export function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export function formatPercentValue(value: number): string {
  return `${value.toFixed(1)}%`;
}

export function formatCount(value: number): string {
  return new Intl.NumberFormat("en-PK").format(Math.round(value));
}

export function formatKpiValue(value: number, unit: string, currency: string | null): string {
  switch (unit) {
    case "currency":
      return currency ? formatCurrencyAmount(value, currency) : formatCount(value);
    case "percentage":
      return formatPercentValue(value);
    case "count":
    case "quantity":
      return formatCount(value);
    case "days":
      return `${value.toFixed(1)} days`;
    case "hours":
      return `${formatCount(value)} hrs`;
    default:
      return formatCount(value);
  }
}

export function formatSigned(value: number, formatter: (v: number) => string): string {
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  return `${sign}${formatter(Math.abs(value))}`;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value.toFixed(1)} ${units[unitIndex]}`;
}
