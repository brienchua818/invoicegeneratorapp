# Analysis of real customer files

Three customers' documents were supplied 2026-09-06 and parsed in full. COURTS
and Shell sit at opposite ends of the spreadsheet difficulty range; Yue Hwa is
not a spreadsheet at all and reverses the direction of money. Between them they
cover most of what the app will meet.

---

## File A — `ConsignmentPO2436_SHG_20260906.xlsx` (COURTS)

**Shape:** `Sheet1`, header on row 1, 21 columns, **160 data rows → 159 real**.
One row per *sales transaction*, not per SKU and not per store.

| Col | Header | Meaning | Use |
|---|---|---|---|
| A | `Entry No_` | COURTS ledger entry id | dedupe key |
| D | `Item No_` | **COURTS' article code** (`IP191504`) | `ProductAlias` key |
| E | `Invoiced Quantity` | units (**can be negative**) | quantity |
| F | `Location Code` | **store code** (`870`, `928`) | outlet resolution |
| N | `PONUMBER` | **AR number** (`AR0116471`) | invoice reference |
| O | `CostPrice` | **what COURTS pays us, ex-GST** | ← **the invoice price** |
| R | `Description` | COURTS' description | display / fallback match |
| S | `Model` | **our SKU** (`OKN-7174`, `LS-9743-COAL GREY`) | primary match key |
| U | `Unit Price` | **retail price, GST-inclusive** | verification only |
| M | `BATCHID` | `2436` — matches the filename | period/batch key |
| K | `Vendor No_` | `SHG` (all 159 rows) | entity hint |

### A1. There is a junk row that must be dropped

Row 2 is a null record: `Entry No_ = 0`, `BATCHID = 0`, all prices `0`, dates
`2023-01-01`. It is a template artefact. **Rule: drop rows where
`Entry No_ = 0`.** Left in, it is harmless here, but it is exactly the kind of
row that breaks a naive `SUM()`.

### A2. `Location Code` ↔ `PONUMBER` is strictly 1:1

12 stores, 12 AR numbers, and the row counts match exactly:

```
867→AR0116469(14)  869→AR0116470(4)   870→AR0116471(36)  874→AR0116472(4)
875→AR0116473(6)   876→AR0116474(2)   877→AR0116475(6)   882→AR0116476(2)
921→AR0116477(10)  927→AR0116478(17)  928→AR0116479(29)  929→AR0116480(29)
```

So the AR number never has to be typed. It is read from the file, per store.
This alone makes the truncated `AR011625` in live invoice SI26060092 (F7)
impossible.

### A3. GST is *inside* one column and *outside* another — in the same file

This is the crux of your "some report with GST, some don't" question, and this
file contains **both conventions simultaneously**:

- `Unit Price` (retail) is **GST-inclusive** — `4.90`, `19.90`, `75.00`
- `CostPrice` (what we bill) is **GST-exclusive** — `2.92`, `11.87`, `48.17`

Proof, across every SKU in the file:

```
CostPrice / (Unit Price ÷ 1.09)  →  0.6496 … 0.6503   (i.e. 35% commission)
                                 or 0.6998 … 0.7003   (i.e. 30% commission)
```

Those ratios land on 0.65 and 0.70 to within 0.0007 across all 159 rows. That
is not a coincidence — it confirms both the 9% rate and the inclusive/exclusive
split beyond any doubt.

### A4. Commission is **not** a flat 35% — it is per-SKU, and this is costing money

Your Xero invoices apply a flat 35% (F2). The file says otherwise. **Five SKUs
carry 30%, not 35%:**

| SKU | Cost | Retail | Rate |
|---|---|---|---|
| `LS-9743-COAL GREY` | 48.17 | 75.00 | **30%** |
| `MEGASTORE WAREHOUSE SALES` | 5.14 | 8.00 | **30%** |
| `MOMO FAUX FUR` | 19.21 | 29.90 | **30%** |
| `NORD RECTANGULAR` | 8.22 | 12.80 | **30%** |
| `ROADSHOW SPECIAL BUY $20` | 12.84 | 20.00 | **30%** |
| everything else (29 SKUs) | — | — | 35% |

Note `LS-9743-COAL GREY` is 30% while `LS-9743-WHITE` is 35% — the same table in
a different colour. Whether that is a deal or a COURTS data error is a question
for them (Q11), but either way **the file is authoritative and a flat rate is not.**

The consequence, computed on this actual file:

| Method | August total (ex-GST) |
|---|---|
| Sum of `CostPrice × Qty` (correct) | **$1,127.72** |
| Retail ex-GST × 65% (current practice) | $1,116.75 |
| **Under-billed** | **$10.97 — 0.97% of revenue** |

Blended commission actually ranges **31.78% – 35.05%** by store, purely from
product mix:

```
store  AR number    rows  NET(cost)  RETAIL exGST   blended
876    AR0116474       2      71.22        109.54    34.98%
882    AR0116476       2      31.23         45.78    31.78%
927    AR0116478      17     329.48        499.45    34.03%
928    AR0116479      29     317.42        482.94    34.27%
...
TOTAL                159    1,127.72      1,718.08    34.36%
```

**Design conclusion: do not compute commission. Use `CostPrice` directly.**
The commission rate becomes a *check* (assert the implied rate is 30% or 35%
and flag anything else), never an input. That is both more accurate and
strictly safer.

### A5. Returns are already present

Three rows carry `Invoiced Quantity = -1`, all at store 870 (Greenshield wipes).
They net down within the same store's invoice. So negative quantities are
normal, and `block_on_negative_net` must be **off** for COURTS.

### A6. What the August invoices should be

12 invoices, one per store. `prototype/courts_dryrun.py` computes them from the
file end to end:

```
store 867  AR0116469   7 lines   net    46.72  GST   4.20  total    50.92
store 869  AR0116470   2 lines   net    14.60  GST   1.32  total    15.92
store 870  AR0116471   9 lines   net   102.20  GST   9.20  total   111.40
store 874  AR0116472   1 line    net    11.68  GST   1.05  total    12.73
store 875  AR0116473   4 lines   net    17.52  GST   1.58  total    19.10
store 876  AR0116474   1 line    net    71.22  GST   6.41  total    77.63
store 877  AR0116475   3 lines   net    20.44  GST   1.85  total    22.29
store 882  AR0116476   2 lines   net    31.23  GST   2.81  total    34.04
store 921  AR0116477   5 lines   net    43.80  GST   3.94  total    47.74
store 927  AR0116478  11 lines   net   329.48  GST  29.65  total   359.13
store 928  AR0116479  19 lines   net   317.42  GST  28.57  total   345.99
store 929  AR0116480   6 lines   net   121.41  GST  10.93  total   132.34
```

Grand total: **net $1,127.72 · GST $101.51 · $1,229.23**, from 159 source rows
aggregated into 70 invoice lines.

### A7. A 2¢ lesson worth the whole prototype

My first pass computed GST as `round(store_net × 9%)` and got **$101.49**. The
prototype, which rounds **per line** the way Xero does (F3), gets **$101.51**.

Two stores differ by one cent each:

| Store | Invoice-level rounding | Xero's line-level rounding |
|---|---|---|
| 869 | 1.31 | **1.32** |
| 877 | 1.84 | **1.85** |

Two cents on $1,229 is immaterial as money and *completely* material as a
signal: it means a plausible-looking implementation was already wrong on its
second-ever calculation, silently, in a way no human review would catch. It is
the precise reason the plan front-loads the GST engine and pins it to regression
tests against real posted invoices (plan §11, Phase 0).

---

## File B — `Table_Matters_Aug26_Sales_Report.xlsx` (Shell petrol stations)

**Shape:** `Sheet1`, header row 1, **5 columns, 10 data rows.** As sparse as a
file can be.

| Col | Header | Notes |
|---|---|---|
| A | `Product` | **free text only — no SKU, no barcode** |
| B | `Date` | transaction date |
| C | `Quantity Sold` | all `1` |
| D | `Gross Sales Loc Cur` | `15`, `25`, `14.9`, `15.9`, `35` |
| E | `Site` | `SHELL PAYA LEBAR PIE 627_01` |

### B1. This file proves the AGPL/SGPL split is a day-one problem

The file is titled **Table Matters** — but row 2 is:

```
"Pack of 8 HOUZE - Humipod 800ML"   $15.00   SHELL JURONG WEST AVE5 611_01
```

**HOUZE is SGPL. Table Matters is AGPL. They are in the same file.**

Routing this file by its name or by "Shell → one entity" books SGPL revenue
into AGPL. Routing by **brand**, as designed, produces the correct answer:

| Site | Brand → Entity | Rows | Gross | Net @9% | GST |
|---|---|---|---|---|---|
| SHELL JURONG WEST AVE5 611_01 | HOUZE → **SGPL** | 1 | 15.00 | 13.76 | 1.24 |
| SHELL PAYA LEBAR PIE 627_01 | Table Matters → **AGPL** | 9 | 228.60 | 209.72 | 18.88 |

Two invoices, **two different Xero organisations, from one 10-row file.**

### B2. Site codes make outlet matching exact, not fuzzy

Your Xero contacts already embed the Shell site code:

```
file:    SHELL JURONG WEST AVE5 611_01
Xero:    HJCC-(80) - Shell Jurong West Ave5 611_01      ← 611_01

file:    SHELL PAYA LEBAR PIE 627_01
Xero:    Magnaton Ventures - Shell Paya Lebar Pie 627_01 ← 627_01
```

So the match key is the regex `\d{3}_\d{2}`, not the station name. Exact,
deterministic, immune to `Ave5` vs `Ave 5` and `P.lebar` vs `Paya Lebar`.

Of ~47 Shell contacts in SGPL, **46 carry a site code**; the exception is
`The Driving Forcemgmt Service - Shell Tampines Ave 2`, which needs a manual
alias. That is a 15-second fix, once.

Also note: **each station is a different dealer company** (HJCC, Magnaton,
Fach, Alon, Zenith…). The invoice goes to the *dealer*, not to Shell. That is
why 47 contacts exist and why "invoice Shell" would be wrong.

### B3. Nothing in this file tells you about GST — the profile must

There is no cost column, no commission column, no tax column, and no total row.
`Gross Sales Loc Cur` values of `15.90`, `16.90`, `35.00` are unmistakably
Singapore shelf prices, i.e. **GST-inclusive retail**.

But "unmistakably" is exactly the reasoning that must not be in the code. So:

- the **profile declares** `tax_treatment: inclusive`, `amount_basis: retail_gross`
- and because there is **no total row, Proof 2 is unavailable for this customer** —
  the app falls back to **Proof 3** (challenge each implied unit price against
  the prior period). Losing one of three checks is exactly the kind of thing the
  profile should record explicitly.
- the **commission rate is not in the file** and must come from the Shell
  agreement (Q4).

### B4. Product matching here is name-only — the hard case

8 distinct product strings, no codes:

```
Table Matters - Everyday Chef 28CM Non-Stick Wok Pan - Sage
Table Matters Wok Pan Sage                                   ← same product?
Set of 8 Table Matters - Casa Nestable Kitchen Mixing Bowl Set with …
Pack of 8 HOUZE - Humipod 800ML
```

Two problems, both requiring a human once and never again:

1. **`Table Matters Wok Pan Sage` ($25) vs `Table Matters - Everyday Chef 28CM
   Non-Stick Wok Pan - Sage` ($35).** Different prices, so probably different
   products — but a fuzzy matcher would happily merge them. This is precisely
   why match tiers 5–6 never auto-accept.
2. **`Pack of 8` / `Set of 8` prefixes.** Is `Quantity Sold = 1` one pack of 8,
   or 8 units? It changes the invoice by 8×. Must be resolved explicitly and
   stored as a `pack_multiplier` on the alias.

Once each of these 8 strings is confirmed once, the `ProductAlias` table
answers them forever, and Shell becomes a zero-touch customer.

---

## File C — Yue Hwa: `CC0414_AUDREY_GLOBAL_PTE_LTD_Statement_31Aug2026.pdf` + `…_Invoice_31Aug2026.pdf`

**Shape:** two PDFs, not a spreadsheet. And the direction of money is
**reversed** — these are documents Yue Hwa issues *to us*, not sales data for us
to invoice from.

### C1. What the two documents actually are

**The Statement** (`CONST18-02022`, consignor `CC0414`, 1–31 Aug 2026):

```
Store            Department   Description     Sales Amt(SGD)   Amount(SGD)
China Town Store Households   Sales               1,087.52
                              LOYALTY-5%            179.26           8.96
                              Store Total                            8.96
                              Grand Total                            8.96
```

Read it as: Yue Hwa's China Town store sold **$1,087.52** of our Households
goods in August. Of that, **$179.26** was bought by Yue Hwa loyalty members who
received a 5% discount, and Yue Hwa recharges that discount to us:
`179.26 × 5% = 8.963 → $8.96`. The statement's Grand Total is the **$8.96 we
owe them**, not the $1,087.52 they owe us.

**The Tax Invoice** (`PPCN-2608-0099`, dated 31 Aug 2026) formalises it:

```
70050  AUDREY GLOBAL PTE LTD-LOYALTY-5%   Sundry Income    1 × 8.96 = 8.96
       Total Excl. GST   8.96
       9% GST            0.81
       Total Incl. GST   9.77
```

Yue Hwa is GST-registered (`M2-0106407-4`), so the $0.81 is **claimable input
tax** for AGPL — *if* it is recorded as a bill, not netted invisibly.

### C2. This answers two open questions outright

| Question | Answer, from the PDF |
|---|---|
| Q2 — AGPL's legal identity | **Audrey Global Pte Ltd**, #03-08A Plaza 8 @ CBP, 1 Changi Business Park Crescent, Singapore 486025. Yue Hwa consignor code `CC0414`. |
| Q13 — does anyone send PDF only? | **Yes.** Yue Hwa sends PDFs. PDF intake is in scope, not optional. |

### C3. What it adds to the scope

1. **Bills, not just invoices.** The app must create Xero **ACCPAY** documents
   (bills) as well as ACCREC (sales invoices). The Yue Hwa loyalty recharge is
   a bill in AGPL with $0.81 of input GST. Netting it silently against our
   receivable would lose the input-tax claim and misstate both sides.
2. **The sales figure still needs a separate source.** `Sales Amt 1,087.52` is
   department-level, has no SKUs, and does not say whether it is GST-inclusive
   or what commission Yue Hwa retains. Either Yue Hwa sends a separate itemised
   report, or the app invoices from this figure using a rate from the agreement
   (as for Shell). **Open question Q15.**
3. **A third flow pattern.** COURTS gives us cost prices (bill what they say).
   Shell gives us retail only (derive from agreement). Yue Hwa gives us a
   *department total plus a counter-charge* — settlement is our invoice minus
   their bill. The profile needs a `settlement: gross | contra` mode.
4. **Contact hygiene, again.** SGPL holds three Yue Hwa contacts — `Yue Hwa`,
   `Yue Hwa Chinese Product Pte Ltd`, `Yue Hwa Chinese Product Pte Ltd.` — and
   all three misspell the legal name on the PDF (*Products*, plural). AGPL, where
   this actually belongs, is not visible to me yet.

### C4. Why PDF is the easy part

Both PDFs are text-based (not scanned); the numbers extract cleanly. A PDF
profile is the same idea as an Excel one — declare where each value sits,
fingerprint the layout, reconcile `Store Total = Grand Total`, assert
`Amount = round(Sales Amt × rate, 2)` — plus a fallback to OCR for the day
someone sends a photo. The LLM-assisted onboarding pass is genuinely useful
here: it can propose the field map from one sample; the human confirms; the
run-time stays deterministic.

---

## File E — `A050__S119__CON_AUG26.pdf` (Prime Supermarket, consignment)

**Shape:** 6-page **scanned** PDF (printed, hand-signed, scanned — no text
layer). Two consignment reports back to back, one per vendor code:

| Pages | Vendor code | Vendor name on report | Item category | Entity | Outlets | Grand total |
|---|---|---|---|---|---|---|
| 1–2 | **A050** | AUDREY GLOBAL PTE LTD (CONSIGNMENT) | 05050 | **AGPL** | BR16 | **$238.56** |
| 3–5 | **S119** | SHELDON GLOBAL PTE LTD (CONSIGNMENT) | 05051 | **SGPL** | BR16, TP25 | **$649.46** |

Each report = a **summary page** (Taxable Sales per outlet → Commission −30% →
Total; then Grand Total; note: *"Please issue Tax Invoice for the Grand Total
amount"*) followed by **detail pages** listing every item sold per outlet:
`Item No` (`0505000064`…) · `Description` · `QTY` · `Net Sales` · `Disc.` ·
`Gross Amount`. Page 6 is blank.

### E1. Prime pre-splits by entity — and the brand rule still agrees

Prime keeps a vendor account per legal entity, so the split that COURTS and
Shell force us to compute (§B1, §D1) arrives pre-done. Brand routing yields the
same answer (Kakudo/Table Matters lines under A050; HOUZE/Greenshield under
S119), so **the rule does not change** — Prime is just the easy case of it.
Two invoices, two Xero orgs, from one PDF.

### E2. Commission is printed on the report: 30.00%

Independent confirmation of the rate derived from Xero (F2) and the master's
header. It is applied to **Net Sales after `Disc.`**: 730.15 × 30% = 219.05 ✓;
340.80 × 30% = 102.24 ✓.

### E3. "Net Sales" is GST-exclusive retail — provable from the file itself

Every line's `Net Sales ÷ QTY × 1.09` lands on a shelf price:

```
HOUZE MATTE 13L drawer      9.08  × 1.09 =  9.90
Stair climber trolley      36.61  × 1.09 = 39.90
Anti-bacterial wipes        4.50  × 1.09 =  4.905 → 4.90
TM 20cm non-stick pot      33.94  × 1.09 = 37.00
```

So `gst.columns.net_sales: exclusive`, and Proof 1 exists for Prime. Current
Xero practice (SI26060095, July: 1,054.12 gross → −316.24 commission → 737.88
net → GST 66.41) is consistent with that.

### E4. Summary and detail reconcile — Proof 2 is available

BR16 detail lines sum to $340.80 = the summary's Taxable Sales. TP25: lines sum
to $730.15 = summary. Unlike Shell (§B3), Prime gives the app a customer total
to check against.

### E5. It is a scan, and half of it is upside-down

Pages 2, 4 (the detail pages) are rotated 180°. No text layer anywhere. The
app's PDF intake therefore needs **OCR with orientation detection** (Tesseract
`--psm 0` OSD, or a cloud document API), and the *summary page* — not the OCR of
the detail lines — should drive the invoice, with the detail used for Proof 2
and for per-SKU analytics. OCR of digits must be validated by the reconciliation
(E4), never trusted alone.

### E6. Prime's item codes have no home in the master yet

`0505000064`, `0505100039`… are Prime's article numbers (category prefix + seq).
Master 4.0 has no `Prime SKU` column. Either one is added (consistent with how
every other retailer is handled) or Prime stays summary-only with no SKU-level
detail — which is what the current Xero invoice does.

### E7. Invoice grain is HQ, with outlet detail

Xero has one Prime contact (`Prime Supermarket (1996) PTE LTD`) and one invoice
per entity per month (`Sales July 2026`, commission to `8-2006`). The report's
outlet columns (BR16, TP25) belong as line-level detail or a reference note,
not as separate invoices.

---

## File D — the master price lists in Google Drive

> **Superseded on the same day.** Brien then supplied the current master,
> `Master Price List 4.0 - 2025 R1.xlsm` (modified 2026-09-04). It is documented
> in full in `03-master-price-list.md` and replaces both lists below. The
> analysis here is kept because it is what exposed the nickname problem (§D3).

Brien's instruction: *"when in doubt, look for the master pricelist in the shared
drive."* I did. Two candidates, both read in full via the Drive connector.

| File | Location | Modified | Rows | Has BRAND | Has barcode |
|---|---|---|---|---|---|
| `Master Price List - For Ravi.xlsx` | Drive `1911XKZ6…` | **Jun 2024** | 2,127 active + 1,149 discontinued | ✅ | ✅ |
| `GoLabel Master Database 2025 (Updated).xlsx` | Drive `13rGDfCt…` | **Jan 2026** | 1,431 (HOUZE & TM sheet) | ✅ | ✅ |

**Brand split, active SKUs (Ravi master):** TABLE MATTERS 1,050 · HOUZE 851 ·
LIAO 77 · Finder 53 · ecoHOUZE 52 · Greenshield 11 · Tramontina 4. So the
`BRAND` column exists, is populated, and routes cleanly: `TABLE MATTERS → AGPL`,
everything else → SGPL.

### D1. Confirmed: KD10998 is Table Matters → AGPL

```
KD10998   TABLE MATTERS   BOWLS(1)   Kakudo Assorted 5.25 inch Rice Bowl (Set of 5)   8886483726840
OKN-7174  Greenshield     Kitchen Necessities   Microwave & Fridge Freezer Wipes 70's    5060110227174
LS-9743-COAL GREY  HOUZE  Lifestyle  180cm/6ft HDPE Folding Table …   8886483723221
```

So the COURTS August file **does** split across entities: store 928's AR0116479
carries $19.38 of Table Matters (KD10998) → AGPL, and — once the CM-20/28/38
lines are confirmed TM (Brien says they are) — $99.30 in total.

### D2. Both masters are stale, and that is the finding

Neither contains `CM-20`, `CM-28`, `CM-38` (newer SKUs). The Ravi master (2024)
has none of the *Everyday Chef* range that Shell sells; the GoLabel file (2026)
has it under `EF` codes:

```
EF97240G  Table Matters Everyday Chef Series: Non-Stick 24cm Wok Pan …
EF94200G  Table Matters Everyday Chef Series: 20cm Non Stick Casserole …
EF07217S  Table Matters Everyday Chef Series: Tempered Glass Universal Lid …
```

**So there is no single current master.** The app's `Product` table has to be
seeded from *both* and then kept current from Xero Items. This is a Tier-1 data
item (plan §10 #2) and it is not solved yet.

### D3. The COURTS `Model` column is not reliably our SKU

Running the prototype against the Ravi master shows exactly how much the alias
table matters. Of 34 distinct `Model` values in the COURTS file:

| Resolved via master | Not in master |
|---|---|
| 19 values — `OKN-*`, `LS-*`, `LN-*`, `KD10998` … | **15 values** — `KYRO`, `POPCON`, `PORTASTOOL`, `KRUSTY`, `MOMO FAUX FUR`, `NORD RECTANGULAR`, `MATTE 5.5L/13L/25L/35L SINGLE TIER`, `MEGASTORE WAREHOUSE SALES`, `ROADSHOW SPECIAL BUY $20`, `CM-20/28/38` |
| $663.48 of net | **$464.24 of net — 41% of the file** |

These are COURTS' *nicknames* for our products, not codes. `KYRO` is a Houze
product line; `MATTE 13L SINGLE TIER` is `MS-22xx`. They will never match a SKU
column. What *will* match, forever, is COURTS' own `Item No_` (`IP201479` etc.),
which is stable — so the alias key for COURTS is **`(courts, Item No_) →
our SKU`**, exactly tier 2 of the match ladder, and the `Model` column drops to a
hint. Fifteen aliases to confirm once; then zero-touch.

This is the strongest possible validation of the plan's rule that an unresolved
row *blocks* rather than passes: a naive "match on Model" implementation would
have silently invoiced 59% of COURTS and dropped the rest.

### D4. The Shell `Pack of 8` question is answered by a SKU

GoLabel lists both `LS-9631` *Humipod – Activated Charcoal Dehumidifier (800ml)*
and **`LS-9631*8`** *… Pack of 8*. The pack is its own SKU, so `Quantity Sold = 1`
of *Pack of 8 HOUZE – Humipod 800ML* is **one unit of `LS-9631*8`**, not eight
of `LS-9631`. The `pack_multiplier` field becomes unnecessary for this case —
the alias simply points at the pack SKU.

### D5. What this means for the app

- **Drive is reachable from the app.** The master lives in Google Drive; the
  Drive API is available; the app should pull the current master on a schedule
  rather than rely on someone uploading it.
- **Xero Items is the other half.** Both masters miss recent SKUs; Xero's item
  list (which the NTUC invoices already reference by `item_code`) will have them.
  Product table = union of Drive master + Xero Items, per entity.
- **Cost tiers are in the master too.** `COST TO RELATED COMPANIES`, `CURRENT
  COST TO TGG (Mark up 35%)`, `TIER 1/2/3 RSP`. That is the price-list input for
  itemised customers (plan §10 #3), at least as a starting point.

---

## What these files change in the plan

| Finding | Plan change |
|---|---|
| A4: commission is per-SKU and in the file | `CostPrice` is the price. Commission becomes a **validation**, not a calculation. |
| A4: 0.97% under-billing | Quantified ROI. Recover it from month 1. |
| A3/B3: GST convention differs *per column* | `tax_treatment` moves from the profile root to **per-column**. |
| B1: cross-entity file confirmed | Brand→entity splitting is **Phase 2, not Phase 5.** |
| B2: site codes in contact names | Add `outlet_match: regex` to the profile. Kills fuzzy matching for Shell. |
| A1: junk row | Add `row_filters` to the profile. |
| A5: negative quantities | Returns handling is day-one, not a later phase. |
| B3: no totals row | Profile records **which proofs are available** per customer. |
| B4: pack/set prefixes | `ProductAlias` needs a `pack_multiplier` field. |
| A2: AR number derivable | Reference is computed, never typed. |
| C1: Yue Hwa bills *us* | App must create **Bills (ACCPAY)** as well as invoices; input GST captured. |
| C2: AGPL identified | Audrey Global Pte Ltd, consignor `CC0414` at Yue Hwa. |
| C2: PDF intake confirmed | PDF parsing moves from Phase 5 to **Phase 4**; text-layer first, OCR fallback. |
| C3: settlement pattern | Profile gains `settlement: gross | contra`. |
| D1: KD10998 is Table Matters | COURTS **does** split across entities (store 928 → AGPL). |
| D2: no single current master | Product table = Drive master ∪ Xero Items, refreshed on schedule. |
| D3: COURTS `Model` is a nickname 44% of the time | Alias key for COURTS is `Item No_`, not `Model`. ~15 aliases to confirm once. |
| E1: Prime pre-splits by vendor code = entity | Brand rule unchanged; Prime is the easy case. |
| E3/E4: Net Sales ex-GST, summary = detail | Prime has Proofs 1 **and** 2; commission 30% printed on the report. |
| E5: scanned, rotated | PDF intake needs OCR + orientation detection; summary drives, detail verifies. |
| E6: no `Prime SKU` column | Add one to the master, or keep Prime summary-only. |
| D4: pack SKUs exist | `Pack of N` resolves to a pack SKU (`LS-9631*8`), not a multiplier. |
| **Master 4.0** has per-customer SKU columns | **The alias table already exists** in the master; unresolved articles are fixed by filling a cell there. See `03-master-price-list.md`. |
| Master 4.0 resolves 24 of 36 COURTS articles | 12 remain (KYRO ×3, POPCON, PORTASTOOL, KRUSTY, MOMO ×2, CM-20/28/38, two promo lines) — $390.24, 35% of the file. |
