"""
neurotcs.adapters — Dataset adapters (Piece 6 of 7, PARTIALLY SHIPPED).

Adapters convert public neuroimaging / clinical datasets into the NeuroTCS
input contract format (v1.0 or v1.1).

Shipped (in input_contract v1.0 and v1.1):
  - ADNI categorical adapter (DXSUM longitudinal diagnoses; 14,958 visits)
  - ADNI continuous adapter (UCSFFSX7 hippocampal volumes; 19,072 measurements)
  - ADNI canonical trajectory loader (load_adni_trajectories — locks the
    cTCS = 0.994575 invariant for the four-cohort triangulation)
  - OASIS-3 adapter (Aim 2 AD external validation; 1,247 subjects scored,
    7,248 transitions; locks the cTCS = 0.994191 invariant)
  - NACC adapter (third AD-cohort triangulation; locks cTCS = 0.991502)
  - MIRIAD adapter (Aim 3 measurement-noise floor; 46 AD + 23 CN, 708 scans;
    test-retest pairs at weeks 0, 6, 38 + longitudinal follow-up through
    104 weeks; locks cTCS = 0.985369 (longitudinal) and 1.000000
    (test-retest))

Planned for v1.9.x+ (pending DUA, AD-only):
  - ALZ-NET adapter (Aim 6 real-world anti-amyloid; 3,600+ patients)

Scope (v1.9.0+): NeuroTCS is AD-only. It contains no non-AD adapters and
roadmaps none.

The AD adapters live in neurotcs.input_contract.v1_0.adapters and
neurotcs.input_contract.v1_1.adapters; they will be re-exported here
when piece 6 fully ships.
"""

__status__ = "partial"
__shipped__ = [
    "adni_categorical (v1.0)",
    "adni_continuous (v1.1)",
    "adni_canonical (v1.1)",
    "oasis3 (v1.1)",
    "nacc (v1.1)",
    "miriad (v1.1)",
]
__planned__ = [
    "alz_net",
]
