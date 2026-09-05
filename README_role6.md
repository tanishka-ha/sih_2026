# Role 6 — Synthetic Data + Evaluation Metrics

This folder is your whole deliverable for Milestone 1 (and most of what
you'll need later for precision/recall numbers in the pitch).

## What's inside

| File | What it does |
|---|---|
| `generate_dataset.py` | Generates 20 synthetic scholarship application bundles (10 clean, 10 defective) as images + PDFs, with full ground truth. **No Faker needed** — has its own tiny built-in name generator, so it works with zero internet. |
| `evaluate.py` | Once Roles 1–4 have something running, feeds their output back against the ground truth and prints precision/recall/F1 — the numbers for your pitch deck. |
| `requirements.txt` | The 3 packages you need: Pillow, reportlab, numpy. |
| `dataset/` | Already generated for you (see below) — hand this to Person 1 and Person 3 today. |

## What's already been generated for you

I ran the generator already. `dataset/` contains:

- **20 applications** (`APP-2026-0001` ... `APP-2026-0020`), each with 6
  documents: `income_certificate.jpg`, `category_certificate.jpg`,
  `marksheet.jpg`, `id_proof_front.jpg`, `id_proof_back.jpg` (a realistic
  card-style ID with photo box, formatted ID number, address, and a
  QR-style block on the back), `bank_proof.jpg`, plus a combined
  `bundle.pdf`. The ID card carries a visible "SPECIMEN - SYNTHETIC TEST
  DATA" watermark and a footer disclaimer, so it looks realistic for
  OCR/layout testing but can never be mistaken for, or reused as, a real
  identity document.
- **10 clean** applications, **10 defective** with exactly the mix your plan
  specified: 1 expired certificate, 2 name typos, 2 tampered income amounts,
  5 duplicate certificate numbers.
- **~17% of individual documents** also have a random "hard mode" scan
  defect layered on top (angled scan, blur, or low-res) — regardless of
  whether that application is otherwise clean or defective. This is what
  Person 1 (OCR) should stress-test against *this week*, per the plan's
  "someone needs to test OCR now" urgency.
- `dataset/ground_truth.json` — the answer key: exact fields, which doc is
  tampered and its bounding box, which cert numbers are duplicated, which
  name is the typo, and the exact flags a correct system should raise.
- `dataset/ground_truth_summary.csv` — same thing, one row per application,
  quick to skim in Excel/Sheets.

You can hand `dataset/` to Person 1 and Person 3 immediately without
running anything yourself.

## Step-by-step: running this yourself in VS Code

You only need to do this if you want to **regenerate** the dataset (e.g.
change the number of applications, add more defect types) or **run the
evaluator** once the pipeline exists.

### 1. Install Python (if you don't have it)
Download from https://www.python.org/downloads/ (3.10+ is fine). During
install on Windows, tick **"Add Python to PATH"**.

### 2. Open this folder in VS Code
`File → Open Folder...` → select this `role6` folder.

### 3. Open a terminal inside VS Code
`` Terminal → New Terminal `` (or `` Ctrl+` ``).

### 4. Create a virtual environment (keeps packages isolated)
```bash
python -m venv venv
```
Activate it:
- **Windows:** `venv\Scripts\activate`
- **Mac/Linux:** `source venv/bin/activate`

You'll know it worked because your terminal prompt now starts with `(venv)`.

### 5. Install dependencies
```bash
pip install -r requirements.txt
```

### 6. Run the generator
```bash
python generate_dataset.py
```
This creates/overwrites the `dataset/` folder. It prints a summary when done.
The dataset is **reproducible** — running it again gives you the exact same
20 applications (there's a fixed random seed), so everyone's ground truth
stays in sync.

### 7. (Later) Run the evaluator
Once someone gives you a `system_output.json` (see the format documented at
the top of `evaluate.py`):
```bash
python evaluate.py dataset/ground_truth.json system_output.json
```
Until then, you can preview the report format with simulated results:
```bash
python evaluate.py --demo
```
Both write a full `evaluation_report.json` you can screenshot or graph for
the pitch deck.

## Handing off to the team

- **Person 1 (OCR):** point them at `dataset/*/*.jpg` and `dataset/*/bundle.pdf`.
  Ask them to specifically try the ones flagged `"scan_quality": "rotate"` /
  `"blur"` / `"lowres"` in `ground_truth.json` first — that's your early
  warning on whether OCR accuracy is good enough.
- **Person 2 (rules engine):** `ground_truth.json`'s `expected_flags` field
  is exactly what their rules engine should reproduce. Use it to unit-test
  their fuzzy-matching thresholds (typo cases are tuned to land in the
  80–95% similarity band on purpose).
- **Person 3 (forensics):** the 2 `tampered_amount` applications have a
  known `tampering_bounding_box` in ground truth — that's the exact region
  their ELA script should localize.
- **Person 4 (backend):** once their API is live, dump its output into the
  `system_output.json` format and hand it to `evaluate.py`.

## Next for you (Role 6)

1. Today: hand off `dataset/` (done — see above).
2. This week, in parallel: start drafting pitch deck slides — problem,
   4-layer architecture, and a placeholder slide for the precision/recall
   table (`evaluation_report.json` will fill it in once the pipeline exists).
3. Once Roles 1–4 integrate (Milestone 5), run `evaluate.py` for real and
   drop the numbers into the deck.
4. Optional, if there's time: regenerate a **second, larger** dataset
   (e.g. 50–100 applications) closer to the finale for a more convincing
   sample size — just increase the defect counts and total count in
   `generate_dataset.py`'s `main()` function.
