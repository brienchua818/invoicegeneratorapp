"""Proof-of-concept: COURTS consignment file -> the 12 invoices it should produce.

Not the app. It exists to prove the plan's arithmetic on a real file before
anyone writes the real thing. No Xero calls; prints what it would post.

    pip install openpyxl
    python prototype/courts_dryrun.py <ConsignmentPO*.xlsx>
"""
import sys
from collections import defaultdict
from datetime import date
from decimal import Decimal

import openpyxl

from gst import line_exclusive, invoice_totals, rate_for, r2

EXPECTED_COMMISSION_TIERS = (Decimal("0.30"), Decimal("0.35"))
TIER_TOLERANCE = Decimal("0.002")


def load(path):
    ws = openpyxl.load_workbook(path, data_only=True)["Sheet1"]
    hdr = [c.value for c in ws[1]]
    rows = [dict(zip(hdr, [c.value for c in ws[r]]))
            for r in range(2, ws.max_row + 1)]
    # profiles/courts.yaml row_filters
    return [r for r in rows if r["Entry No_"] not in (None, "", 0)
            and r["Invoiced Quantity"]]


def main(path):
    rows = load(path)
    rate = rate_for(date(2026, 8, 31))
    stores = defaultdict(lambda: defaultdict(lambda: [Decimal(0), Decimal(0), None]))
    ar = {}
    warnings = []

    for row in rows:
        store = str(row["Location Code"])
        ar.setdefault(store, set()).add(row["PONUMBER"])
        qty = Decimal(str(row["Invoiced Quantity"]))
        cost = Decimal(str(row["CostPrice"]))
        retail = Decimal(str(row["Unit Price"]))

        # Proof 1: commission is VERIFIED, never calculated (plan section 6.1)
        if retail:
            implied = Decimal(1) - cost / (retail / (Decimal(1) + rate))
            if not any(abs(implied - t) <= TIER_TOLERANCE
                       for t in EXPECTED_COMMISSION_TIERS):
                warnings.append(f"{row['Model']}: implied commission "
                                f"{implied:.4f} is not a known tier")

        bucket = stores[store][row["Model"]]
        bucket[0] += qty
        bucket[1] += qty * cost
        bucket[2] = row["Description"]

    grand = {"net": Decimal(0), "tax": Decimal(0), "total": Decimal(0)}
    for store in sorted(stores):
        refs = ar[store]
        assert len(refs) == 1, f"store {store} has multiple AR numbers: {refs}"
        ref = refs.pop()
        lines = [line_exclusive(v[1], rate) for v in stores[store].values()]
        t = invoice_totals(lines)
        print(f"store {store}  {ref}  {len(stores[store]):2} lines   "
              f"net {t['net']:>9}  GST {t['tax']:>7}  total {t['total']:>9}")
        for k in grand:
            grand[k] += t[k]

    print(f"\n{len(stores)} invoices   net {grand['net']}   "
          f"GST {grand['tax']}   total {grand['total']}")
    print(f"rows in: {len(rows)}   rows invoiced: "
          f"{sum(len(v) for v in stores.values())} aggregated lines")
    for w in sorted(set(warnings)):
        print(f"  ⚠ {w}")


if __name__ == "__main__":
    main(sys.argv[1])
