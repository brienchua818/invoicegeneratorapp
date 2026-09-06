# Consignment Invoice Generator — Design Plan

**Sheldon Global / Audrey Global · Singapore · v1 plan · 2026-09-06**

**Evidence base — read these first:**
- `00-findings.md` — what your live Xero org actually contains
- `02-source-files.md` — full analysis of the real customer files you sent, plus the master price lists found in Drive
- `profiles/courts.yaml`, `profiles/shell.yaml` — working profiles built from them

This plan refers to both constantly. Where it says (F3) or (§A4) it means a
specific, checkable finding in those documents, not an assumption.

---

## 1. The question you actually asked

> *"how do we train the app to know all these?"*

**You don't train it. You teach it once per customer, and then it never guesses
again.**

This is the single most important decision in the whole project, so it is worth
being blunt about why.

A trained/statistical model that "learns" your invoicing would be a disaster
here. It would be right 95% of the time, which sounds good until you realise
that on a 40-outlet COURTS run it means two wrong invoices every month, and you
would never know which two. Money and GST are domains where a system must be
either **provably right** or **loudly stopped**. There is no acceptable middle.

So the architecture is:

```
     ONE-TIME, PER CUSTOMER                       EVERY MONTH, FOREVER
  ┌───────────────────────────┐            ┌──────────────────────────────┐
  │  AI-ASSISTED ONBOARDING   │            │  DETERMINISTIC EXECUTION     │
  │                           │            │                              │
  │  LLM reads a sample file  │            │  Rules engine reads the      │
  │  and PROPOSES a mapping   │  ────────► │  saved profile and applies   │
  │                           │  produces  │  it exactly. No inference.   │
  │  A HUMAN CONFIRMS it      │  a saved   │  No model. No randomness.    │
  │  once, in a UI            │  Customer  │  Same file in = same         │
  │                           │  Profile   │  invoices out, byte for byte │
  └───────────────────────────┘            └──────────────────────────────┘
        ~20 min per customer                    ~90 seconds per file
```

The "intelligence" is spent **once**, on a hard problem (what do these columns
mean?), under human supervision. The recurring monthly run is then boring,
auditable arithmetic — which is exactly what you want touching your GST returns.

### Where AI *is* used (and where it is banned)

| Allowed | Banned |
|---|---|
| Proposing column mappings at onboarding | Deciding any number that reaches an invoice |
| Suggesting candidate SKU matches for a human to approve | Auto-matching a SKU |
| Detecting that a file's layout drifted from last month | Deciding whether a figure includes GST |
| Drafting a plain-English explanation of a variance | Choosing which Xero org to post to |
| Reading a PDF/email when a customer sends no Excel | Filling a blank cell with a "reasonable" value |

**Rule: no LLM output ever reaches Xero without passing through a
deterministic validator or a human click.**

---

## 2. The Customer Profile — the thing you "teach"

This is the heart of the system. One YAML/JSON record per customer, version
controlled, human readable, diffable. Working examples for three of your real
customers are in `docs/profiles/`.

Two **real** profiles, built from the two files you sent, are in
`docs/profiles/`. Rather than reprint them, here is what they demonstrate:

| | `courts.yaml` | `shell.yaml` |
|---|---|---|
| Source shape | 21 cols, 159 transaction rows | 5 cols, 10 rows |
| Product key | our SKU **and** their article code | **free text only** |
| Price source | `CostPrice` column (authoritative) | not in file — from agreement |
| GST | **inclusive and exclusive, in different columns** | inclusive (declared) |
| Outlet key | store code → 1:1 AR number | `\d{3}_\d{2}` site code regex |
| Proofs available | 2 of 3 | **1 of 3** |
| Entities touched | SGPL | **AGPL *and* SGPL, same file** |

Read `profiles/courts.yaml` next to `02-source-files.md §A` and the whole
design should click: **every line of the profile traces to an observed fact in
the file.** Nothing is invented, and nothing is inferred at runtime.

The critical property is that when COURTS changes their commission, or Shell
renames a station, the fix is a line of YAML with a date on it — reviewed in
30 seconds — not a code change and not a retraining exercise.

---

## 3. Domain model

```
Entity          AGPL, SGPL                    (a Xero tenant + its OAuth token)
Brand           Table Matters, Houze,         (belongs to exactly one Entity)
                Painting Matters, Greenshield
Product         our SKU, barcode(s), brand    (brand determines Entity)
ProductAlias    (customer, their_code) -> Product
Customer        COURTS, NTUC, Giant …
Outlet          COURTS Tampines, NTUC JEM …
ContactLink     (Entity, Outlet) -> xero_contact_id   ← kills the F5 duplicates
CustomerProfile the YAML above
Period          2026-07
Upload          the file + sha256 + who + when
StagedRow       one parsed line, with its resolution decisions
InvoiceDraft    what we intend to post
PostedInvoice   xero_invoice_id + idempotency key
```

Three of these deserve emphasis.

**`ContactLink` is per-Entity.** The same COURTS Tampines outlet has one
contact ID in SGPL and a *different* one in AGPL. A single `contact_id` field
would be a bug.

**`ProductAlias` is the memory.** Every time a human resolves "what is COURTS
article 4471820?", that answer is stored forever. Month 1 you might resolve 60
aliases. Month 6 you resolve two. The system gets quieter over time without
anyone "training" anything.

**`Upload.sha256` + `PostedInvoice.idempotency_key` are how you can never
double-invoice.** Key = `sha256(entity, customer, outlet, period, line_hash)`.
Re-upload the same file → the app recognises every invoice already exists and
posts nothing.

---

## 4. Which Xero org — the bit that's more subtle than it looks

You described it as:

> AGPL = Table Matters · SGPL = Houze, Painting Matters, Greenshield

That is a **brand → entity** rule, not a customer → entity rule. And that has a
consequence worth catching now:

> **One customer file can contain both AGPL and SGPL products, and must be
> split into two invoices in two different Xero organisations.**

**This is confirmed, not theoretical.** The Shell file you sent is titled
*Table_Matters_Aug26_Sales_Report.xlsx* — and row 2 of 10 is
`Pack of 8 HOUZE - Humipod 800ML`, a **Houze/SGPL** product (§B1). Routing that
file by its name, or by "Shell → one entity", books SGPL revenue into AGPL.

One 10-row file therefore produces **two invoices in two different Xero
organisations**:

| Site | Brand → Entity | Gross | Net | GST |
|---|---|---|---|---|
| SHELL JURONG WEST AVE5 611_01 | HOUZE → **SGPL** | 15.00 | 13.76 | 1.24 |
| SHELL PAYA LEBAR PIE 627_01 | Table Matters → **AGPL** | 228.60 | 209.72 | 18.88 |

Isetan, BHG, Yue Hwa and Tangs will behave the same way. Brand→entity routing
is therefore **Phase 2 work, not a later refinement.**

So the routing algorithm is:

```
for each parsed row:
    product = resolve_sku(row)          # §7 — hard-stops if unresolved
    brand   = product.brand
    entity  = brand.entity              # Table Matters -> AGPL, else SGPL

group rows by (entity, outlet)
    -> one InvoiceDraft per group
    -> each draft posts to its own entity's Xero tenant
```

Confirmed twice over: SI26060070 (one NTUC JEM invoice) already mixes **Houze**
and **Greenshield** — both SGPL, so it stays one invoice. The Shell file mixes
**Houze** and **Table Matters** — different entities, so it must split.

✅ **Resolved:** the COURTS file carries `Vendor No_ = SHG` on all 159 rows, yet
includes `KD10998` (Kakudo rice bowl) and `CM-20/28/38`. Brien confirmed these
are Table Matters, and the Drive master agrees for KD10998 (§D1). **Brand wins
over the customer's vendor code.** So the August COURTS file splits: store 928
produces an SGPL invoice *and* an AGPL invoice (net $99.30) referencing the same
AR number.

**Edge case to decide (open question Q3):** if an outlet has $0 of AGPL
product in a month, we post one invoice, not an empty second one.

---

## 5. GST — the full answer

Your question was *"some report the sales with GST, some don't — how does the
app know?"* Here is the complete treatment.

### 5.1 There are three independent unknowns, not one

People conflate these and that is where GST errors come from:

| # | Unknown | Values | Consequence of getting it wrong |
|---|---|---|---|
| 1 | **Tax treatment** | inclusive / exclusive | 9% error on the whole invoice |
| 2 | **Amount basis** | retail gross / our net cost | 30–35% error (the commission) |
| 3 | **Explicit tax column** | present / absent | double-counting GST |

A file that says "Sales: 1,090.00" could legitimately mean **$1,000 ex-GST to
us**, **$1,090 ex-GST to us**, or **$708.50 to us after 35% commission**. No
amount of cleverness resolves that from the number alone.

**And it gets worse: the convention can differ *between columns of one file*.**
The COURTS file proves it (§A3):

| Column | Contents | Treatment |
|---|---|---|
| `Unit Price` | `4.90`, `19.90`, `75.00` | **GST-INCLUSIVE** retail |
| `CostPrice` | `2.92`, `11.87`, `48.17` | **GST-EXCLUSIVE** — what we bill |

So `tax_treatment` is **not a per-file flag. It is a per-column flag**, and the
profile format reflects that (`gst.columns` in `profiles/courts.yaml`). A
design that stores one boolean per customer cannot represent this file at all.

### 5.2 So the profile declares it — and then the app *proves* it

The profile is the source of truth. But a declaration nobody checks is just a
comment, so every run executes three independent proofs:

**Proof 1 — Internal consistency.** If the file has both a net and a gross
column, `gross / net` must land within 0.0005 of `1 + rate`. If the file has an
explicit tax column, `tax / net` must equal the rate. Any deviation = STOP.

**Proof 2 — The customer's own totals.** Almost every retailer statement has a
TOTAL row. Sum our parsed rows and compare. Mismatch beyond $0.02 = STOP.
This catches header-row drift, hidden rows, merged cells, and filtered ranges —
the actual causes of real-world spreadsheet errors.

**Proof 3 — Historical challenge.** Compute the implied unit price per SKU and
compare against what that SKU billed at last period. If a $2.98 wipe suddenly
implies $2.73 (a 9% drop), the file has flipped to inclusive and *the profile
is now wrong*. Flag it, don't silently follow either one.

Proof 3 is the one that saves you. A retailer changing their report format
without telling you is the most likely real failure, and this catches it in the
one way that matters: by noticing that the *money* moved, not that the *file*
changed.

**Worked example — Proof 1 on the real COURTS file.** Across all 159 rows:

```
CostPrice ÷ (Unit Price ÷ 1.09)  =  0.6496…0.6503   or   0.6998…0.7003
```

Every row lands on 0.65 or 0.70 within 0.0007. That single check simultaneously
confirms the 9% rate, the inclusive/exclusive split, *and* the commission tier —
and it would fail loudly the moment COURTS changed any of them.

**And note which proofs each customer actually has.** COURTS has Proofs 1 and 3.
Shell has **only Proof 3** — one money column, no totals row (§B3). The profile
records this explicitly (`proofs:`) so that a customer running on one check gets
a tighter variance guard and a longer draft-only period. Pretending all
customers are equally verifiable is how you get caught.

### 5.3 Rate table, not a constant

```yaml
gst_rates:
  - { from: 2007-07-01, to: 2022-12-31, rate: 0.07 }
  - { from: 2023-01-01, to: 2023-12-31, rate: 0.08 }
  - { from: 2024-01-01, to: null,       rate: 0.09 }
```

Rate is selected by the **period being invoiced**, never by today's date. This
matters the first time you restate an old month or issue a credit note against
a 2023 invoice — hardcoding `0.09` makes that silently wrong.

### 5.4 Reproduce Xero's arithmetic exactly

From F3, verified against live invoices:

```python
# EXCLUSIVE
line_tax  = round_half_up(line_net * rate, 2)      # per line
amount_tax = sum(line_tax for line in lines)       # then sum

# INCLUSIVE
line_net  = round_half_up(line_gross / (1 + rate), 2)
line_tax  = line_gross - line_net
```

The app computes the expected totals **before** calling Xero, then compares
against what Xero returns. A mismatch of even one cent means our model of Xero
is wrong, and that is a bug worth failing loudly on.

### 5.5 The commission GST question — flag for your tax agent

Your COURTS invoices net the commission *inside* your own sales invoice, with
GST reversed on the negative line (F1). Arithmetically it lands correctly:
`(278.18 − 97.38) × 9% = 16.28` ✓.

But mechanically, the retailer's commission is *their* supply to *you*, and
input tax is normally claimed against **their** tax invoice, not a negative
line on yours. This may be perfectly fine as an agreed net-settlement
arrangement — but it is a question for your tax agent, not for me.

**The app will replicate your existing practice by default.** I am flagging it,
not changing it. If your agent wants it restructured, it becomes a profile flag
(`commission_posting: netted | separate_bill`) and switches per customer with
no code change.

---

## 6. Invoice styles — and the $10.97 problem

From F1 you already run two styles, and the profile picks one. But the COURTS
file changed my recommendation for COURTS itself, so start there.

### 6.1 Do not calculate commission. Read the price.

Your COURTS invoices apply a **flat 35%** to a gross figure (F2). The file says
that is wrong. Five SKUs carry **30%**, not 35% (§A4):

`LS-9743-COAL GREY` · `MEGASTORE WAREHOUSE SALES` · `MOMO FAUX FUR` ·
`NORD RECTANGULAR` · `ROADSHOW SPECIAL BUY $20`

Because the mix differs by store, the *blended* rate ranges **31.78% – 35.05%**
across the 12 stores in one month. On this single file:

| Method | August total (ex-GST) |
|---|---|
| `Σ CostPrice × Qty` — what COURTS says it owes | **$1,127.72** |
| Retail ex-GST × 65% — current practice | $1,116.75 |
| **Under-billed** | **$10.97 — 0.97% of revenue** |

That is one customer, one month, on a small file. Annualised across COURTS'
consignment volume it is not a rounding error, and it runs one way only.

**So: `CostPrice` *is* the invoice price.** Commission stops being a
calculation and becomes an *assertion* — "the implied rate must be 30% or 35%;
anything else, stop and show a human". That is simultaneously more accurate,
simpler, and safer, because a wrong rate now surfaces instead of silently
applying.

The general principle, worth stating plainly:

> **Where the customer's file states what they will pay us, bill that. Only
> derive a price when the file doesn't contain one.**

### 6.2 The three styles

**`itemised`** — COURTS (recommended, changed from current practice), NTUC,
Ideal Parts, Horme:
- one Xero line per resolved SKU, transactions aggregated by SKU
  (159 COURTS rows → ~9 lines per store)
- `item_code` populated → your Xero inventory reports keep working
- description follows your existing convention: `{our_sku}: {name} - {barcode}`
- gives you per-SKU sell-through analytics that the summary style throws away

**`summary_plus_commission`** — Shell, Prime, and any customer whose file has no
cost price:
- line 1: gross sales ex-GST, account 6-1000
- line 2: `−(gross × rate)`, commission account, description "Commission"
- rate from the **agreement**, because it is not in the file

**`itemised_plus_commission`** — for customers who send SKU detail but report
only retail. Full line detail *and* the deduction.

Note the profile decides this per customer, so moving COURTS from style B to
style A is a one-line change plus a parallel-run month — not a rewrite.

### 6.3 What the app produces for the August COURTS file

12 invoices, one per store, referenced by the AR number read from the file:

```
SGPL  store 870  AR0116471   36 rows -> 9 SKU lines (incl. 3 returns)
                 net 102.20   GST 9.20   total 111.40
...
AGPL  store 928  AR0116479   KD10998, CM-20, CM-28, CM-38
                 net  99.30   GST 8.94   total 108.24

SGPL: 12 invoices   net 1,028.42   GST 92.57   total 1,120.99
AGPL:  1 invoice    net    99.30   GST  8.94   total   108.24
159 source rows -> 70 invoice lines, 13 invoices, 2 Xero organisations
```

Every AR number correct by construction, every commission rate checked, every
one of the 159 rows accounted for. This is not a mock-up — it is the output of
`prototype/courts_dryrun.py` run against the file you sent.

**And it already earned its keep.** My first hand-calculation of that GST total
was $101.49. Xero's per-line rounding makes it **$101.51** (§A7). Two cents,
found by a regression test rather than by a person, on the second calculation
anyone did. Multiply that across 12 customers and 12 months and you see why
Phase 0 is the GST engine and nothing else.

## 7. SKU resolution — the largest source of residual risk

Everything else in this system is arithmetic. This part is genuinely hard,
because customers use their own article numbers and rename things.

### The match ladder — strict order, stop at first hit

| # | Method | Confidence | Action |
|---|---|---|---|
| 1 | **Barcode / EAN exact** | certain | auto-accept |
| 2 | **`ProductAlias(customer, their_code)`** | certain | auto-accept |
| 3 | **Our SKU appears verbatim** | certain | auto-accept |
| 4 | Normalised description exact match | high | auto-accept, log |
| 5 | Fuzzy description ≥ 0.92 | medium | **queue for human**, never auto |
| 6 | LLM candidate suggestion | low | **queue for human**, never auto |
| 7 | No match | — | **HARD STOP** |

Steps 1–4 are deterministic and cover the steady state. Steps 5–6 exist purely
to make the human's job fast — they present three ranked candidates with
barcodes and last month's price, and one click both resolves the row *and*
writes a permanent `ProductAlias`.

### The non-negotiable rule

> **An unresolved row never becomes an invoice, and never silently disappears.**

The batch is blocked. This is the correct behaviour — an invoice that quietly
omits $4,000 of a customer's sales is far worse than an invoice that is one day
late. Every row in the file is accounted for as `invoiced`, `excluded (with
reason)`, or `blocking`. The three always sum to the file's row count, and the
app asserts it.

### Even COURTS needs the alias table — 41% of it

I assumed COURTS' `Model` column was our SKU. Running the prototype against the
real Drive master (§D3) says otherwise: **15 of 34 values are nicknames** —
`KYRO`, `POPCON`, `PORTASTOOL`, `MOMO FAUX FUR`, `MATTE 13L SINGLE TIER` — worth
$464.24 of the $1,127.72 file. A "match on Model" implementation would have
silently invoiced 59% and dropped the rest.

The fix is already in the ladder: COURTS' own `Item No_` (`IP201479`) is stable
and unique, so the alias is keyed on it (tier 2), and `Model` becomes a hint
that speeds up the one-time confirmation. Fifteen aliases, once.

### The name-only case (Shell) is the hard one

COURTS gives us `Model = OKN-7174` — tier 3, automatic, done. Shell gives us
`Table Matters - Everyday Chef 28CM Non-Stick Wok Pan - Sage` and nothing else
(§B4). Two traps in ten rows:

1. **`Table Matters Wok Pan Sage` ($25)** vs **`Table Matters - Everyday Chef
   28CM Non-Stick Wok Pan - Sage` ($35).** A fuzzy matcher scores these as the
   same product. The $10 price gap says they are not. This is the single
   clearest argument for why tiers 5–6 never auto-accept.
2. **`Pack of 8 HOUZE - Humipod 800ML`, `Quantity Sold = 1`.** One pack, or
   eight units? An 8× error on the line. ✅ Answered by the GoLabel master
   (§D4): `LS-9631*8` is a distinct pack SKU, so the alias points at it and the
   quantity is 1. The profile still detects `Pack of N` / `Set of N` and refuses
   to guess when no pack SKU exists.

Eight distinct strings, resolved once, and Shell becomes zero-touch.

### Getting to steady state

Month 1 will have real work: perhaps 50–150 aliases to confirm across all
customers. This is a one-time cost, and it is genuinely a one-time cost —
month 3 onward you should see only new product launches, typically 0–5 rows.

---

## 8. Robustness — "how robust can it be without error"

The honest answer has two halves, and the second half is the important one.

### 8.1 What can be made *structurally* impossible

These are not "unlikely". They cannot happen, because the code path does not
exist:

- ✅ Arithmetic errors (GST, extensions, commission, totals) — computed and
  cross-verified twice
- ✅ Wrong GST rate for a period — table lookup by period
- ✅ Typos like `Commissionj` (F7) — templated strings
- ✅ Wrong expense account (the 8-2001/8-2002 split, F7) — single profile value
- ✅ July/August description mismatches (F7) — one period variable renders both
  the reference and the description
- ✅ Duplicate invoices from a re-upload — idempotency key
- ✅ Truncated AR numbers (F7) — validated against a regex in the profile
- ✅ Inconsistent due dates within a batch (F7) — one rule per customer
- ✅ Silently dropped rows — the row-count assertion in §7
- ✅ Posting to the wrong Xero org — brand→entity routing, §4
- ✅ Rows lost to hidden/filtered spreadsheet rows — total reconciliation, §5.2

**Every one of the eight defects found in your live July 2026 batch (F7) falls
in this list.**

### 8.2 What remains, and how it's contained

| Residual risk | Why it can't be eliminated | Containment |
|---|---|---|
| Customer sends wrong data | We can't see their POS | Variance check vs prior period; total reconciliation |
| Genuinely new SKU | Nothing to match against | Hard stop, human resolves in ~15 s |
| Customer silently changes file layout | Outside our control | Header fingerprint + Proof 3 (§5.2) |
| Wrong contact chosen for a *new* outlet | Ambiguous by nature | New outlets always require explicit human mapping |
| Commercial terms changed verbally | Not in any file | Commission-rate drift check; effective-dated profiles |
| Xero API rejects/partially fails | Network reality | Idempotent retry + reconciliation sweep after every batch |

### 8.3 The layered controls

```
 1. Upload         sha256, virus scan, size/type check
 2. Fingerprint    header hash vs profile   -> STOP on drift
 3. Parse          typed, locale-aware ("1,234.56", "(123)" negatives)
 4. Reconcile      our sum vs their TOTAL   -> STOP on mismatch
 5. Resolve SKU    match ladder             -> STOP on unresolved
 6. Resolve outlet ContactLink registry     -> STOP on unknown
 7. Route          brand -> entity          -> split drafts
 8. Compute        GST + commission, twice, by two code paths
 9. Guardrails     variance, max total, negative net
10. PREVIEW        human sees every invoice, side by side with source rows
11. Post as DRAFT  Xero DRAFT, never AUTHORISED
12. Approve        human authorises in the app or in Xero
13. Sweep          re-read from Xero, confirm totals match our expectation
```

**Stage 11 is the safety net that makes the whole thing safe to deploy.** A
wrong DRAFT costs one click to delete. A wrong AUTHORISED invoice sent to NTUC
costs a credit note, an apology, and a GST amendment. Draft-first is
non-negotiable for at least the first three months.

### 8.4 Realistic expectation

- **Months 1–2** (parallel run, humans check everything): the app finds *your*
  errors, not the other way round. Expect it to catch several F7-class defects.
- **Month 3+**: posting/arithmetic error rate effectively zero. Human touches
  limited to new-SKU resolution and genuine data queries with customers.
- **Time**: a 40-outlet COURTS run goes from a day of copy-paste to roughly
  90 seconds of compute plus a 5-minute review.

I want to be precise rather than flattering: **the app will not be 100%
error-free, because your customers' files aren't.** What it will be is
*incapable of the silent error*. Everything it can't prove, it stops on.

---

## 9. Architecture

```
┌──────────────┐   upload   ┌───────────────────────────────────────┐
│  Web UI      │ ─────────► │  API (FastAPI)                        │
│  Next.js     │            │   ├── parser      (openpyxl/pandas)   │
│  + Tailwind  │ ◄───────── │   ├── resolver    (SKU, outlet)       │
└──────────────┘   preview  │   ├── gst engine  (Decimal only)      │
                            │   ├── router      (brand -> entity)   │
┌──────────────┐            │   ├── validator   (12 gates)          │
│ Postgres     │ ◄────────► │   └── xero client (2 tenants, OAuth2) │
│  + audit log │            └───────────────────────────────────────┘
└──────────────┘                          │
                                          ▼
                          ┌───────────────────────────────┐
                          │ Xero: AGPL tenant │ SGPL tenant│
                          └───────────────────────────────┘
```

**Stack recommendation**

| Layer | Choice | Why |
|---|---|---|
| Backend | Python 3.12 + FastAPI | best Excel tooling by a wide margin |
| Money | `decimal.Decimal`, `ROUND_HALF_UP` | **never float.** Non-negotiable. |
| Excel | `openpyxl` (+ `pandas` for shaping) | handles merged cells, hidden rows |
| DB | Postgres | needs real transactions + JSONB for profiles |
| Frontend | Next.js + Tailwind | review UI is the product; it must be fast |
| Xero | official `xero-python` SDK | OAuth2 PKCE, token refresh, rate limits |
| Hosting | single container, SG region | data residency; this is not a scale problem |
| LLM | Claude, onboarding + suggestions only | §1's ban list is enforced in code |

### 9.1 Yes — Xero has a proper API, and it replaces browser automation entirely

You asked whether Xero has an open API, as opposed to the Cowork browser
automation you have been using to open invoices. It does, and it is the right
foundation for this app:

| | Browser automation (Cowork) | Xero Accounting API |
|---|---|---|
| Mechanism | drives the Xero web UI | REST + OAuth 2.0, `POST /api.xro/2.0/Invoices` |
| Reliability | breaks when Xero changes a button | versioned, stable since 2011 |
| Speed | one invoice per screen sequence | **up to 50 invoices per call** |
| Multi-org | log out, log in | one call with a different `Xero-Tenant-Id` header |
| Bills (Yue Hwa) | separate UI flow | same endpoint, `Type: ACCPAY` |
| Attach the source file | manual | `PUT /Invoices/{id}/Attachments` — the customer's Excel/PDF rides on the invoice |
| Idempotency | none | send our own `InvoiceNumber`/`Reference`; re-posts are detectable |
| Draft-first | possible | `Status: DRAFT` in the payload |
| Cost | — | **free** to register at developer.xero.com |

Practical shape:

- Register one **web app** at developer.xero.com. Both AGPL and SGPL are
  connected to it once, by someone who is an adviser/user in each org. After
  that the app holds a refresh token per tenant.
- Scopes needed: `accounting.transactions` (invoices, bills),
  `accounting.contacts`, `accounting.settings.read` (account codes, tax rates),
  `accounting.attachments`, `offline_access` (refresh tokens).
- Official SDKs exist; `xero-python` is mature and handles token refresh.
- Reads are useful too: pull the contact list to build the alias registry, pull
  posted invoices to build the golden test set, pull `TaxRates` so the 9% is
  confirmed from the org rather than hard-coded.

Note that the Xero connector available in *this* session is read-only and sees
only SGPL — good for analysis, not for the app. The app needs its own OAuth
registration.

### 9.2 Xero specifics that will bite if unplanned
- Two tenants = two token sets = a `tenant_id` on every single call.
  There is no "current org"; passing the wrong `Xero-Tenant-Id` posts to the
  wrong company with no error.
- Rate limit: 60 calls/min, 5,000/day per tenant. A 40-outlet batch is fine;
  batch the `POST /Invoices` endpoint (up to 50 per call) anyway.
- Access tokens expire in 30 min, refresh tokens in 60 days — a customer who
  invoices monthly will find the connection dead. **Schedule a weekly refresh
  ping**, or the app breaks the one week a year you need it.
- Use `POST /Invoices` with `Contact.ContactID` (never `Contact.Name` — Xero
  will happily *create* a duplicate contact from a name).

---

## 10. What documents I need from you

Ordered by how much they unblock. Items 1–4 are the critical path.

### Tier 1 — cannot start without these

**1. Three months of real Excel statements from each customer**
✅ **Received: COURTS (Aug 2026) and Shell (Aug 2026)** — both fully parsed, and
they produced `profiles/courts.yaml` and `profiles/shell.yaml` plus every
finding in `02-source-files.md`. That is exactly the loop; please repeat it for
the rest.

Still needed: Giant, Cold Storage, NTUC, Sheng Siong, Isetan, Yue Hwa, BHG —
and **two more months each for COURTS and Shell**. One file tells me the layout;
three tell me what *varies* (new columns, months with returns, promo lines,
outlet openings, the month someone merges cells). Raw and unedited — send the
ugly ones especially.

**2. Product master export**
🟡 **Partly found.** Two masters in Drive, both read in full (§D): `Master Price
List - For Ravi.xlsx` (Jun 2024, 2,127 active SKUs, has BRAND + barcode + cost
tiers) and `GoLabel Master Database 2025 (Updated).xlsx` (Jan 2026, 1,431 SKUs,
has Brand + barcode + RSP). Neither has `CM-20/28/38`. **Still needed:** whichever
list is current for 2026 SKUs — or confirmation that Xero Items is the source
of truth and the app should union Drive + Xero.
→ *Brand is the field that routes AGPL vs SGPL. Both masters have it.*

**3. Price lists per customer**
The agreed net price per SKU per customer, **with effective dates**. If prices
differ per outlet, say so.
→ *For itemised customers, this — not the file — sets the invoice price.*

**4. Commission / margin terms per customer**
Rate, whether it applies to gross or net, whether GST applies to it, and when
it last changed.

Status from the evidence so far:
- **COURTS** — the file gives exact cost prices, so no rate is needed to
  invoice. But I need to know whether the **30% tier is intentional** (§A4) and
  whether `LS-9743-COAL GREY` at 30% vs `LS-9743-WHITE` at 35% is a real deal or
  a COURTS data error.
- **Shell** — ✅ **30%**, confirmed by Brien. Recorded in `profiles/shell.yaml`
  with an effective date. Brien also asked for a **Commission & Terms tab** in the
  app where rates can be entered per customer — see §11a.
- **Prime** — derived as 30% from your invoices; please confirm.
- Everyone else — needed.

### Tier 2 — needed before go-live

**5. Outlet ↔ Xero contact mapping**
For each chain, the definitive list of outlets you invoice and which Xero
contact each maps to, **per entity**. This is where you resolve the F5
duplicates — including deciding which "Courts Tampines" contact is correct.
→ *I can pre-generate this as a spreadsheet from your Xero contacts for you to
tick through; that turns a nasty job into an hour.*

**6. Ten past invoices per customer, with the source file that produced them**
The single most valuable artefact in this list. It gives me a **golden test
set**: run the app on the old file, compare to the invoice you actually issued,
require an exact match. That is how the app earns trust before it touches
anything live.

**7. Chart of accounts** (both entities)
Revenue and commission account codes. I've seen 6-1000, 8-2001, 8-2002, 8-2006
in use — I need to know which is intended for which customer.

**8. Payment terms per customer**
Your data shows both "end of month + 2" and "end of following month" in the
same batch (F7). Which is right, per customer?

### Tier 3 — improves quality

**9. Consignment/trading agreements** — authoritative source for commission,
payment terms, returns handling.
**10. GST registration details** for both entities, and confirmation of the
commission treatment in §5.5 from your tax agent.
**11. Any known-problem list** — customers who habitually report wrongly, SKUs
that get confused, anything you currently check by hand.
**12. Email samples** — if you later want the app to pull files straight from
the customer's monthly email.

### The fastest possible start

**COURTS is already 80% specified.** I have the file, the profile, the store↔AR
mapping, the SKU list and the exact expected output ($1,127.72 net across 12
invoices). To finish it I need only:

1. **Product master with brand** — to route the Kakudo/CM- lines (Q12) and
   populate `item_code`
2. **Store code → Xero contact mapping** for the 12 codes
   (`867, 869, 870, 874, 875, 876, 877, 882, 921, 927, 928, 929`) — and a
   decision on the duplicate Courts Tampines contacts (F5)
3. **The July 2026 file** — so I can reproduce the July invoices you already
   issued and prove the engine to the cent

That is a short list, and it is the whole critical path to a working pilot.

---

## 11. Build plan

| Phase | Scope | Output | Est. |
|---|---|---|---|
| **0** | Schema, profile format, GST engine + golden tests | GST engine proven against your real invoices to the cent | 1 wk |
| **1** | Parser, SKU resolver, product master import | CLI: file in → invoice JSON out, no Xero | 1–2 wk |
| **2** | Xero integration, 2 tenants, DRAFT posting, idempotency | COURTS live, draft-only | 1–2 wk |
| **3** | Review UI: preview, SKU resolution queue, approve | Non-technical staff can run it | 2 wk |
| **4** | Onboard remaining customers; AI-assisted onboarding wizard; **PDF intake + Bills (Yue Hwa)** | All 8+ chains live | 2–3 wk |
| **5** | Credit notes, variance dashboards, email intake | Full monthly close in the app | 2–3 wk |

**~9–13 weeks to full coverage; ~4 weeks to COURTS running live in draft
mode.** Phases 0–2 are the risky part and they are front-loaded deliberately —
if the GST engine can't reproduce your existing invoices exactly, we find out
in week 1, not week 9.

**Parallel-run policy:** for the first two months every customer runs both
ways — app and manual — and the app's output is *compared*, not trusted. Cut
over per customer, only after a clean month.

---

## 11a. Requested: a Commission & Terms tab

Brien asked for a place in the app to fill in commission rates rather than
editing YAML. Agreed — this is the right shape:

- One row per customer (optionally per brand or per SKU group, because COURTS
  runs 30% and 35% side by side).
- Fields: rate, applies-to (retail ex-GST / retail inc-GST / cost), account
  code, **effective from**, note. Old rows are never deleted; a new row with a
  later date supersedes.
- Editing a rate writes a new version of the customer profile and logs who
  changed it. The run for any period uses the rate effective for *that* period.
- Same tab carries payment terms and invoice style, since they change together.

The YAML stays as the storage format underneath; the tab is a form over it.
Builds in Phase 3 with the rest of the review UI.

## 12. Questions I need you to answer

The two files answered several of my original questions and raised sharper ones.

### Blocking — all three answered on 2026-09-06

1. ✅ **Shell commission rate — 30%.** Recorded. Account code still to confirm.
2. ✅ **AGPL Xero access** — Brien can authorise the app. Identity: Audrey Global
   Pte Ltd (§C2).
3. ✅ **COURTS Kakudo/CM lines are Table Matters → AGPL.** Brand wins over the
   customer's vendor code. Rule adopted: when a brand is in doubt, look it up in
   the Drive master price list (§D).

### New blocker surfaced by the master list

3b. **Which product master is current?** The two in Drive are Jun 2024 and Jan
    2026 and neither has `CM-20/28/38` (§D2). Is Xero Items the source of truth
    for new SKUs, or is there a newer list?

### Needed before the COURTS pilot goes live

4. **Fifteen COURTS aliases** (§D3) — `KYRO`, `POPCON`, `MATTE 13L SINGLE
   TIER`… → our SKU. I can pre-fill likely matches from the master; you confirm.
4a. **Store code → Xero contact** for the 12 COURTS codes, and **which "Courts
   Tampines" contact is correct** — `368f74f9…` or `b32222af…`? Both were
   invoiced in July 2026 (F5). Shall I generate the full duplicate report across
   all chains? It is about an hour of your time to tick through and it removes
   an entire class of error permanently.
5. **Q11 — is the COURTS 30% tier intentional?** `LS-9743-COAL GREY` at 30% vs
   `LS-9743-WHITE` at 35% (§A4). Real deal, or COURTS data error? Either way the
   app bills what the file says — I just need to know whether to alert you.
6. **Do you accept moving COURTS to `CostPrice`-based invoicing?** It recovers
   the 0.97% (§6.1) but changes what the invoice looks like to them.
7. **Shell `Pack of 8` / `Set of 8`** — is `Quantity Sold = 1` one pack or eight
   units (§B4)? An 8× error either way.
8. **Payment terms per customer.** Your data shows both "end of month + 2" and
   "end of following month" in the same batch (F7). Which is right, per customer?

### Design decisions

9. **Zero-value entity split** — if an outlet sells no AGPL product in a month,
   skip the invoice or issue a nil one?
10. **Invoice numbering** — your `SI2606…` prefix appeared on July and August
    invoices. Should the app control numbering, or let Xero auto-number?
11. **Returns** — COURTS returns net down within the same store's invoice (§A5).
    Is that right for every customer, or do some need credit notes?
12. **Who approves?** Does the uploader also authorise, or do you want
    two-person approval above a threshold?
13. **Non-Excel customers** — ✅ answered: Yue Hwa sends PDF only (§C). Anyone
    else?
15. **Yue Hwa sales source.** The statement shows `Sales Amt 1,087.52` for
    Households at China Town, but no SKUs, no GST flag, no commission. Do you
    receive a separate itemised report, or is this figure what you invoice
    from — and at what rate? And do you currently record their loyalty
    recharge as a **bill** in AGPL (input GST claimable) or net it?
14. **"Any other type of invoices"** — do you need PDF invoices outside the Xero
    template, or a portal upload format? Several chains require their own.

## 13. Recommendation

Build it, and start with COURTS.

The case no longer rests on argument. Two files, both from August 2026, produced:

- **eight distinct defects** in one month of live invoices (F7) — wrong account
  codes, a truncated AR number, July/August mismatches, `Commissionj`,
  inconsistent due dates, and two different contacts for one Tampines store
- **$10.97 of under-billing on a $1,128 file** — 0.97%, structural, one
  direction only (§6.1)
- **a cross-entity file that would have booked Houze revenue into AGPL** (§B1),
  in the very first Table Matters file I looked at
- **a customer whose monthly paperwork is a bill to us, in PDF** (§C) — a third
  flow the design has to carry from the start

Every one of those is a class of error this design makes structurally
impossible, and none of them is the kind a careful person catches reliably at
2am on a month-end.

**The first move is narrow and concrete: COURTS, draft-only, four weeks.** I
already know the expected answer — $1,127.72 net, $101.51 GST, 13 invoices
across two organisations. The three blocking questions are answered. Give me the
15 COURTS aliases, the store mapping, and the July file, and the pilot either
reproduces your July invoices to the cent or it doesn't. That is proof
rather than promises, and everything after it is repetition.
