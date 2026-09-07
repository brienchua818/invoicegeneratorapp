# Consignment Invoice Generator

Turns monthly consignment sales files from retailers (COURTS, NTUC, Giant, Cold
Storage, Sheng Siong, Isetan, Yue Hwa, BHG, Shell stations …) into Xero invoices
across two organisations — **AGPL** (Audrey Global Pte Ltd — Table Matters) and
**SGPL** (Sheldon Global Pte Ltd — Houze, Painting Matters, Greenshield).

**Status: design phase.** No app yet. What is here is a plan grounded in real
data, plus a runnable proof of the riskiest part.

## Read in this order

| Doc | What it is |
|---|---|
| [`docs/00-findings.md`](docs/00-findings.md) | What the live SGPL Xero org actually contains — invoice styles, GST arithmetic, contact duplication, and eight defects found in one month of posted invoices |
| [`docs/02-source-files.md`](docs/02-source-files.md) | Full analysis of four real customer documents: COURTS (xlsx), Shell (xlsx), Yue Hwa (PDF), Prime (scanned PDF, both entities) |
| [`docs/03-master-price-list.md`](docs/03-master-price-list.md) | The product master in Drive: structure, per-customer alias columns, and how the app uses it |
| [`docs/01-plan.md`](docs/01-plan.md) | The design: how customers are "taught", GST, entity routing, robustness, Xero API, build plan, and the questions that need answering |
| [`docs/profiles/`](docs/profiles/) | Customer profiles: COURTS, Shell, Prime (consignment, from real files); NTUC FairPrice (SOR, skeleton) |

## Run the proof

```bash
pip install openpyxl
python prototype/gst.py                       # GST engine vs live Xero invoices
python prototype/courts_dryrun.py <file.xlsx> [master.xlsm]  # COURTS file -> invoices per entity
```

`gst.py` asserts its output against two real posted invoices (one GST-exclusive,
one GST-inclusive). `courts_dryrun.py` turns the August COURTS file into the invoices it should
produce — **net $1,127.72 · GST $101.51 · $1,229.23** — and, given the master
price list, routes each line to AGPL or SGPL by brand (13 invoices, 2 orgs).

## The three things that matter most

1. **Nothing is inferred at runtime.** Each customer gets a profile that is
   written once with human confirmation; every month after that is deterministic
   arithmetic. AI proposes mappings at onboarding — it never decides a number.
2. **Routing is by brand, not by customer.** One file can span both Xero orgs.
   Proven: the Shell "Table Matters" file contains a Houze line (SGPL) alongside
   Table Matters lines (AGPL).
3. **Where the customer's file states what they will pay, bill that.** The
   COURTS file carries exact cost prices; the current flat-35% approximation
   under-bills by 0.97%.
