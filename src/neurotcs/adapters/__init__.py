"""
neurotcs.adapters — Dataset adapters (Piece 6 of 7, PARTIALLY SHIPPED).

Adapters convert public neuroimaging / clinical datasets into the NeuroTCS
input contract format (v1.0 or v1.1).

Shipped (in input_contract v1.0 and v1.1):
  - ADNI categorical adapter (DXSUM longitudinal diagnoses; 14,958 visits)
  - ADNI continuous adapter (UCSFFSX7 hippocampal volumes; 19,072 measurements)

Planned for v0.2 (pending DUA):
  - OASIS-3 adapter (Aim 2 AD external validation; 1,378 subjects)
  - MIRIAD adapter (Aim 3 test-retest stress; 46 AD + 23 CN, 708 scans)
  - PPMI adapter (Aim 5 PD portability; 2,000+ subjects)
  - RIDER Lung PET-CT adapter (Aim 5 oncology RECIST; 244 subjects)
  - ALZ-NET adapter (Aim 6 real-world anti-amyloid; 3,600+ patients)

The ADNI adapters currently live in neurotcs.input_contract.v1_0.adapters
and neurotcs.input_contract.v1_1.adapters; they will be re-exported here
when piece 6 fully ships.
"""

__status__ = "partial"
__shipped__ = ["adni_categorical (v1.0)", "adni_continuous (v1.1)"]
__planned__ = [
    "oasis3",
    "miriad",
    "ppmi",
    "rider_lung_pet_ct",
    "alz_net",
]
