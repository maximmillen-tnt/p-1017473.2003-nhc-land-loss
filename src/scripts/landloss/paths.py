"""Filesystem paths to assets shared across the landloss scripts."""

from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent / "vul" / "assets"

NHI_ACT_LAND_CLAIMS_COHORT_CSV = ASSETS_DIR / "NHI_Act_Land claims cohort modelling.csv"
NHI_ACT_SETTLED_LAND_CLAIMS_CSV = (
    ASSETS_DIR / "NHI_Act_Settled_Land_Claims - 20260916.csv"
)
