# Findings from the live SGPL Xero org

Everything below was read directly from **Sheldon Global Pte. Ltd.** (SGPL, UEN
201423985K, SGD, Asia/Singapore) on 2026-09-06 via the read-only Xero
connector. These facts drive every design decision in `01-plan.md`.

## F1. You already run two different consignment invoice styles

**Style A — Itemised** (NTUC FairPrice, Ideal Parts, Horme):
one line per SKU, linked to a Xero inventory `Item`, `unit_amount` = our net
selling price, GST Exclusive.

```
SI26060070  NTUC - JEM   2026-07-31   net 366.72  gst 33.01  total 399.73
  OKN-5316: Greenshield Anti-Bacterial Household Wipes 70's - 5060110225316   24 @ 2.98
  LS-9205-BLACK: HOUZE - Aluminium Square Frame Stair Climber Trolley (Black)   6 @ 25.36
```

**Style B — Summary + Commission** (COURTS, Prime Supermarket):
line 1 = the retailer's **gross** sales value for the month, line 2 = a
**negative** "Commission" line posted to an expense account. Net of the two is
what we actually collect.

```
SI26060093  Courts Singapore Pte Ltd - Toa Payoh   2026-07-31
  AR0116257 sales July 2026        1 @  105.42   -> acct 6-1000   gst  9.49
  Commission                       1 @  -36.90   -> acct 8-2002   gst -3.32
                                      net 68.52   gst 6.17   total 74.69
```

The app must support **both**, selected per customer.

> **Reinterpreted 2026-09-07.** Style A is not a consignment style at all — it
> is the **SOR delivery invoice** (plan §1a). Every 2026 NTUC invoice carries an
> 8-digit NTUC **PO number** as its reference and is dated by delivery, not
> month-end. NTUC FairPrice buys on sale-or-return; Ideal Parts and Horme are
> PO-referenced wholesale. Style B (and COURTS' itemised-from-CostPrice variant)
> is the consignment side.

## F2. Commission rates are fixed per customer and machine-checkable

| Customer | Rate (observed) | Samples |
|---|---|---|
| COURTS (all outlets) | **35.00%** | 10/10 invoices, max deviation 0.02% |
| Prime Supermarket | **30.00%** | 316.24 / 1054.12 = exactly 30% |

This means commission is not a judgement call — it is a rate in the customer
profile, and every generated invoice can be **proved** against it before posting.

## F3. GST is 9%, and Xero's exact arithmetic is now known

Verified against real posted invoices, so the app can reproduce Xero's numbers
to the cent *before* it posts anything:

- **Exclusive** (the default): `line_tax = round_half_up(line_net * 0.09, 2)`,
  per line, then summed.
  Proof — SI26060070: 6.44 + 3.22 + 3.22 + 6.44 + 13.69 = 33.01 = `amount_tax`.
  (9% of 71.52 = 6.4368 -> 6.44; 9% of 152.16 = 13.6944 -> 13.69.)
- **Inclusive**: `line_net = round_half_up(gross / 1.09, 2)`, `tax = gross - net`.
  Proof — SI26060097 (Watsons E-Commerce): 18.95 / 1.09 = 17.3853 -> 17.39;
  18.95 − 17.39 = 1.56 = `amount_tax`.

## F4. Inclusive vs Exclusive is already a real per-customer difference

Of 63 invoices in Jul–Aug 2026, all are `Exclusive` **except**
`Watsons (E-Commerce Online)_SGPL`, which is `Inclusive`. So this is not
hypothetical — it is a live profile flag, and getting it wrong on a
$100,000 month is a $9,000 error.

## F5. Contacts are massively duplicated and inconsistently named

Live counts from the SGPL contact list:

- **~48** contacts matching "NTUC"
- **~40** contacts matching "Giant"
- **5** matching "Isetan", **4** matching "Sheng Siong"

Real duplicates and traps found:

| Problem | Examples |
|---|---|
| Same outlet, two contacts | `NTUC - JEM` **and** `NTUC FairPrice Co-operative Limited - Jem` |
| Same outlet, two contacts, **both used in July 2026** | `Courts (Singapore) Pte Ltd -Tampines` (SI26060092) **and** `Courts (Singapore) Pte Ltd - Tampines` (SI26060084) — note the missing space |
| Six spellings of one chain | `Courts Singapore Pte Ltd - X`, `Courts (Singapore) Pte Ltd - X`, `Courts(Singapore) Pte Ltd - X`, `Courts - X`, `Courts Nojima - X` |
| Typo baked into a contact | `Cold Storage Singapore 1983) Pte Ltd - Pioneer Mall` (unbalanced bracket) |
| Chain-level *and* outlet-level contacts coexisting | `NTUC FairPrice Co-operative Limited`, `NTUC FairPrice Co-operative`, `NTUC` |
| Non-customer caught by name match | `NTUC Learning Hub` |

**Fuzzy name matching against this list will post invoices to the wrong
contact.** The app needs an explicit alias registry, not a similarity score.

## F6. Invoicing grain differs by customer

- **Per outlet**: COURTS, NTUC, Giant, Cold Storage (one invoice per store)
- **Per HQ**: Sheng Siong (`CMM Marketing Management Pte Ltd (Sheng Siong)`),
  Prime Supermarket

So one uploaded file may legitimately produce 1 invoice or 40.

## F7. Concrete errors currently in posted, AUTHORISED invoices

These are live in Xero right now. They are the honest business case for the app.

| Invoice | Error |
|---|---|
| SI26060084 | Reference says "sales July 2026", line description says "sales **Aug** 2026". Dated 2026-07-31. |
| SI26060083 | Same July/Aug mismatch between reference and line. |
| SI26060085 | Line description reads `Commissionj` (typo) |
| SI26060092 | Reference `AR011625` — an 8-char AR number where every sibling is 9 (`AR0116257`). Truncated. |
| SI26060090 | Commission posted to **8-2001** while every other COURTS outlet that month used **8-2002** |
| SI26060092 vs SI26060084 | Two different Xero contacts, both "Courts ... Tampines", invoiced in the same batch |
| COURTS Jul batch | Due dates split: most `2026-09-29`, Tampines `2026-08-31` |
| SI26060020 etc. | Invoice number `SI2606…` on invoices dated July and August |
| SI26060070 | NTUC JEM delivery invoice with a **blank reference** — no PO number |
| NTUC 2026 | Payment terms ≈ 60 days but inconsistently applied (2 Jul → 29 Sep, 18 Aug → 17 Oct, 13 Jan → 1 Apr) |

Ten distinct defects across a single quarter's invoicing, all of the type a
deterministic generator makes structurally impossible.

## F8. Only SGPL is reachable from this session

The connector sees one tenant: Sheldon Global Pte. Ltd. **AGPL is a separate
Xero organisation and is not connected here.** The app will need its own Xero
OAuth2 app with *both* tenants authorised — see `01-plan.md` §9.
