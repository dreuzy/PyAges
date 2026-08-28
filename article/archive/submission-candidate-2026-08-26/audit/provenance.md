# PyAge v1.0 submission-candidate provenance

Status: **HARD FAILURE — processing stopped before manuscript modification**

Captured at 2026-08-26T21:20:07.4594901+02:00 (Europe/Paris).

## Repository

- Repository: `C:\codes\pyage`
- Branch: `refactor/release-0.1`
- Commit: `04e6ebaa4b7a67154bbb4532e112e543563790ad`
- Upstream: `origin/refactor/release-0.1` (`+0/-0`)
- Initial tracked/untracked status: clean
- Initial untracked files: none
- Initial unstaged diff: empty
- Initial staged diff: empty
- Tags pointing at current commit: none
- Repository tags observed: `1.0`
- The case manifests refer to calculation commits `20d02ed...` or `e77691e...`, not the current commit.

## Host and software

- Operating system: Microsoft Windows NT 10.0.26200.0
- Python: 3.12.4 (`C:\Python312\python.exe`)
- PyAge: 0.1.0
- NumPy: 2.1.2
- SciPy: 1.14.1
- pandas: 2.2.3
- Matplotlib: 3.10.8
- Pillow: 12.2.0
- python-docx: not installed
- Pandoc: installed at `C:\Users\dreuzy\AppData\Local\Pandoc\pandoc.exe`
- Microsoft Word: installed at `C:\Program Files\Microsoft Office\Root\Office16\WINWORD.EXE`
- LibreOffice: not found on `PATH`
- Package inventory command executed: `python -m pip list --format=freeze`

## Required source documents

Neither required DOCX was present in the supplied attachment directory, the repository, or an exact-name recursive search of `C:\Users\dreuzy`:

- `PyAge_v1.0_revised_v22(1).docx` — missing
- `PyAge_v1.0_supplementary_material_v1 (1).docx` — missing

The supplied attachment directory contained only `pasted-text.txt` (23,755 bytes). Therefore no OOXML package audit, template transfer, tracked-revision inspection, equation-preservation check, or bibliography extraction was possible.

## Authorized case verification

Only `python article/run_case.py list` and `python article/run_case.py check <case_id>` were run. No `run` or `postprocess` command was executed. All six requested checks failed. Details are in `case_check_results.csv`.

The failures include canonical checksum mismatches, absent historical manifests, absent canonical summaries, and absent raw posterior chain/pilot directories. Under the supplied non-negotiable rules these are hard-stop conditions.

## Archive and DOI state

- A repository tag named `1.0` exists but does not point at the current commit.
- The repository identifies the installed project as PyAge 0.1.0.
- No final software/archive DOI was found in repository citation or release metadata.
- Repository documentation explicitly says no DOI should be anticipated before an immutable archive exists.

## Scope of work performed

Phase 0 inventory and the authorized case checks were performed. Scientific postprocessing, figure generation, manuscript changes, supplement changes, and rendering were deliberately not performed after the hard failure.
