import re

SUFFIXES = {
    "k": 1_000,
    "m": 1_000_000,
    "b": 1_000_000_000,
    "t": 1_000_000_000_000,
}


def format_money(amount: int) -> str:
    return f"{int(amount):,}"


def short_money(amount: int) -> str:
    amount = int(amount)

    if amount >= 1_000_000_000_000:
        text = f"{amount / 1_000_000_000_000:.2f}T"
    elif amount >= 1_000_000_000:
        text = f"{amount / 1_000_000_000:.2f}B"
    elif amount >= 1_000_000:
        text = f"{amount / 1_000_000:.2f}M"
    elif amount >= 1_000:
        text = f"{amount / 1_000:.1f}K"
    else:
        return str(amount)

    return text.replace(".00", "").replace(".0", "")


def parse_amount(value, *, minimum: int = 1, maximum: int | None = None) -> int:
    if value is None:
        raise ValueError("Amount is required.")

    text = str(value).strip().lower()
    text = text.replace(",", "").replace("_", "").replace(" ", "")

    if not text:
        raise ValueError("Amount is required.")

    match = re.fullmatch(r"(\d+(\.\d+)?)([kmbt]?)", text)

    if not match:
        raise ValueError("Invalid amount. Try `1,000`, `10k`, or `2.5m`.")

    number = float(match.group(1))
    suffix = match.group(3)

    amount = int(number * SUFFIXES.get(suffix, 1))

    if amount < minimum:
        raise ValueError(f"Amount must be at least {minimum:,}.")

    if maximum is not None and amount > maximum:
        raise ValueError(f"Amount cannot be more than {maximum:,}.")

    return amount