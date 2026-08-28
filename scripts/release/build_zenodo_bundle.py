# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Build and validate a reader-facing Zenodo bundle for the article archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from scripts.release import build_reproduction_archive

ROOT = Path(__file__).resolve().parents[2]
ZENODO_CHECKSUMS = "ZENODO_CHECKSUMS.sha256"
ZENODO_MANIFEST = "ZENODO_MANIFEST.json"
SOURCE_DOCUMENTS = (
    "CITATION.cff",
    "COPYRIGHT",
    "LICENSE",
    "LICENSE.en",
    "NOTICE-DATA.md",
    "THIRD_PARTY_NOTICES.md",
)
KEYWORDS = (
    "groundwater age",
    "environmental tracers",
    "lumped parameter models",
    "Bayesian inference",
    "MCMC",
    "PyAges",
    "TracerLPM",
    "prior sensitivity",
    "scientific reproducibility",
)


def sha256(path: Path) -> str:
    """Return the hexadecimal SHA-256 digest of *path*."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _files(root: Path, *, exclude: set[str] | None = None):
    excluded = exclude or set()
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name not in excluded:
            yield path, path.relative_to(root)


def _extract_source_documents(source_zip: Path, destination: Path) -> dict[str, bytes]:
    documents = {}
    with zipfile.ZipFile(source_zip) as archive:
        names = set(archive.namelist())
        missing = set(SOURCE_DOCUMENTS) - names
        if missing:
            raise RuntimeError(f"Source snapshot lacks required documents: {missing}")
        for name in SOURCE_DOCUMENTS:
            data = archive.read(name)
            (destination / name).write_bytes(data)
            documents[name] = data
    return documents


def _creators(citation: dict[str, object]) -> list[dict[str, str]]:
    creators = []
    for author in citation.get("authors", []):
        family = str(author["family-names"])
        given = str(author["given-names"])
        creator = {"name": f"{family}, {given}"}
        if author.get("orcid"):
            creator["orcid"] = str(author["orcid"])
        if author.get("affiliation"):
            creator["affiliation"] = str(author["affiliation"])
        creators.append(creator)
    if not creators:
        raise RuntimeError("CITATION.cff does not declare any creator")
    return creators


def _verify_tracerlpm_dependency(
    path: Path, expected: str, label: str
) -> dict[str, object]:
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Missing TracerLPM {label}: {path}")
    actual = sha256(path)
    if actual.lower() != expected.lower():
        raise RuntimeError(
            f"TracerLPM {label} SHA-256 mismatch: expected {expected}, found {actual}"
        )
    return {
        "label": label,
        "source": path,
        "sha256": actual,
        "bytes": path.stat().st_size,
    }


def _tracerlpm_dependencies(
    archive: Path, workbook: Path, xll: Path
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    config_path = archive / "campaign/tracerlpm/runner-config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    workbook_entry = _verify_tracerlpm_dependency(
        workbook, str(config["workbook_sha256"]), "workbook"
    )
    xll_entry = _verify_tracerlpm_dependency(xll, str(config["xll_sha256"]), "xll")
    return config, workbook_entry, xll_entry


def _scientific_summary(archive: Path) -> dict[str, object]:
    manifest = (
        archive / "campaign/article_package/provenance/article_package_manifest.json"
    )
    return json.loads(manifest.read_text(encoding="utf-8"))["scientific_summary"]


def _require_complete_campaign_scope(manifest: dict[str, object]) -> None:
    scope = str(manifest.get("scope", "")).lower()
    if "holten" not in scope or "prior-sensitivity" not in scope or "excluded" in scope:
        raise RuntimeError(
            "Core archive does not include the Holten prior-sensitivity campaign; "
            "rebuild the complete archive before deposit"
        )


def _readme(
    *,
    title: str,
    version: str,
    doi: str | None,
    core_manifest: dict[str, object],
    scientific: dict[str, object],
    workbook: dict[str, object],
    xll: dict[str, object],
) -> str:
    doi_text = (
        doi or "not reserved yet (reserve it in the Zenodo draft before publication)"
    )
    shifted = scientific["shifted_exponential"]
    holten = scientific["holten_h4"]
    holten_prior = scientific["holten_prior_dirichlet1"]
    ploemeur = scientific["ploemeur_shifted_exponential"]
    ig = scientific["ploemeur_physical_ig"]
    tracer = scientific["pyages_tracerlpm"]
    return f"""# {title}

Version: `{version}`  
Zenodo DOI: `{doi_text}`  
Archived Git revision: `{core_manifest["git_head"]}`

This bundle contains the complete article campaign, retained MCMC states,
derived products, publication-ready figures and tables, execution provenance,
the PyAges source snapshot at the archived Git revision, and the exact USGS
TracerLPM workbook and add-in
used for the cross-software comparison. It includes the Holten--Dirichlet
prior-sensitivity campaign as a distinct robustness analysis; it does not replace
the canonical Holten results.

## Start here

Readers who only want to inspect the article results should open
`campaign/article_package/README.md`, then use:

- `campaign/article_package/figures/` for publication figures;
- `campaign/article_package/tables/` for final numerical tables;
- `campaign/article_package/reports/` for scientific summaries;
- `campaign/article_package/diagnostics/` for convergence and residual checks;
- `campaign/article_package/supporting_data/` for the values plotted in figures.

The less curated complete campaign remains under `campaign/`. Raw `.npz`
files contain NumPy arrays and MCMC states; `.csv.gz` files are compressed CSV;
PDF and PNG files are the easiest figure previews, while TIFF files are the
high-resolution publication versions. Execution logs are historical evidence,
so their recorded Windows paths are not portable commands.

## Résumé de lecture en français

Pour lire les résultats sans relancer les calculs, commencer par
`campaign/article_package/README.md`, puis consulter `figures/`, `tables/` et
`reports/`. Les dossiers `diagnostics/` et `supporting_data/` permettent
l'audit quantitatif. Les chaînes MCMC brutes restent dans les dossiers de la
campagne complète et ne sont utiles que pour un audit approfondi ou une reprise.
La sensibilité Holten au prior Dirichlet est incluse comme analyse de robustesse
distincte; elle ne remplace pas les résultats Holten canoniques.

## Scientific status

- Independent forward verification: {scientific["forward_verification"]["case_count"]} cases
  (`{scientific["forward_verification"]["status"]}`).
- PyAges--TracerLPM: {tracer["paired_cases"]} paired cases,
  {tracer["pyages_successful"]} PyAges successes and
  {tracer["tracerlpm_successful"]} TracerLPM successes.
- Shifted exponential: {shifted["groups"]} groups, maximum split-Rhat
  {shifted["max_split_rhat"]:.6f}, minimum ESS {shifted["min_ess"]:.1f}.
- Holten H4: {holten["groups"]} groups, maximum split-Rhat
  {holten["max_split_rhat"]:.6f}, minimum ESS {holten["min_ess"]:.1f}.
- Holten Dirichlet(1,1,1,1) prior sensitivity: {holten_prior["groups"]} groups,
  maximum split-Rhat {holten_prior["max_split_rhat"]:.6f}, minimum ESS
  {holten_prior["min_ess"]:.1f}; reported as a separate robustness analysis.
- Ploemeur shifted exponential: {ploemeur["groups"]} groups, maximum split-Rhat
  {ploemeur["max_split_rhat"]:.6f}, minimum ESS {ploemeur["min_ess"]:.1f}.
- Ploemeur inverse-Gaussian: {ig["posterior_sets"]} posterior sets, maximum
  split-Rhat {ig["max_split_rhat"]:.6f}, minimum bulk/tail ESS
  {ig["min_bulk_ess"]:.1f}/{ig["min_tail_ess"]:.1f}.

The acceptance thresholds are split-Rhat < 1.01 and ESS >= 300. All reported
MCMC groups pass these thresholds.

## Reproduction material

- `source/pyages-source.zip`: frozen source tree used for this archive;
- `source/environment-pip-freeze.txt`: captured Python environment;
- `campaign/campaign_manifest.json`: stage commands, revisions, status, and timing;
- `campaign/logs/`: unmodified execution logs;
- `external/tracerlpm/`: exact external cross-software dependencies;
- `ARCHIVE_MANIFEST.json` and `CHECKSUMS.sha256`: validated complete scientific archive;
- `{ZENODO_MANIFEST}` and `{ZENODO_CHECKSUMS}`: Zenodo-layer inventory and checksums.

The source snapshot contains the repository at the Git revision named above.
The campaign manifest separately records the exact revision used when each
stage completed, and the article package includes byte-exact execution-source
snapshots for its source-hash-protected calculations. Review the `git_dirty`
field in `ARCHIVE_MANIFEST.json` before publication and rebuild from a clean
release commit for the definitive deposit.

## TracerLPM requirement

The comparison used Microsoft Windows, 64-bit Microsoft Excel, and the USGS
TracerLPM files stored under `external/tracerlpm/`. TracerLPM is identified by
the USGS as public-domain software: https://www.usgs.gov/software/tracerlpm

- workbook: `{Path(str(workbook["source"])).name}`
  (`SHA-256 {workbook["sha256"]}`);
- add-in: `{Path(str(xll["source"])).name}`
  (`SHA-256 {xll["sha256"]}`).

Use `external/tracerlpm/runner-config.example.yaml` as a portable starting
point. The original run configuration is retained under
`campaign/tracerlpm/runner-config.yaml` strictly as provenance.

## Integrity verification

From the extracted bundle root, run:

```text
python verify_bundle.py
```

This verifies every file listed in `{ZENODO_CHECKSUMS}`. The core archive was
also independently validated against {len(core_manifest["files"])} entries in
`ARCHIVE_MANIFEST.json` before this bundle was assembled.

## Rights and citation

PyAges source code is distributed under CeCILL 2.1; see `LICENSE` and
`LICENSE.en`. The CNRS rights-holder and software-authorship notice is in
`COPYRIGHT`. Data and data-derived files retain their source-specific rights
and attribution; see `NOTICE-DATA.md`. Direct dependency notices are recorded
in `THIRD_PARTY_NOTICES.md`. TracerLPM is redistributed with USGS attribution
under its public-domain notice. Review `CITATION.cff` and
`ZENODO_METADATA_DRAFT.json` before publishing the Zenodo record, especially
creator order, ORCIDs, affiliations, the final article title, and the reserved
DOI.
"""


def _tracerlpm_readme(workbook: dict[str, object], xll: dict[str, object]) -> str:
    return f"""# Exact TracerLPM dependencies

These are the byte-exact external files used in the PyAges--TracerLPM article
campaign. They were verified against the SHA-256 values captured before the
run and are included so that reviewers do not have to reconstruct an obsolete
local installation.

| Role | File | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| Workbook | `{Path(str(workbook["source"])).name}` | {workbook["bytes"]} | `{workbook["sha256"]}` |
| 64-bit Excel add-in | `{Path(str(xll["source"])).name}` | {xll["bytes"]} | `{xll["sha256"]}` |

TracerLPM is U.S. Geological Survey software identified as public domain:
https://www.usgs.gov/software/tracerlpm

Credit: U.S. Geological Survey and the TracerLPM authors. Microsoft Excel and
Windows are runtime prerequisites and are not redistributed in this archive.
The adjacent example configuration uses bundle-relative paths; adapt its work
and output directories to the local extraction location.
"""


def _verification_script() -> str:
    return f'''"""Verify every published file in the extracted Zenodo bundle."""

from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHECKSUMS = ROOT / "{ZENODO_CHECKSUMS}"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


failures = []
entries = 0
for raw in CHECKSUMS.read_text(encoding="ascii").splitlines():
    expected, relative = raw.split("  ", 1)
    path = ROOT / Path(relative)
    entries += 1
    if not path.is_file():
        failures.append(f"missing: {{relative}}")
    elif digest(path) != expected:
        failures.append(f"hash: {{relative}}")
if failures:
    raise SystemExit("Invalid Zenodo bundle: " + ", ".join(failures))
print(f"Validated {{entries}} Zenodo bundle files")
'''


def _metadata(
    *,
    title: str,
    version: str,
    citation: dict[str, object],
    doi: str | None,
    article_doi: str | None,
) -> dict[str, object]:
    description = (
        "Complete reproduction evidence for the associated Geoscientific Model "
        "Development article: inputs, scripts, environment, retained MCMC states, "
        "convergence diagnostics, publication figures and tables, the distinct "
        "Holten Dirichlet(1,1,1,1) prior-sensitivity analysis, and the exact USGS "
        "TracerLPM dependencies used for cross-software validation."
    )
    related_identifiers = [
        {
            "identifier": str(citation.get("repository-code", "")),
            "relation": "isSupplementedBy",
            "resource_type": "software",
        }
    ]
    if article_doi:
        related_identifiers.insert(
            0,
            {
                "identifier": article_doi,
                "relation": "isSupplementTo",
                "resource_type": "publication-article",
            },
        )
    return {
        "status": "DRAFT - review before publishing",
        "doi": doi or "RESERVE IN ZENODO AND REBUILD THE BUNDLE WITH --doi",
        "upload_type": "software",
        "title": title,
        "version": version,
        "publication_date": "USE THE DATE THE ZENODO RECORD BECOMES PUBLIC",
        "creators": _creators(citation),
        "description": description,
        "access_right": "open",
        "language": "eng",
        "licenses": [
            {"identifier": "CECILL-2.1", "applies_to": "PyAges source code"},
            {
                "identifier": "review-source-specific-rights",
                "applies_to": "data and derived files; see NOTICE-DATA.md",
            },
            {"identifier": "public-domain", "applies_to": "USGS TracerLPM"},
        ],
        "keywords": list(KEYWORDS),
        "related_identifiers_to_add": related_identifiers,
        "publisher": "Zenodo",
    }


def _portable_runner_config(
    config: dict[str, object], workbook_name: str, xll_name: str
) -> str:
    public = {
        "workbook_path": f"external/tracerlpm/{workbook_name}",
        "workbook_sha256": config["workbook_sha256"],
        "xll_path": f"external/tracerlpm/{xll_name}",
        "xll_sha256": config["xll_sha256"],
        "workbook_map_path": "campaign/tracerlpm/workbook-map.yaml",
        "work_root": "reproduction-output/tracerlpm/work",
        "output_root": "reproduction-output/tracerlpm/output",
        "excel_visible": False,
        "timeout_seconds": config.get("timeout_seconds", 180),
        "reuse_excel_session": config.get("reuse_excel_session", True),
    }
    return yaml.safe_dump(public, sort_keys=False, allow_unicode=True)


def _write_zenodo_inventory(
    root: Path,
    *,
    core_manifest: dict[str, object],
    doi: str | None,
    dependencies: tuple[dict[str, object], dict[str, object]],
) -> dict[str, object]:
    payload = []
    for path, relative in _files(root, exclude={ZENODO_MANIFEST, ZENODO_CHECKSUMS}):
        payload.append(
            {
                "path": relative.as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    manifest = {
        "schema_version": 1,
        "created_at": datetime.now(ZoneInfo("Europe/Paris")).isoformat(),
        "doi": doi,
        "core_archive_git_head": core_manifest["git_head"],
        "core_archive_manifest": "ARCHIVE_MANIFEST.json",
        "core_archive_files": len(core_manifest["files"]),
        "scope": (
            "reader-facing Zenodo bundle and complete GMD reproduction evidence, "
            "including the distinct Holten Dirichlet prior-sensitivity campaign"
        ),
        "external_dependencies": [
            {
                "label": entry["label"],
                "path": f"external/tracerlpm/{Path(str(entry['source'])).name}",
                "bytes": entry["bytes"],
                "sha256": entry["sha256"],
            }
            for entry in dependencies
        ],
        "files": payload,
    }
    (root / ZENODO_MANIFEST).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    checksum_entries = []
    for path, relative in _files(root, exclude={ZENODO_CHECKSUMS}):
        checksum_entries.append(f"{sha256(path)}  {relative.as_posix()}")
    (root / ZENODO_CHECKSUMS).write_text(
        "\n".join(checksum_entries) + "\n", encoding="ascii", newline="\n"
    )
    return manifest


def validate_bundle(root: Path) -> dict[str, object]:
    """Validate the core archive and all files added for Zenodo."""
    root = root.resolve()
    build_reproduction_archive.validate_archive(root)
    manifest = json.loads((root / ZENODO_MANIFEST).read_text(encoding="utf-8"))
    failures = []
    for item in manifest["files"]:
        path = root / item["path"]
        if not path.is_file():
            failures.append(f"missing: {item['path']}")
        elif path.stat().st_size != item["bytes"]:
            failures.append(f"size: {item['path']}")
        elif sha256(path) != item["sha256"]:
            failures.append(f"hash: {item['path']}")

    checksums = {}
    for raw in (root / ZENODO_CHECKSUMS).read_text(encoding="ascii").splitlines():
        expected, relative = raw.split("  ", 1)
        checksums[relative] = expected
    actual_paths = {
        relative.as_posix(): path
        for path, relative in _files(root, exclude={ZENODO_CHECKSUMS})
    }
    if set(checksums) != set(actual_paths):
        failures.append("ZENODO_CHECKSUMS.sha256 inventory")
    for relative, expected in checksums.items():
        path = actual_paths.get(relative)
        if path is not None and sha256(path) != expected:
            failures.append(f"Zenodo hash: {relative}")
    if failures:
        raise RuntimeError("Invalid Zenodo bundle: " + ", ".join(failures))
    return manifest


def _build_zip(root: Path, output: Path) -> Path:
    if output.exists():
        raise FileExistsError(f"Refusing to replace existing ZIP: {output}")
    sidecar = output.with_name(f"{output.name}.sha256")
    if sidecar.exists():
        raise FileExistsError(f"Refusing to replace existing ZIP checksum: {sidecar}")
    temporary = output.with_name(f".{output.name}.staging-{os.getpid()}")
    if temporary.exists():
        raise FileExistsError(f"Refusing to replace temporary ZIP: {temporary}")
    try:
        with zipfile.ZipFile(
            temporary,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=6,
            allowZip64=True,
        ) as archive:
            for path, relative in _files(root):
                archive.write(path, (Path(root.name) / relative).as_posix())
        temporary.replace(output)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    validate_zip(root, output)
    sidecar.write_text(
        f"{sha256(output)}  {output.name}\n", encoding="ascii", newline="\n"
    )
    return output


def validate_zip(root: Path, zip_path: Path) -> int:
    """Validate ZIP structure, member inventory, sizes, and CRC values."""
    expected = {
        (Path(root.name) / relative).as_posix(): path.stat().st_size
        for path, relative in _files(root)
    }
    with zipfile.ZipFile(zip_path) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("ZIP CRC validation failed")
        members = {item.filename: item.file_size for item in archive.infolist()}
        if members != expected:
            raise RuntimeError("ZIP member inventory does not match bundle directory")
        for name in members:
            parts = Path(name).parts
            if Path(name).is_absolute() or ".." in parts:
                raise RuntimeError(f"Unsafe ZIP member: {name}")
    sidecar = zip_path.with_name(f"{zip_path.name}.sha256")
    if sidecar.is_file():
        expected_digest, filename = (
            sidecar.read_text(encoding="ascii").strip().split("  ", 1)
        )
        if filename != zip_path.name or sha256(zip_path) != expected_digest:
            raise RuntimeError("ZIP SHA-256 sidecar validation failed")
    return len(expected)


def build_bundle(
    archive: Path,
    output: Path,
    zip_output: Path,
    *,
    workbook: Path,
    xll: Path,
    title: str | None = None,
    doi: str | None = None,
    article_doi: str | None = None,
) -> tuple[Path, Path]:
    """Create and validate a Zenodo directory plus its uploadable ZIP."""
    archive = archive.resolve()
    output = output.resolve()
    zip_output = zip_output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to replace existing bundle: {output}")
    if zip_output.exists():
        raise FileExistsError(f"Refusing to replace existing ZIP: {zip_output}")
    if output == archive or archive in output.parents or output in archive.parents:
        raise ValueError("Bundle output and core archive must be separate directories")
    core_manifest = build_reproduction_archive.validate_archive(archive)
    _require_complete_campaign_scope(core_manifest)
    config, workbook_entry, xll_entry = _tracerlpm_dependencies(archive, workbook, xll)
    source_zip = archive / "source/pyages-source.zip"
    with zipfile.ZipFile(source_zip) as source:
        citation = yaml.safe_load(source.read("CITATION.cff"))
    version = str(citation["version"])
    title = title or f"PyAges {version} - complete article reproduction archive"
    if core_manifest.get("pyages_version") != version:
        raise RuntimeError(
            "Core archive and CITATION.cff versions differ: "
            f"{core_manifest.get('pyages_version')!r} != {version!r}"
        )
    if core_manifest.get("release_tag") != version:
        raise RuntimeError(
            "Core archive release tag and software version differ: "
            f"{core_manifest.get('release_tag')!r} != {version!r}"
        )
    if version not in core_manifest.get("git_tags_at_head", []):
        raise RuntimeError(
            f"Core archive source commit is not identified by release tag {version!r}"
        )
    scientific = _scientific_summary(archive)
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output.name}.staging-", dir=output.parent)
    )
    try:
        shutil.copytree(archive, staging, dirs_exist_ok=True)
        _extract_source_documents(source_zip, staging)
        external = staging / "external/tracerlpm"
        external.mkdir(parents=True)
        for entry in (workbook_entry, xll_entry):
            shutil.copy2(entry["source"], external / Path(str(entry["source"])).name)
        (external / "README.md").write_text(
            _tracerlpm_readme(workbook_entry, xll_entry),
            encoding="utf-8",
            newline="\n",
        )
        (external / "runner-config.example.yaml").write_text(
            _portable_runner_config(
                config,
                Path(str(workbook_entry["source"])).name,
                Path(str(xll_entry["source"])).name,
            ),
            encoding="utf-8",
            newline="\n",
        )
        (staging / "README.md").write_text(
            _readme(
                title=title,
                version=version,
                doi=doi,
                core_manifest=core_manifest,
                scientific=scientific,
                workbook=workbook_entry,
                xll=xll_entry,
            ),
            encoding="utf-8",
            newline="\n",
        )
        (staging / "verify_bundle.py").write_text(
            _verification_script(), encoding="utf-8", newline="\n"
        )
        (staging / "ZENODO_METADATA_DRAFT.json").write_text(
            json.dumps(
                _metadata(
                    title=title,
                    version=version,
                    citation=citation,
                    doi=doi,
                    article_doi=article_doi,
                ),
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        _write_zenodo_inventory(
            staging,
            core_manifest=core_manifest,
            doi=doi,
            dependencies=(workbook_entry, xll_entry),
        )
        staging.rename(output)
        validate_bundle(output)
        _build_zip(output, zip_output)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        raise
    return output, zip_output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--zip-output", type=Path)
    parser.add_argument("--tracerlpm-workbook", type=Path)
    parser.add_argument("--tracerlpm-xll", type=Path)
    parser.add_argument("--title")
    parser.add_argument("--doi", help="reserved Zenodo DOI, e.g. 10.5281/zenodo.123")
    parser.add_argument("--article-doi", help="GMD article or preprint DOI")
    parser.add_argument(
        "--draft",
        action="store_true",
        help="allow a review bundle without a reserved Zenodo DOI",
    )
    parser.add_argument("--validate-only", type=Path)
    args = parser.parse_args(argv)
    if args.validate_only is not None:
        manifest = validate_bundle(args.validate_only)
        count = len(manifest["files"])
        if args.zip_output is not None:
            count = validate_zip(
                args.validate_only.resolve(), args.zip_output.resolve()
            )
        print(f"Validated Zenodo bundle with {count} files")
        return 0
    required = {
        "--archive": args.archive,
        "--output": args.output,
        "--zip-output": args.zip_output,
        "--tracerlpm-workbook": args.tracerlpm_workbook,
        "--tracerlpm-xll": args.tracerlpm_xll,
    }
    missing = [name for name, value in required.items() if value is None]
    if missing:
        parser.error(f"required for build: {', '.join(missing)}")
    if args.doi is None and not args.draft:
        parser.error("--doi is required for a final bundle; use --draft for review")
    output, zip_output = build_bundle(
        args.archive,
        args.output,
        args.zip_output,
        workbook=args.tracerlpm_workbook,
        xll=args.tracerlpm_xll,
        title=args.title,
        doi=args.doi,
        article_doi=args.article_doi,
    )
    manifest = validate_bundle(output)
    print(
        f"Built Zenodo bundle with {len(manifest['files'])} payload files: "
        f"{output} and {zip_output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
