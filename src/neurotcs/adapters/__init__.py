"""
neurotcs.adapters — Dataset adapters (Piece 6 of 7, PARTIALLY SHIPPED).

Adapters convert public neuroimaging / clinical datasets into the NeuroTCS
input contract format (v1.0 or v1.1).

Shipped (in input_contract v1.0 and v1.1):
  - ADNI categorical adapter (DXSUM longitudinal diagnoses; 14,958 visits)
  - ADNI continuous adapter (UCSFFSX7 hippocampal volumes; 19,072 measurements)
  - OASIS-3 adapter (Aim 2 AD external validation; 1,247 subjects scored,
    7,248 transitions; locks the cTCS = 0.9942 invariant)
  - MIRIAD adapter (Aim 3 measurement-noise floor; 46 AD + 23 CN, 708 scans;
    test-retest pairs at weeks 0, 6, 38 + longitudinal follow-up through
    104 weeks)

Planned for v0.2 (pending DUA):
  - PPMI adapter (Aim 5 PD portability; 2,000+ subjects)
  - RIDER Lung PET-CT adapter (Aim 5 oncology RECIST; 244 subjects)
  - ALZ-NET adapter (Aim 6 real-world anti-amyloid; 3,600+ patients)

The ADNI, OASIS-3, and MIRIAD adapters live in
neurotcs.input_contract.v1_0.adapters and
neurotcs.input_contract.v1_1.adapters; they will be re-exported here
when piece 6 fully ships.
"""

__status__ = "partial"
__shipped__ = [
    "adni_categorical (v1.0)",
    "adni_continuous (v1.1)",
    "oasis3 (v1.1)",
    "miriad (v1.1)",
]
__planned__ = [
    "ppmi",
    "rider_lung_pet_ct",
    "alz_net",
]
