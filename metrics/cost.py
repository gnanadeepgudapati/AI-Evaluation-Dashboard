# cost.py
# Maintained price table for supported models (USD per 1M tokens) and the
# function that turns token counts into a dollar figure.

PRICE_TABLE: dict[str, dict[str, float]] = {
    "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.00},
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
}


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Return the USD cost for a single request.

    Unknown models are not an error — they simply cost $0.0, since newer
    models may not yet be in the price table.
    """
    prices = PRICE_TABLE.get(model)
    if prices is None:
        return 0.0

    cost = (
        input_tokens * prices["input"] + output_tokens * prices["output"]
    ) / 1_000_000
    return cost
