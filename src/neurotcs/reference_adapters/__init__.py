"""
neurotcs.reference_adapters — Reference vendor adapters (Piece 6b, v1.8.1).

This subpackage hosts *reference submission-builders*: scripts that convert
a cohort's raw data files INTO a conforming NeuroTCS input-contract
submission. They are intended as **pedagogical templates** that vendors
(icometrix, Cortechs.ai, Combinostics, etc.) clone and modify to format
their own AI output for NeuroTCS audit.

IMPORTANT — these are NOT runtime loaders.

For the v1.8 canonical *runtime* loaders that drive `neurotcs.audit()`, see:

    from neurotcs.input_contract.v1_1.adapters.adapter_adni_canonical import (
        load_adni_trajectories,
    )
    from neurotcs.input_contract.v1_1.adapters.adapter_oasis3 import (
        load_oasis3_trajectories,
    )
    from neurotcs.input_contract.v1_1.adapters.adapter_nacc import (
        load_nacc_trajectories,
    )
    from neurotcs.input_contract.v1_1.adapters.adapter_miriad import (
        load_miriad_trajectories,
    )

The reference adapters in THIS package, by contrast, are submission-builder
CLIs that emit JSON manifests in the NeuroTCS input-contract format. They
are used by vendor onboarding documentation and FDA Q-Sub demonstration
packages.

Modules:

    adni_categorical_submission   — Convert ADNI DXSUM into a v1.0 categorical
                                    submission (clinical state per visit).
    adni_volumetric_submission    — Convert ADNI FreeSurfer UCSFFSX7 into a
                                    v1.1 continuous-biomarker submission
                                    (hippocampal volumes in mL).
"""

__all__: list = []
__status__ = "production"
