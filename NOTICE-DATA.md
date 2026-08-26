# Data provenance and redistribution notice

This notice covers scientific data and data-derived files distributed in the
PyAge source repository and Python package. It does not replace the citations
embedded in individual CSV, YAML, text, or spreadsheet files.

The PyAge software is licensed under CeCILL 2.1. That software license does not
automatically relicense third-party data. Each source below retains its own
terms, attribution requirements, and scientific limitations.

On 19 August 2026, the project maintainer confirmed that the project-owned data
and Excel files listed below may remain in, and be redistributed with, the
source repository. Source-specific attribution and restrictions still apply.

## Atmospheric tracer histories

| Repository material | Source and transformations | Redistribution and attribution |
| --- | --- | --- |
| `data_core/data_tracer/CFC-SF6 chronicles, December 2025.xlsx` | Working compilation of Northern Hemisphere CFC-11, CFC-12, CFC-113, and SF6 atmospheric histories. The workbook metadata identifies Barbara Yvard as creator. Its cells and comments refer to USGS age-dating air curves and NOAA Global Monitoring Laboratory HATS data. | Project redistribution confirmed. Cite USGS and NOAA and identify PyAge/local updates when redistributing a modified copy. |
| `data_core/data_tracer/CFC-SF6 chronicles, Octobre 2024.xlsx` | Earlier working compilation of CFC and SF6 atmospheric histories; workbook metadata identifies Barbara Yvard as creator. | Project redistribution confirmed. Cite USGS and NOAA and identify local modifications. |
| `data_core/data_tracer/CFCs-SF6 chronicles 1940-2020.xlsx` | Historical working compilation used to prepare tracer recharge series. Workbook metadata identifies Barbara Yvard as creator and Jean-Raynald de Dreuzy as a later editor. | Project redistribution confirmed. Cite the upstream atmospheric-data providers and identify local modifications. |
| `data_core/data_tracer/cfc11/recharge.csv` | NOAA Global Monitoring Laboratory CFC-11 combined record, supplemented before the observational period by a legacy reconstruction and sampled on a semi-annual grid. Citation: Dutton et al. (2025), <https://doi.org/10.15138/BVQ6-2S69>. | NOAA material is generally public domain in the United States. Cite NOAA GML and the dataset DOI. Do not imply NOAA endorsement. |
| `data_core/data_tracer/cfc12/recharge.csv` | NOAA Global Monitoring Laboratory CFC-12 combined record, supplemented before the observational period by a legacy reconstruction and sampled on a semi-annual grid. Citation: Dutton et al. (2025), <https://doi.org/10.15138/PJ63-H440>. | Same conditions as the CFC-11 record. |
| `data_core/data_tracer/cfc113/recharge.csv` | NOAA Global Monitoring Laboratory CFC-113 combined record, with a retained legacy reconstruction before 1992 and semi-annual sampling. Citation: Dutton et al. (2025), <https://doi.org/10.15138/4N0D-4M07>. | Same conditions as the CFC-11 record. |
| `data_core/data_tracer/sf6/recharge.csv` | NOAA Global Monitoring Laboratory and AGAGE SF6 history, with a retained legacy reconstruction before 1995 and semi-annual sampling. Citation: Dutton et al. (2023), <https://doi.org/10.15138/TQ02-ZX42>. | Cite NOAA GML, AGAGE, and the dataset DOI. Verify the terms of any non-NOAA contribution before reusing it outside this distribution. |
| `data_core/data_tracer/3H/recharge.csv` | Tritium precipitation history attributed in the file header to the IAEA/WMO Global Network of Isotopes in Precipitation (GNIP/WISER), <https://nucleus.iaea.org/Pages/GNIPR.aspx>. | Cite the IAEA GNIP database. Users reusing the data outside PyAge must check the current IAEA data-use terms. |
| `data_core/data_tracer/14C_NH/recharge.csv` and `14C_SH/recharge.csv` | Curves derived from the `StoredTracerData` sheet of the USGS TracerLPM workbook. The file headers identify IntCal09 for the pre-bomb period and Hua et al. (2021), as distributed through CALIBomb/IntCal, for the post-bomb period. Monthly workbook data were aggregated to annual means where documented. | TracerLPM is published by USGS as public-domain software. Retain the USGS attribution, the calibration-curve citations, and the transformation notes. Check the cited calibration datasets' terms for independent redistribution. |
| Other tracer inputs under `data_core/data_tracer/` (`39Ar`, `kr85`, `Li`, `NO3`, and `SO4`) | Scientific constants, illustrative recharge histories, or literature-derived inputs. Citations and model assumptions are recorded where available in file headers and tracer YAML metadata. | Project redistribution confirmed. These files require scientific-source verification before reuse as authoritative observational datasets. |

Official source information:

- USGS TracerLPM: <https://www.usgs.gov/software/tracerlpm>
- USGS software user-rights notice: <https://water.usgs.gov/software/CAP/code/1.0/UserRightsNotice.html>
- NOAA digital-media conditions: <https://sos.noaa.gov/copyright/>

The three working spreadsheets are retained in the source repository for
provenance and auditability. They are not runtime resources and are excluded
from the Python wheel; the normalized CSV and YAML resources are the packaged
inputs used by PyAge.

## Ploemeur observations

The source spreadsheets under `sites/ploemeur/data/brut/`, including the CFC
chronicles and well measurements, are project-authorized observation data. The
text files in the same directory are manually maintained exports. Files under
`sites/ploemeur/data/ori/` are normalized derivatives produced by
`python -m sites.ploemeur.scripts.prepare_observations`.

Redistribution of these source and normalized files with the PyAge repository
was confirmed by the project maintainer on 19 August 2026. Reusers should cite
the PyAge project and the **Ploemeur-Guidel observatory, SNO H+ / OZCAR**, whose
site description and data-access catalogue are available at
<https://hplus.ore.fr/en/ploemeur/>. Questions about the institutional dataset
and attribution can be addressed to `hplus-contact@univ-rennes1.fr`. A useful
site-context reference is Le Borgne et al. (2004), *Water Resources Research*,
<https://doi.org/10.1029/2003WR002436>. These references identify the
observatory; they do not imply that every local working-table value was
downloaded from that publication.

## Holten example data

The Holten workbook and derived tables under `examples/natural/holten/doc/`,
the prepared well files under `examples/natural/holten/data/`, and the local
tracer histories reproduce data and reported model fractions from:

> Visser, A., Broers, H. P., Purtschert, R., Sültenfuß, J., and de Jonge, M.
> (2013). Groundwater age distributions at a public drinking water supply well
> field derived from multiple age tracers (85Kr, 3H/3He, and 39Ar). *Water
> Resources Research*, 49, 7778–7796.
> <https://doi.org/10.1002/2013WR014012>

The project maintainer confirmed redistribution of the extracted and prepared
data. The publisher PDF and locally prepared presentation are not part of the
current source tree or release distribution; obtain the article through its
DOI. They occurred in older Git history and require a separate redistribution
review before that history is mirrored or archived publicly.

## Fontainebleau example data

The observation files under `examples/natural/fontainebleau/data/` reproduce
the Fontainebleau benchmark described by:

> Corcho Alvarado, J. A., et al. (2007). Constraining the age distribution of
> highly mixed groundwater using 39Ar: A multiple environmental tracer
> (3H/3He, 85Kr, 39Ar, and 14C) study in the semiconfined Fontainebleau Sands
> Aquifer (France). *Water Resources Research*, 43, W03427.
> <https://doi.org/10.1029/2006WR005096>

The project maintainer confirmed redistribution of the extracted benchmark
data. The publisher PDF is not part of the current source tree or release
distribution; obtain the article through its DOI. It occurred in older Git
history and requires a separate redistribution review before that history is
mirrored or archived publicly.

## Other examples, tests, and validation data

- Data under `examples/natural/albuquerque/` are local example inputs prepared
  from the Albuquerque public-supply-well case described by Jurgens, Böhlke,
  and Eberts (2012), *TracerLPM: An Excel Workbook for Interpreting Groundwater
  Age Distributions from Environmental Tracer Data*, USGS Techniques and
  Methods 4-F3, <https://doi.org/10.3133/tm4F3>. Redistribution of the prepared
  tables was confirmed by the project maintainer; retain both the USGS and
  PyAge transformation attribution.
- Files under `tests/data/` and `tests/golden/` are compact fixtures or
  regression values created for PyAge. They may be redistributed with the
  software and are not independent reference datasets.
- Files under `validation/tracerlpm/benchmark/inputs/` and `references/` are
  deterministic synthetic inputs and compact reference values produced by the
  documented validation scripts. Large generated observations, raw Excel
  exports, campaign outputs, and reports are deliberately excluded from Git.

## Scientific-use disclaimer

The data are provided for reproducibility and software validation. Presence in
the repository does not certify fitness for a particular hydrogeological
interpretation. Check units, temporal coverage, spatial applicability,
transformations, uncertainty assumptions, and the cited primary sources before
using a dataset in scientific or operational work.
