"""Plugin declaration connecting the model and its packaged parameters."""

from pathlib import Path

from pyages.lpm.extensions import LpmDefinition

from pyages_lpm_bounded_power.model import BoundedPowerLpm

# This proposed public API does not exist in PyAges yet. The template documents
# the intended future plugin contract.

definition = LpmDefinition(
    model_class=BoundedPowerLpm,
    parameter_directory=Path(__file__).parent / "data_lpm",
    api_version=1,
)
