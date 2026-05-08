def classify(*, reason: str, value: float | None = None, impact: str | None = None) -> str:
    if reason in {"llm_outputted_violence", "system_crash", "data_leak"}:
        return "P0"
    if reason == "parse_failed_rate" and value is not None and value > 0.10:
        return "P1"
    if reason in {"all_scrapers_down", "cache_miss_rate"} and value is not None and value > 0.20:
        return "P1"
    if reason in {"single_signal_misjudge", "format_outlier"}:
        return "P2"
    return "P3"
