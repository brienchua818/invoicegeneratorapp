"""GST engine — reproduces Xero's arithmetic exactly.

Verified against live SGPL invoices (see docs/00-findings.md F3):
  Exclusive: SI26060070 -> 6.44+3.22+3.22+6.44+13.69 = 33.01 = amount_tax
  Inclusive: SI26060097 -> 18.95/1.09 = 17.39, 18.95-17.39 = 1.56 = amount_tax

Money is Decimal everywhere. Never float.
"""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

# Rate is chosen by the PERIOD being invoiced, never by today's date, so that
# restatements and credit notes against older periods stay correct.
GST_RATES = [
    (date(2007, 7, 1), date(2022, 12, 31), Decimal("0.07")),
    (date(2023, 1, 1), date(2023, 12, 31), Decimal("0.08")),
    (date(2024, 1, 1), None,               Decimal("0.09")),
]


def rate_for(period_end: date) -> Decimal:
    for start, end, rate in GST_RATES:
        if period_end >= start and (end is None or period_end <= end):
            return rate
    raise ValueError(f"no GST rate defined for {period_end}")


def r2(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def line_exclusive(net: Decimal, rate: Decimal) -> tuple[Decimal, Decimal]:
    """Amount EXCLUDES GST. Returns (net, tax). Tax rounds per line."""
    net = r2(net)
    return net, r2(net * rate)


def line_inclusive(gross: Decimal, rate: Decimal) -> tuple[Decimal, Decimal]:
    """Amount INCLUDES GST. Returns (net, tax)."""
    gross = r2(gross)
    net = r2(gross / (Decimal(1) + rate))
    return net, gross - net


def invoice_totals(lines: list[tuple[Decimal, Decimal]]) -> dict:
    """Xero sums the per-line rounded values; it does not re-round the total."""
    net = sum((n for n, _ in lines), Decimal(0))
    tax = sum((t for _, t in lines), Decimal(0))
    return {"net": net, "tax": tax, "total": net + tax}


if __name__ == "__main__":
    r = rate_for(date(2026, 8, 31))
    assert r == Decimal("0.09")

    # Regression: SI26060070 (NTUC - JEM), exclusive
    lines = [line_exclusive(Decimal(n), r)
             for n in ("71.52", "35.76", "35.76", "71.52", "152.16")]
    t = invoice_totals(lines)
    assert t == {"net": Decimal("366.72"), "tax": Decimal("33.01"),
                 "total": Decimal("399.73")}, t

    # Regression: SI26060097 (Watsons E-Commerce), inclusive
    net, tax = line_inclusive(Decimal("18.95"), r)
    assert (net, tax) == (Decimal("17.39"), Decimal("1.56")), (net, tax)

    print("GST engine matches both live Xero invoices exactly.")
