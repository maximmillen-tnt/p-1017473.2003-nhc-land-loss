"""Constants shared across the landloss modules."""

from enum import StrEnum

# NZGD2000 / New Zealand Transverse Mercator 2000
DEFAULT_CRS = "EPSG:2193"

# Koordinates domains. T+T's own instance holds the internal layers; LINZ layers
# are served from their own domain by the same API, with a separate key.
TTGROUP_DOMAIN = "ttgroup.koordinates.com"
LINZ_DOMAIN = "data.linz.govt.nz"

# The public Koordinates catalogue, which serves third-party open data such as
# the Greater Wellington hazard layers. A separate account from the two above,
# so its key does not work on either of them.
KOORDINATES_PUBLIC_DOMAIN = "koordinates.com"

# Landcare Research's LRIS portal, another Koordinates instance, which serves
# the land cover and soils datasets. Its key is separate again.
LRIS_DOMAIN = "lris.scinfo.org.nz"

# The environment variable holding the API key for each domain.
API_KEY_ENV_VARS = {
    TTGROUP_DOMAIN: "TNT_KOORDINATES_API_KEY",
    LINZ_DOMAIN: "LINZ_API_KEY",
    KOORDINATES_PUBLIC_DOMAIN: "KOORDINATES_PUBLIC_API_KEY",
    LRIS_DOMAIN: "LRIS_API_KEY",
}

# https://data.linz.govt.nz/layer/123113-nz-addresses/
NZ_ADDRESSES_LAYER_ID = 123113

# https://data.linz.govt.nz/layer/103632-nz-river-name-lines-pilot/
# River name lines carry the ``name`` and ``feat_type`` attributes that the
# topo50 river centrelines lack, which is what lets named rivers be told apart
# from the smaller streams and creeks.
NZ_RIVER_NAME_LINES_LAYER_ID = 103632

# https://lris.scinfo.org.nz/layer/123148-lcdb-v60-land-cover-database-version-60-mainland-new-zealand/
# LCDB v6.0, released October 2025. Polygons carrying a land cover class at each
# of six time steps from summer 1996/97 to summer 2023/24.
NZ_LCDB_V60_LAYER_ID = 123148

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

# https://koordinates.com/layer/4069-wellington-region-earthquake-induced-slope-failure/
# Greater Wellington's earthquake-induced slope failure susceptibility zones.
GWRC_SLOPE_FAILURE_LAYER_ID = 4069

# The layer's SEVERITY column is a string, and only three of the five classes
# carry a word alongside the number. Mapping to an integer is what makes the
# classes sortable and colourable.
GWRC_SEVERITY_RANKS = {
    "1 Low": 1,
    "2": 2,
    "3 Moderate": 3,
    "4": 4,
    "5 High": 5,
}

# The supplied earthquake-induced landslide probability grid, below the
# project's SourceMaterial folder on T:. Read by
# landloss.io.source_material.get_eil_landslide_probability; forward slashes so
# the path reads the same on any platform.
#
# One probability of slope failure per cell, on a 25 m grid covering Wellington.
# Two things about it are taken from the file name rather than from
# documentation, and both need confirming with the supplier before any number
# derived from it is quoted: that "PGA2g" names the shaking level the grid is
# conditioned on, and what that level is in g. Nothing in the code depends on
# the answer -- the grid is used as supplied -- but the report cannot describe
# the result without it.
EIL_PROBABILITY_SOURCE_PATH = "EILProb_Wellington/EILProb_PGA2g.tif"

# The National Liquefaction Model's flatland model, mirrored on the T+T
# Koordinates instance. This is the flat versus sloping land split the study
# takes from the NLM rather than rebuilding; the representation is simplified,
# which was accepted as a sensible base model (see data-sources.md).
NLM_FLATLAND_LAYER_ID = 120641

# The National Liquefaction Model's geomorphology model, also on the T+T
# instance. Carries the landform classes (``l2_geomorphology``) and the
# liquefaction susceptibility the exposure attributes are built from.
NLM_GEOMORPHOLOGY_LAYER_ID = 121398


class NlmRelease(StrEnum):
    r"""The National Liquefaction Model core releases, as the folders name them.

    The releases live under
    ``T:\Auckland\Projects\1017473\WorkingMaterial\new_versioned_releases\core``,
    one directory per member. The folder names are not consistently punctuated --
    ``v2025p0_rc4`` has an underscore that ``v2026p0rc4`` does not -- which is
    exactly why they are listed here once rather than retyped into a path.

    A ``StrEnum``, so a member drops straight into a path join or an f-string and
    reads as the folder name it is.

    Add a member when the NLM publishes a release this study reads; the list is
    what the code has been pointed at, not everything the NLM has ever cut.
    """

    V2025P0_RC4 = "v2025p0_rc4"
    V2026P0_RC4 = "v2026p0rc4"
    V2026P0_RC6 = "v2026p0rc6"


# The National Liquefaction Model release this study reads, named once here so
# that every path reaching into the NLM's tree is built from it. The NLM turns
# releases over during the life of this study, and bumping this is how the study
# follows: there is one pin rather than one per sub-tree, so hazard layers,
# scenario grids and mapped observations cannot silently drift onto different
# releases from one another.
#
# A reader that genuinely has to stay on an older release names the member
# instead -- ``NlmRelease.V2025P0_RC4`` -- so that it is visible at the point of
# use rather than hidden in a second constant.
CORE_NLM_VERSION = NlmRelease.V2026P0_RC6

# The cell size the study works at when deriving terrain attributes, in metres.
# The LINZ LiDAR is 1 m, but the study area is 59 by 54 km: at 1 m that is about
# 3.2 billion cells, which the amenity calculations in particular cannot carry.
# At 10 m it is about 32 million, and nothing the land value model asks of the
# terrain -- the gradient a section sits on, whether it stands above its
# surroundings, whether it can see the sea -- is decided at finer than 10 m.
# A slope feeding retaining wall exposure would need the native resolution and
# should not reuse this value.
DEM_RESOLUTION_M = 10
