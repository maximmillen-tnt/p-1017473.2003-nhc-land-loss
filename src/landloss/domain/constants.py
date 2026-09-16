"""Constants shared across the landloss modules."""

# NZGD2000 / New Zealand Transverse Mercator 2000
DEFAULT_CRS = "EPSG:2193"

# Koordinates domains. T+T's own instance holds the internal layers; LINZ layers
# are served from their own domain by the same API, with a separate key.
TTGROUP_DOMAIN = "ttgroup.koordinates.com"
LINZ_DOMAIN = "data.linz.govt.nz"

# The environment variable holding the API key for each domain.
API_KEY_ENV_VARS = {
    TTGROUP_DOMAIN: "TNT_KOORDINATES_API_KEY",
    LINZ_DOMAIN: "LINZ_API_KEY",
}

# https://data.linz.govt.nz/layer/123113-nz-addresses/
NZ_ADDRESSES_LAYER_ID = 123113

# Territorial Authority 2025 boundaries, mirrored on the T+T Koordinates
# instance. LINZ does not publish territorial authority boundaries; they
# originate from Stats NZ.
TERRITORIAL_AUTHORITY_LAYER_ID = 122409

# The four territorial authorities making up the study area, by their
# TA2025_V1_00 code, as agreed at the kick-off meeting.
STUDY_AREA_TA_CODES = {
    "044": "Porirua City",
    "045": "Upper Hutt City",
    "046": "Lower Hutt City",
    "047": "Wellington City",
}
