# Final submission readiness

## Verdict

**NOT READY FOR SUBMISSION**

The supplied rules require an immediate hard stop when canonical checksums fail or required raw outputs are missing. Both conditions occurred. The source manuscript and supplement were also not supplied.

## Hard blockers

1. `PyAge_v1.0_revised_v22(1).docx` is missing.
2. `PyAge_v1.0_supplementary_material_v1 (1).docx` is missing.
3. All six `article/run_case.py check` commands fail.
4. Six canonical script checksums differ from their case manifests.
5. Required archived chains/pilots, data-audit artifacts, canonical summaries, and historical manifests are missing.
6. The current checkout is commit `04e6ebaa...`; case manifests identify older calculation commits `20d02ed...` and `e77691e...`.
7. Tag `1.0` does not point at the current commit, while installed/package metadata reports PyAge 0.1.0.
8. No immutable public v1.0 scientific archive or resolving software/archive DOI was found.
9. Author contribution, competing-interest, financial-support verification, and AI-use-declaration decisions require human input.

## Acceptance gates

- [ ] All scientific values are traced to canonical files — **blocked**
- [ ] All case checks pass — **failed (0/6)**
- [ ] Checksums match archived v1.0 source and inputs — **failed**
- [ ] Public archive DOI exists and resolves — **failed/not found**
- [ ] Code/data availability uses verified present or past tense — **not evaluated**
- [ ] Figures 2–4 and S1 meet content/readability rules — **not generated**
- [ ] Tables 3 and 4 use at least 9 pt and Table 4 is redesigned — **not evaluated**
- [ ] Supplement title page is removed — **not evaluated**
- [ ] Supplement S1–S5 revisions are verified — **blocked by missing canonical outputs and DOCX**
- [ ] Bibliography citations and references match one-to-one — **blocked by missing DOCX**
- [ ] Recent references have current publication status — **not evaluated**
- [ ] Human declarations are supplied and validated — **outstanding**
- [ ] Both PDFs pass page-by-page inspection — **PDFs not created**

## Required recovery before resuming

Provide the two exact input DOCX files and restore or mount the immutable scientific archive paths declared by the six case manifests. Reconcile the script checksum differences against the calculation revisions without rerunning science, or obtain explicit human authorization for any required reruns. Supply the resolving archive DOI and the four human declaration decisions. Then rerun all six `check` commands; manuscript work may resume only after the hard-stop conditions are cleared.
