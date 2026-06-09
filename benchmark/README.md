# NeuroTCS AD Challenge -- synthetic benchmark generator

Reproducible, citation-anchored synthetic AD-cohort generator for testing the
NeuroTCS auditor end to end. SOFTWARE TEST HARNESS only -- proves the detector
behaves correctly against known-injected errors. NOT clinical validation
evidence (no Arm A flag-precision on DUA-gated data).

## Usage
    pip install numpy pandas
    python generate_benchmark.py --seed 20260609 --subjects 450 --out .

Produces NeuroTCS_AD_Challenge_Dataset.csv + AnswerKey.csv + HardNegatives.csv
(deterministic: same seed => identical files).

## Acceptance test
    neurotcs audit NeuroTCS_AD_Challenge_Dataset.csv --allow-no-dates --confirm-assays --csv -o audit_bench
Expected: staging_clinical and staging_biological each catch 6/6 regressions,
zero false positives on the 11 hard-negatives. Every error type is anchored to
Jack 2024 (PMID 38934362) or La Joie 2025 (TRAC; DOI 10.1002/alz.70997); no
fabricated rate thresholds.
