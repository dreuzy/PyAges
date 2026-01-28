# Adding a New Tracer

This guide explains how to add a new environmental tracer to PyAge. Tracers are chemical species with known atmospheric histories used for groundwater age dating.

## Quick Method: Use the Template Generator

The easiest way to create a new tracer is with the template generator:

```bash
python scripts/new_component.py tracer <name> [options]
```

**Options:**
- `--unit`, `-u`: Concentration unit (default: pptv)
- `--decay`, `-d`: Enable radioactive decay
- `--production`, `-g`: Enable geoproduction
- `--no-recharge`: Use constant concentration instead of chronicle

**Examples:**

```bash
# Standard atmospheric tracer
python scripts/new_component.py tracer krypton85 --unit "Bq/L"

# Radioactive tracer
python scripts/new_component.py tracer argon39 --unit "atoms/L" --decay

# Tracer with decay and geoproduction
python scripts/new_component.py tracer carbon14 --unit pmC --decay --production
```

This creates:
- `data_core/data_tracer/<name>/<name>.yaml` - Configuration file
- `data_core/data_tracer/<name>/recharge.csv` - Sample data (replace with real data)

---

## Manual Method: Step by Step

### Step 1: Create the Tracer Directory

```bash
mkdir data_core/data_tracer/mytracer
```

### Step 2: Create the Configuration File

Create `data_core/data_tracer/mytracer/mytracer.yaml`:

```yaml
# MyTracer Configuration

# Unit of concentration measurement
unit: pptv

# Recharge chronicle from CSV file
recharge: true

# Optional: Radioactive decay (uncomment if needed)
# decay_time: 17.77  # Half-life / ln(2) in years

# Optional: In-situ production (uncomment if needed)
# production_rate: 0.0
```

### Step 3: Create the Recharge Chronicle

Create `data_core/data_tracer/mytracer/recharge.csv`:

```csv
date,concentration
1940.0,0.0
1950.0,10.5
1960.0,45.2
1970.0,120.8
1980.0,250.3
1990.0,350.0
2000.0,380.5
2010.0,395.2
2020.0,400.0
```

**Format requirements:**
- First column: decimal year (e.g., 2020.5 = July 1, 2020)
- Second column: atmospheric concentration
- Header line with column names
- Comments allowed with `#` prefix

### Step 4: Test the Tracer

```python
from tracer.tracer_root import Tracer, find_tracer_dir

tracer = Tracer(find_tracer_dir(), name="mytracer")
print(f"Name: {tracer.name}")
print(f"Unit: {tracer.unit}")
print(f"Date range: {tracer.datemin} - {tracer.datemax}")

# Test concentration lookup
conc = tracer.get_concentration(date=2010.0, time=20.0)
print(f"Concentration at 2010, age 20: {conc}")
```

---

## Configuration Reference

### Basic Configuration

```yaml
# Required: concentration unit
unit: pptv      # or TU, pmC, Bq/L, atoms/L, mol, etc.

# Required: recharge source (choose one)
recharge: true                 # Load from recharge.csv
# OR
recharge_constant: 100.0       # Use constant value
```

### Radioactive Decay

For tracers that decay radioactively (3H, 14C, 39Ar, 85Kr, etc.):

```yaml
# Decay time = half-life / ln(2)
decay_time: 17.77  # years
```

**Common decay times:**

| Tracer | Half-life | decay_time |
|--------|-----------|------------|
| Tritium (3H) | 12.32 years | 17.77 |
| Carbon-14 | 5,730 years | 8,267 |
| Krypton-85 | 10.76 years | 15.52 |
| Argon-39 | 269 years | 388 |

**Formula:** `decay_time = half_life / ln(2) = half_life / 0.693`

### Geoproduction

For tracers produced in situ in the aquifer:

```yaml
# Production rate in concentration units per year
production_rate: 0.5
```

This is used for tracers like 14C (produced by cosmic rays in the subsurface) or 4He (produced by radioactive decay of U/Th).

### Manual Date Range

If not using a recharge chronicle:

```yaml
recharge: false
recharge_constant: 100.0
datemin: 1940.0
datemax: 2025.0
```

---

## Recharge Chronicle Format

### Standard CSV Format

```csv
date,concentration
1940.0,0.01
1940.5,0.01
1941.0,0.02
...
2025.0,213.0
```

### With Comments and Metadata

```csv
# ============================================================================
# CFC-11 Atmospheric Recharge Chronicle
# ============================================================================
#
# Tracer: CFC-11 (Trichlorofluoromethane)
# Unit: pptv (parts per trillion by volume)
#
# Data Source: NOAA Global Monitoring Laboratory
# Reference: https://gml.noaa.gov/hats/combined/CFC11.html
#
# Temporal Coverage: 1940.0 - 2025.0
# Temporal Resolution: 0.5 years (semi-annual)
#
# ============================================================================
date,concentration
1940.0,0.01
1940.5,0.01
1941.0,0.02
```

### Tips for Data Quality

1. **Temporal resolution**: Use at least annual data; semi-annual is better
2. **Coverage**: Ensure data covers the expected age range of your groundwater
3. **Extrapolation**: Don't extrapolate beyond the data range
4. **Units**: Be consistent with the unit specified in the YAML file

---

## Complete Examples

### Example 1: Sulfur Hexafluoride (SF6)

A stable atmospheric tracer that is still increasing.

**sf6/sf6.yaml:**
```yaml
# SF6 Tracer Configuration
unit: pptv
recharge: true
```

**sf6/recharge.csv:**
```csv
date,concentration
1970.0,0.1
1980.0,1.0
1990.0,3.0
2000.0,5.5
2010.0,7.5
2020.0,10.5
```

### Example 2: Tritium (3H)

A radioactive tracer with the famous "bomb peak" from nuclear testing.

**3H/3H.yaml:**
```yaml
# Tritium Tracer Configuration
unit: TU
recharge: true
decay_time: 17.77  # Half-life 12.32 years / ln(2)
```

**3H/recharge.csv:**
```csv
date,concentration
1950.0,5.0
1955.0,10.0
1960.0,50.0
1963.0,5000.0    # Bomb peak
1965.0,3000.0
1970.0,1000.0
1980.0,100.0
1990.0,20.0
2000.0,10.0
2010.0,8.0
2020.0,6.0
```

### Example 3: Carbon-14 (14C)

Long-lived radioactive tracer with geoproduction.

**14C/14C.yaml:**
```yaml
# Carbon-14 Tracer Configuration
unit: pmC
recharge: true
decay_time: 8267     # Half-life 5730 years / ln(2)
production_rate: 0.5  # In-situ production
```

### Example 4: Constant Tracer (Synthetic)

For testing or simplified models.

**synthetic/synthetic.yaml:**
```yaml
# Synthetic constant tracer
unit: arbitrary
recharge: false
recharge_constant: 100.0
datemin: 1900.0
datemax: 2100.0
```

---

## Using Custom Data Sources

### From Excel Files

Convert your Excel data to CSV:

```python
import pandas as pd

# Read Excel
df = pd.read_excel("my_data.xlsx", sheet_name="Sheet1")

# Select and rename columns
df = df[['Year', 'Concentration']].copy()
df.columns = ['date', 'concentration']

# Save as CSV
df.to_csv("data_core/data_tracer/mytracer/recharge.csv", index=False)
```

### From NOAA or Other Databases

```python
import pandas as pd

# Download NOAA CFC data
url = "https://gml.noaa.gov/webdata/hats/combined/CFC11.csv"
df = pd.read_csv(url, comment='#')

# Process to required format
df_out = pd.DataFrame({
    'date': df['year'] + df['month']/12,
    'concentration': df['NH_monthly']  # Northern Hemisphere
})

df_out.to_csv("data_core/data_tracer/cfc11_updated/recharge.csv", index=False)
```

---

## Physics of Tracers

### The Convolution Equation

The measured concentration `C(t)` at time `t` is:

```
C(t) = ∫₀^∞ C_in(t - τ) × g(τ) × exp(-τ/τ_decay) dτ + C_prod
```

Where:
- `C_in(t - τ)` = Input concentration at recharge time
- `g(τ)` = Transit time distribution (from LPM)
- `exp(-τ/τ_decay)` = Radioactive decay factor
- `C_prod` = Geoproduction contribution

### Decay Correction

For radioactive tracers, the decay factor is:

```
decay_factor = exp(-τ / decay_time)
```

Where `decay_time = T_half / ln(2)`.

### Geoproduction

For tracers with in-situ production, the contribution accumulates over transit time:

```
C_prod = production_rate × τ  (no decay)
C_prod = production_rate × decay_time × (1 - exp(-τ/decay_time))  (with decay)
```

---

## Troubleshooting

### "Tracer not found"

- Check directory name matches tracer name
- Verify YAML file is named `<tracer>/<tracer>.yaml`
- Run: `python scripts/run_system_check.py`

### "FileNotFoundError: recharge.csv"

- Ensure `recharge.csv` exists in the tracer directory
- Or set `recharge: false` and use `recharge_constant`

### "Date out of range"

- Extend your recharge chronicle data
- Or adjust the sampling date in your input file

### Unexpected Concentrations

- Verify units match between YAML and input data
- Check decay_time calculation (use half-life / 0.693)
- Ensure recharge data covers the required time range

---

## Data Sources

Common atmospheric tracer data sources:

| Tracer | Source |
|--------|--------|
| CFCs, SF6 | [NOAA HATS](https://gml.noaa.gov/hats/) |
| Tritium | [IAEA GNIP](https://www.iaea.org/services/networks/gnip) |
| Carbon-14 | [IntCal](https://www.intcal.org/) |
| Noble gases | [USGS](https://water.usgs.gov/lab/) |
