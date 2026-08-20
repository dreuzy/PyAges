"""Validate the HYP-26-0172 matrix and all referenced configurations."""

from __future__ import annotations

from sites.ploemeur.workflows.ploemeur_workflow import validate_workflow_params

from .study_common import load_matrix, load_yaml, resolve_repo_path, split_field


def validate_row(row: dict[str, str]) -> list[str]:
    errors: list[str] = []
    experiment_id = row["experiment_id"]
    params_path = resolve_repo_path(row["params_path"])
    if row["enabled"].lower() not in {"true", "false"}:
        errors.append(f"{experiment_id}: enabled must be true or false")
    if not params_path.is_file():
        return [f"{experiment_id}: missing params file {params_path}"]

    params = load_yaml(params_path)
    try:
        validate_workflow_params(params)
    except (TypeError, ValueError) as exc:
        errors.append(f"{experiment_id}: invalid workflow configuration: {exc}")
        return errors

    expected_wells = split_field(row["wells"])
    actual_wells = [str(value) for value in params["observations"]["wells"]]
    if expected_wells != actual_wells:
        errors.append(
            f"{experiment_id}: matrix wells {expected_wells} != YAML wells {actual_wells}"
        )

    expected_errors = [float(value) for value in split_field(row["relative_errors"])]
    actual_errors = [float(value) for value in params["observations"]["conc_error_rel"]]
    if expected_errors != actual_errors:
        errors.append(
            f"{experiment_id}: matrix errors {expected_errors} != YAML errors {actual_errors}"
        )

    expected_pipelines = split_field(row["prior_pipeline"])
    actual_pipelines = [str(value) for value in params["workflows"]["prior_pipeline"]]
    if expected_pipelines != actual_pipelines:
        errors.append(
            f"{experiment_id}: matrix pipelines {expected_pipelines} != YAML pipelines {actual_pipelines}"
        )

    expected_seeds = [int(value) for value in split_field(row["seeds"])]
    actual_seed = int(params["calibration"]["seed"])
    if expected_seeds != [actual_seed]:
        errors.append(
            f"{experiment_id}: matrix seeds {expected_seeds} != YAML seed {actual_seed}"
        )

    expected_results = f"results/HYP-26-0172/runs/{experiment_id}/workflow"
    actual_results = params["results"].get("directory", "").replace("\\", "/")
    if actual_results != expected_results:
        errors.append(f"{experiment_id}: results.directory must be {expected_results}")
    return errors


def main() -> int:
    rows = load_matrix()
    ids = [row["experiment_id"] for row in rows]
    errors = [
        f"duplicate experiment_id: {value}"
        for value in sorted(set(ids))
        if ids.count(value) > 1
    ]
    for row in rows:
        errors.extend(validate_row(row))
    if errors:
        print("Study validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    enabled = sum(row["enabled"].lower() == "true" for row in rows)
    print(f"Validated {len(rows)} experiments ({enabled} enabled).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
