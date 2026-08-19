"""Job-building helpers for the Ploemeur workflow."""

from sites.ploemeur.config.models import WellDateConfig


def results_root_name(
    folder: str, conc_error_rel: float, time_span_and_prior_mode: str
) -> str:
    """Build the results root name for a given error and mode."""
    return f"{folder}{conc_error_rel}{time_span_and_prior_mode}"


def selector(
    well_select: list[str],
    well_dates: dict[str, WellDateConfig],
    conc_error_rel: float = 0.03,
    lpm_default: list[str] | None = None,
    lpm_by_well: dict[str, list[str]] | None = None,
) -> tuple[list[str], list[str], list[float], list[list[str]]]:
    """Map selected wells to date ranges, errors, and LPM models."""
    wells: list[str] = []
    datess: list[str] = []
    conc_error_rel_values: list[float] = []
    lpm_types: list[list[str]] = []

    lpm_by_well = lpm_by_well or {}

    for well in well_select:
        if well not in well_dates:
            raise ValueError(f"Missing well_dates entry for {well}")
        date_range = well_dates[well]
        start = date_range.start
        end = date_range.end
        wells.append(well)
        datess.append(f"{start}_{end}")
        conc_error_rel_values.append(conc_error_rel)
        lpm_types.append(lpm_by_well.get(well, lpm_default))

    return wells, datess, conc_error_rel_values, lpm_types


def build_jobs(
    conc_error_rel_values: list[float],
    time_span_and_prior: list[str],
    prior: list[bool],
    likelihood: list[bool],
    prior_folder: list[str],
    well_select: list[str],
    well_dates: dict[str, WellDateConfig],
    lpm_default: list[str],
    lpm_by_well: dict[str, list[str]],
    folder: str,
) -> list[tuple[str, str, list[str], str, str, float, bool, bool, str]]:
    """Build a list of execution jobs from configured parameters."""
    jobs: list[tuple[str, str, list[str], str, str, float, bool, bool, str]] = []
    for conc_error_rel in conc_error_rel_values:
        for (
            time_span_and_prior_mode,
            prior_opt,
            likelihood_opt,
            prior_folder_name,
        ) in zip(
            time_span_and_prior,
            prior,
            likelihood,
            prior_folder,
        ):
            wells, datess, _, lpm_types = selector(
                well_select,
                well_dates,
                conc_error_rel=conc_error_rel,
                lpm_default=lpm_default,
                lpm_by_well=lpm_by_well,
            )
            file_root = results_root_name(
                folder, conc_error_rel, time_span_and_prior_mode
            )

            for idx in range(len(wells)):
                jobs.append(
                    (
                        wells[idx],
                        datess[idx],
                        lpm_types[idx],
                        file_root,
                        time_span_and_prior_mode,
                        conc_error_rel,
                        prior_opt,
                        likelihood_opt,
                        prior_folder_name,
                    )
                )
    return jobs
