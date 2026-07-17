export function formatCurrency(
  value: number | null,
  currency: string
): string {
  if (value === null) return "待确认";

  try {
    return new Intl.NumberFormat("zh-CN", {
      style: "currency",
      currency,
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  } catch {
    return new Intl.NumberFormat("zh-CN", {
      maximumFractionDigits: 0,
    }).format(value);
  }
}
