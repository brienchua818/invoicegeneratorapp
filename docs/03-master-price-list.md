# The Master Price List — the app's product source of truth

**File:** `Master Price List 4.0 - 2025 R1.xlsm`
**Where it lives:** Google Drive file `1kfa_KvpN8klUX1HhbIFZFTXpFN4N5V_D`
(https://docs.google.com/spreadsheets/d/1kfa_KvpN8klUX1HhbIFZFTXpFN4N5V_D)
Mirrors the shared-drive path recorded in its own `Config` sheet:
`G:\Shared drives\SHELDON GLOBAL PTE LTD (Shared Drive)\SHELDON GLOBAL PTE LTD\SALES\Pricelist (Confidential)\`
**Owner:** Brien Chua · **Last modified:** 2026-09-04 · **Size:** 6.6 MB, macro-enabled
**Read in full** on 2026-09-06. Supersedes the two older lists described in
`02-source-files.md §D` (Jun 2024 "For Ravi", Jan 2026 GoLabel).

> Brien's standing instruction: *when a product's brand or price is in doubt,
> this file decides.*

---

## 1. What is in it

18 sheets. The ones the app cares about:

| Sheet | Rows | Role |
|---|---|---|
| **`MasterPriceList`** | **3,810 SKUs × 121 cols**, header on **row 4** | The master. Everything below refers to it. |
| `MasterPriceList_SaleStaff` | 1,343 | Filtered view: Available SKUs, 40 cols |
| `MasterPriceTable_SaleStaff_Disc` | 2,387 | Filtered view: Discontinued |
| `Barcodes` | 13,500 rows → 7,241 EAN→Model | GS1 barcode register, incl. retired codes |
| `Brands` | 42 | Brand list with priority order |
| `TaxRate` | 1 | `GST = 9` |
| `Categories`, `Colors`, `Materials`, `Suppliers` | — | Reference lists |
| `HOUZE - 2026 Focus Items` | 162 | Promo bundles (not needed for invoicing) |

**Status split:** 1,014 `Available` · 2,796 `Discontinued`.
**Brand split (all 3,810):** HOUZE 1,889 · TABLE MATTERS 1,526 · LIAO 90 ·
ecoHOUZE 84 · Finder 68 · Eotia 48 · Sundis 22 · Crash Baggage 18 · Creative
Polybag 15 · Greenshield 11 · Lifty Tech 8 · Tramontina 4 · Xiaomi 2 · (blank) 25.

## 2. The columns the app uses

### Identity & routing
`SKU` · `MODEL PREFIX` · `MODEL NO` · `COLOR` · **`BRAND`** · `CATEGORY` ·
`SUB-CATEGORY` · `LONG NAME` · `SHORT NAME UPTO 40 CHARACTERS` · **`STATUS`** ·
**`BARCODE`**

→ `BRAND` routes the entity: `TABLE MATTERS → AGPL`, everything else → `SGPL`.
→ `BARCODE` is match-ladder tier 1.

### Per-customer alias + cost — this is the alias table

The master already carries, per row, each retailer's own article code and the
agreed cost to that retailer. **These columns are the `ProductAlias` table the
plan describes (§7), and they already exist.**

| Customer | SKU column | Cost column | Populated (SKU / cost) |
|---|---|---|---|
| COURTS | `COURTS SKU` (`IP138419`…) | `COURTS Cost (30-35%）` | **914 / 220** |
| NTUC | `NTUC SKU` (`13193300`…) | `NTUC COST` | 542 / **0** |
| NTUC Online | `NTUC Online SKU` | `NTUC Online COST` | 1,339 / — |
| Giant | `GIANT SKU` (`5064411`…) | `GIANT COST` | 524 / 115 |
| Yue Hwa | `Yue Hwa SKU` (`4000012657`…) | `Yue Hwa COST` | 643 / **0** |
| BHG | `BHG SKU` (`1091804`…) | `BHG COST (35%)` | 446 / 326 |
| Sheng Siong | `Sheng Siong SKU` (`953287`…) | `Sheng Siong COST (35%)` | 14 / 6 |
| Gain City | `Gain City SKU` (`T0166605`…) | `Gain City COST (36%)` | 175 / — |
| RedMart | `REDMART SKU` | `REDMART COST (25%)` | 1,659 / — |
| Watsons | `Watsons PLU` | — | 621 / — |
| Amazon | `AMAZON ASIN #` | `AMAZON COST(3)` | — |

**The commission schedule is in the column headers:** COURTS 30–35%, BHG 35%,
Sheng Siong 35%, Gain City 36%, RedMart 25%. These match what was derived
independently from the COURTS file (§A4) and the Xero invoices (F2).

### Pricing
`ACTUAL LANDED COST` · `COST TO RELATED COMPANIES (SGD)` · `CURRENT COST TO TGG
(SGD) (Mark up 35%)` · `RSP (SGD)` · `TIER 1/2/3 RSP (SGD)` · `Retail RSP (SGD)`
· `GENERAL TRADE (GP%) 35%` · `NORMAL DISCOUNT RATE (35%)` / `(45%)`

## 3. What the COURTS file looks like against it

Running `prototype/courts_dryrun.py` with this master as the second argument
(match ladder: `Item No_` → `COURTS SKU`, then `Model` → `SKU`):

- **`COURTS SKU` column resolves 11 of 36 distinct COURTS articles**, including
  every nickname the older lists could not: `MATTE 5.5L/13L/25L/35L SINGLE TIER`
  → `MS-2261/2262/2263/2264-CLEAR`, `NORD RECTANGULAR` → `CS-3122-GREY`.
- `Model = SKU` resolves a further ~13 (`OKN-*`, `LS-*`, `KD10998`).
- **Still unresolved: 12 articles** — `IP201581/82/84` (KYRO ×3 colours),
  `IP209537` (POPCON), `IP201484` (PORTASTOOL), `IP198842` (KRUSTY drying rack),
  `IP215623/25` (MOMO FAUX FUR ×2), `IP218543/44/45` (**CM-20/28/38**, not in
  the master at all), `IP190733` (ROADSHOW SPECIAL BUY $20), `IP195376`
  (MEGASTORE WAREHOUSE SALES).

The last two are event/promo lines rather than products. The rest exist in the
master as products but their `IP` codes are not yet filled into `COURTS SKU`.
**So the alias work for COURTS is: fill ~10 cells in the master.** That is the
whole one-time cost, and it is done in a file the team already maintains.

### One cost discrepancy caught immediately
`IP138548` → `LN-5182-BEIGE`: master `COURTS Cost` = **10.27**, COURTS file
`CostPrice` = **10.67**. Either the master is stale or COURTS changed the price.
This is exactly the Proof-3 class of check the app runs every month.

## 4. How the app should use it

1. **Pull, don't upload.** The Drive API can read this file on a schedule; the
   app should refresh its `Product` and `ProductAlias` tables from it nightly,
   keyed on Drive file ID, and log the file's `modifiedTime` with every batch.
2. **Union with Xero Items** for SKUs that appear in Xero before they reach the
   master (the `CM-*` case), and flag the gap back to whoever maintains the
   master.
3. **Treat the per-customer SKU columns as the alias table**, and the per-
   customer cost columns as the expected-price check. When a customer's file
   carries its own cost (COURTS), *bill the file* and *assert against the
   master*; when it doesn't (Shell, Yue Hwa), *bill from the master* using the
   commission in the header.
4. **Route by `BRAND`.** The 25 blank-brand rows must be fixed or excluded —
   a blank brand cannot be routed.
5. **Transport note.** The file is 6.6 MB and the Drive connector used in this
   session could not download it (payload too large); it had to be uploaded
   directly. The app should use the Drive API's `files.get?alt=media` with a
   service account, which has no such limit.
