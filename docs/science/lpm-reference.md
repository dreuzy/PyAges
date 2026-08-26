# LPM Scientific Reference

Lumped-parameter models describe the distribution of groundwater transit time
$T$. The keys below are the names accepted by the PyAge model registry. Runtime
availability remains discoverable with `pyage list lpms`.

| Registry key | Parameters | Scientific interpretation | Mean transit time |
|---|---|---|---|
| `dirac` | `mu` | All mass occurs at age $\mu$ (piston flow). | $\mu$ |
| `exp` | `mu` | Exponential timescale and mean. | $\mu$ |
| `exp_shifted` | `mu`, `shift` | No mass before `shift`; `mu` is the mean of the exponential component. | `shift + mu` |
| `ig` | `mu`, `sigma` | Inverse Gaussian with physical mean `mu` and standard deviation `sigma`. | `mu` |
| `ig_shifted` | `mu`, `sigma`, `shift` | Shifted inverse Gaussian; `mu` and `sigma` describe the dispersive component. | `shift + mu` |
| `gamma` | `k`, `scale` | Gamma shape $k$ and scale $\theta$. | $k\theta$ |
| `uniform` | `tmin`, `delta` | Uniform ages from `tmin` to `tmin + delta`. | `tmin + delta/2` |
| `weibull` | `k`, `lambda` | Weibull shape $k$ and scale $\lambda$. | $\lambda\Gamma(1+1/k)$ |
| `dirac_double` | `mu1`, `mu2`, `rate` | Atoms at `mu1` and `mu1 + mu2`; `rate` is the first-atom mass. | `mu1 + (1-rate)*mu2` |
| `dirac_double_1_set` | `mufree`, `rate` | One free atom and one fixed atom supplied by the programmatic workflow. | Weighted mean of the two atoms |
| `mix_exp_shifted` | `rate`, `mu1`, `mu2`, `shift` | Mass `rate` at `mu1`; remaining mass is a normalized shifted exponential beginning at `mu1 + shift`, with scale `mu2`. | `rate*mu1 + (1-rate)*(mu1+shift+mu2)` |
| `shapefree_n_oldbin` | latent `z1`, `z2`, `z3` by default | Piecewise-uniform mass over configured finite age bins; stick breaking maps latent values to non-negative fractions summing to one. | Weighted mean of bin midpoints |

## Parameter conventions that require care

For the inverse Gaussian, PyAge exposes physical moments rather than SciPy's
native shape and scale. The equivalent Péclet number is
$Pe=\mu^2/\sigma^2$. The internal SciPy conversion is documented in
{doc}`../scientific-migration-ig-decay`.

For `exp_shifted`, the median transit time is

```{math}
t_{50}=\mathrm{shift}+\mu\ln(2),
```

whereas the mean is `shift + mu`. These quantities must not be interchanged.

For `dirac_double`, `mu2` is an additional delay, not the absolute position of
the second atom. For `mix_exp_shifted`, the continuous component is normalized
before multiplication by `1-rate`; the mixing weight must not be applied twice.

The generic `shapefree_n_oldbin` model uses a finite final bin. The Holten H4
article benchmark is a distinct case-specific helper: its open-ended `>60 yr`
class is represented by a prescribed old-water tracer signature and is not a
mass located at one physical age.

## Configuration bounds are not universal science bounds

Distributed `params.yaml` files provide usable defaults for initialization,
proposal steps, bounds, and priors. They are not statements that a parameter is
physically restricted to those values in every aquifer. A study-specific file
may narrow or extend them when justified, but the resulting inference remains
conditional on those choices.

When adding a model, verify normalization, moments, CDF/quantile consistency,
partial first moments, and convolution behavior. See
{doc}`../user-guide/adding-lpm` for the implementation procedure.
