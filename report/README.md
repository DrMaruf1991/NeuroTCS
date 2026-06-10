# NeuroTCS Audit Report generator

Professional PDF report over a NeuroTCS audit. Presentation layer only -- reads
the signed *.bundle.json + *.flags.csv and reproduces values/citations verbatim;
does not touch the verified core.

## Usage
    pip install reportlab pandas
    neurotcs audit cohort.csv --allow-no-dates --confirm-assays --csv -o audit_out
    python report/neurotcs_report.py --bundle audit_out/cohort.bundle.json \
        --flags audit_out/cohort.flags.csv --out cohort_report.pdf --title "..."
Add --answer-key / --hard-negatives for a benchmark reconciliation page.

Software-audit output -- not clinical validation evidence.
