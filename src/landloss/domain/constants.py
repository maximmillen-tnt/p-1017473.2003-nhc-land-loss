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
