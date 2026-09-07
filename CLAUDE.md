# Project memory — consignment invoice generator

Read `docs/01-plan.md` for the design. The facts below are the ones a future
session must not re-derive.

## Entities and routing
- **SGPL** = Sheldon Global Pte Ltd (UEN 201423985K). Brands: HOUZE, ecoHOUZE,
  Greenshield, Painting Matters, LIAO, Finder and all other non-TM brands.
- **AGPL** = Audrey Global Pte Ltd (Yue Hwa consignor code CC0414; address
  #03-08A Plaza 8 @ CBP, 1 Changi Business Park Crescent, S486025). Brand:
  **TABLE MATTERS** only.
- **Routing is by product BRAND, never by customer or by the customer's vendor
  code.** One customer file can produce invoices in both Xero orgs (proven: the
  Shell "Table Matters" file and the COURTS file both do).
- Kakudo (`KD…`) and `CM-20/28/38` are Table Matters → AGPL (confirmed by Brien).

## The product master — source of truth
- `Master Price List 4.0 - 2025 R1.xlsm`, Google Drive id
  `1kfa_KvpN8klUX1HhbIFZFTXpFN4N5V_D`, owner Brien, maintained on the SGPL
  shared drive under `SALES/Pricelist (Confidential)/`. Details: `docs/03-master-price-list.md`.
- Sheet `MasterPriceList`, **header row 4**, 3,810 SKUs, 121 columns.
  Key columns: `SKU`, `BRAND`, `STATUS` (Available/Discontinued), `BARCODE`,
  `LONG NAME`, and per-customer alias/cost pairs: `COURTS SKU` /
  `COURTS Cost (30-35%）`, `NTUC SKU`, `GIANT SKU`, `Yue Hwa SKU`, `BHG SKU` /
  `BHG COST (35%)`, `Sheng Siong SKU`, `Gain City SKU`, `REDMART SKU`, `Watsons PLU`.
- **The per-customer SKU columns are the alias table.** When a customer article
  is unknown, the fix is to fill that cell in the master, not to build a side table.
- When brand or price is in doubt, this file decides (Brien's rule).
- The file is 6.6 MB; the Drive MCP connector cannot download it. Ask for a
  direct upload, or use the Drive API with a service account in the app.
- Older lists (`Master Price List - For Ravi.xlsx` 2024, `GoLabel Master
  Database 2025`) are superseded; do not use them.

## Two business models — never conflate them
- **Consignment** (post-sale): the customer's monthly sales report triggers an
  invoice for what sold; commission applies; reference = AR no. / period;
  idempotency = (entity, customer, outlet, period). COURTS, Shell, Yue Hwa, Prime.
- **SOR / sale-or-return** (pre-dispatch): the customer's **PO** triggers an
  invoice at delivery for what we ship, at our cost price, no commission;
  reference = **PO number** (NTUC's are 8 digits); date = delivery date;
  idempotency = (entity, customer, PO no.); delivery order accompanies goods;
  returns come back as credit notes. **NTUC FairPrice is SOR, not consignment**
  (Brien, 2026-09-07). Ideal Parts and Horme are PO-referenced too.
- Each profile carries `mode: consignment | sor`. **Classification (Brien,
  2026-09-07): every customer is consignment except NTUC FairPrice.**
- `NTUC COST` in the master is empty — SOR pricing for NTUC is unresolved.

## Commission and terms (confirmed)
- COURTS: per-SKU, 35% standard / 30% on some lines; the file's `CostPrice`
  is authoritative — bill it, verify the implied rate.
- Shell stations: 30% (Brien, 2026-09-06), on retail ex-GST. Invoice the dealer
  company per station, matched on the `\d{3}_\d{2}` site code in the contact name.
- Prime Supermarket: 30%, printed on Prime's consignment report; vendor codes
  A050 = AGPL, S119 = SGPL; report is a scanned PDF (OCR + rotation needed);
  Net Sales are GST-exclusive; invoice per entity at HQ level, commission to 8-2006. BHG / Sheng Siong: 35%,
  Gain City 36%, RedMart 25% (from master headers). Rates live in the profile
  with effective dates; the app will expose them in a Commission & Terms tab.
- Yue Hwa sends PDFs and bills *us* a 5% loyalty recharge (+GST) → a Xero
  **bill** in AGPL, not netted.

## GST
- 9% since 2024-01-01 (8% in 2023, 7% before). Select by invoice period.
- Xero rounds **per line**, half-up, then sums. `prototype/gst.py` asserts this
  against two real posted invoices. Never use invoice-level rounding.
- Treatment is **per column**, not per file: COURTS `Unit Price` is GST-inclusive
  retail, `CostPrice` is GST-exclusive.

## Xero conventions observed in SGPL
- Revenue account `6-1000`; commission expense `8-2002` (COURTS), `8-2006` (Prime).
- Line description style: `{our_sku}: {product name} - {barcode}`.
- Contacts are per outlet and heavily duplicated; always post by `ContactID`,
  never by name. Two live "Courts Tampines" contacts exist (`368f74f9…`, `b32222af…`).
- Invoice numbers `SI` + `YYMM` + seq, but the month segment is unreliable.

## Working rules for this repo
- Money is `decimal.Decimal`, `ROUND_HALF_UP`. Never float.
- Nothing inferred at runtime: profiles in `docs/profiles/*.yaml` declare
  everything; an unresolved SKU or outlet **blocks** the batch.
- Post to Xero as **DRAFT** only until Brien says otherwise.
- Default branch is `main`; work on feature branches and open draft PRs.
