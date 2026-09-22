"""The policy settings the study puts under test, gathered into one object.

`loss` is the only module where policy wording enters the model, and comparing
one set of settings against another is the whole point of the study. Holding
them in a frozen dataclass rather than as bare module constants is what makes a
scenario a value instead of an edit: two scenarios can be built and run in the
same process without one leaking into the other, and a run records which
settings produced it.

The defaults are the Natural Hazards Insurance Act as it currently stands, taken
from ``.agents/context/nhi-act-land-cover-explainer.md``. The setting NHC is
considering introducing -- :attr:`PolicySettings.total_cap_nzd`, which has no
equivalent in the present Act -- sits alongside them, so switching it on is the
same kind of act as changing a sub-cap rather than a different kind of change.

**Dollar amounts in this module are exclusive of GST**, because that is how the
Act states the sub-caps. The settlement arithmetic in
:mod:`landloss.loss.settlement` works GST-inclusive, since that is the basis the
Act compares repair cost against undepreciated value on, so the sub-caps are
grossed up at the point of use by :meth:`PolicySettings.retaining_wall_limit_nzd`
and :meth:`PolicySettings.bridge_culvert_limit_nzd` rather than by the caller.
"""

from dataclasses import dataclass

import numpy as np

# The explainer's worked examples gross a one-dwelling retaining wall limit of
# $50,000 to $57,500, which is what fixes the rate at 15% rather than leaving it
# to be assumed.
GST_RATE = 0.15

# Both sub-caps are per dwelling in the residential building -- not per wall, not
# per owner, and not per property. A site carrying two residential buildings has
# two caps, worked out separately.
RETAINING_WALL_SUB_CAP_NZD = 50_000.0
BRIDGE_CULVERT_SUB_CAP_NZD = 25_000.0

# The land excess is $500 per dwelling capped at $5,000, so it stops growing at
# ten dwellings.
LAND_EXCESS_PER_DWELLING_NZD = 500.0
LAND_EXCESS_MAX_NZD = 5_000.0

# Damaged land is valued over the lesser of the district plan minimum area and
# 4,000 m2. No district plan minimum has been obtained for the four territorial
# authorities, so the Act's own fallback stands in for all of them and is the
# first number to replace when they arrive.
AREA_CAP_M2 = 4_000.0


@dataclass(frozen=True)
class PolicySettings:
    """One scenario's policy settings.

    Attributes:
        gst_rate: GST as a fraction, used to gross the sub-caps up.
        retaining_wall_sub_cap_nzd: Retaining wall sub-cap per dwelling,
            excluding GST.
        bridge_culvert_sub_cap_nzd: Bridge and culvert sub-cap per dwelling,
            excluding GST.
        excess_per_dwelling_nzd: Land excess charged per dwelling.
        excess_max_nzd: The most the land excess can reach however many
            dwellings there are.
        area_cap_m2: The largest area of damaged land that is valued. Damage
            beyond it is valued as though it stopped here.
        total_cap_nzd: A single cap over the whole land settlement. ``None`` is
            the present Act, which has no such cap; a figure is the setting
            under test.
        include_imminent_damage: Whether imminently damaged land and structures
            are settled. ``True`` is the present Act. Setting it ``False`` is
            how the study prices removing the provision.
    """

    gst_rate: float = GST_RATE
    retaining_wall_sub_cap_nzd: float = RETAINING_WALL_SUB_CAP_NZD
    bridge_culvert_sub_cap_nzd: float = BRIDGE_CULVERT_SUB_CAP_NZD
    excess_per_dwelling_nzd: float = LAND_EXCESS_PER_DWELLING_NZD
    excess_max_nzd: float = LAND_EXCESS_MAX_NZD
    area_cap_m2: float = AREA_CAP_M2
    total_cap_nzd: float | None = None
    include_imminent_damage: bool = True

    def __post_init__(self) -> None:
        """Refuse settings that cannot describe a real policy."""
        negatives = {
            "gst_rate": self.gst_rate,
            "retaining_wall_sub_cap_nzd": self.retaining_wall_sub_cap_nzd,
            "bridge_culvert_sub_cap_nzd": self.bridge_culvert_sub_cap_nzd,
            "excess_per_dwelling_nzd": self.excess_per_dwelling_nzd,
            "excess_max_nzd": self.excess_max_nzd,
        }
        for name, value in negatives.items():
            if not np.isfinite(value) or value < 0:
                msg = f"{name} must be finite and not negative"
                raise ValueError(msg)
        if not np.isfinite(self.area_cap_m2) or self.area_cap_m2 <= 0:
            msg = "area_cap_m2 must be finite and positive"
            raise ValueError(msg)
        if self.total_cap_nzd is not None and (
            not np.isfinite(self.total_cap_nzd) or self.total_cap_nzd < 0
        ):
            msg = "total_cap_nzd must be finite and not negative, or None"
            raise ValueError(msg)

    def retaining_wall_limit_nzd(
        self, n_dwellings: np.ndarray | float
    ) -> np.ndarray | float:
        """Return the retaining wall sub-cap limit, grossed up for GST.

        Args:
            n_dwellings: Dwellings in the residential building.

        Returns:
            The applicable limit in GST-inclusive dollars.
        """
        gross = self.retaining_wall_sub_cap_nzd * (1.0 + self.gst_rate)
        return np.asarray(n_dwellings, dtype=float) * gross

    def bridge_culvert_limit_nzd(
        self, n_dwellings: np.ndarray | float
    ) -> np.ndarray | float:
        """Return the bridge and culvert sub-cap limit, grossed up for GST.

        Args:
            n_dwellings: Dwellings in the residential building.

        Returns:
            The applicable limit in GST-inclusive dollars.
        """
        gross = self.bridge_culvert_sub_cap_nzd * (1.0 + self.gst_rate)
        return np.asarray(n_dwellings, dtype=float) * gross

    def excess_nzd(self, n_dwellings: np.ndarray | float) -> np.ndarray | float:
        """Return the land excess for a residential building.

        Args:
            n_dwellings: Dwellings in the residential building.

        Returns:
            The excess, which stops growing once it reaches
            :attr:`excess_max_nzd`.
        """
        per_dwelling = np.asarray(n_dwellings, dtype=float)
        return np.minimum(
            per_dwelling * self.excess_per_dwelling_nzd, self.excess_max_nzd
        )
