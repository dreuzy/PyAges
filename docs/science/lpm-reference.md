# LPM Scientific Reference

Lumped-parameter models describe the distribution of groundwater transit time
$T$. The keys below are the names accepted by the PyAges model registry. Runtime
availability remains discoverable with `pyages list lpms`.

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
| `dirac_double_1_set` | `mufree`, `rate` | Constrained `dirac_double` variant with one free atom and one fixed atom supplied by the programmatic workflow. | Weighted mean of the two atoms |
| `mix_exp_shifted` | `rate`, `mu1`, `mu2`, `shift` | Mass `rate` at `mu1`; remaining mass is a normalized shifted exponential beginning at `mu1 + shift`, with scale `mu2`. | `rate*mu1 + (1-rate)*(mu1+shift+mu2)` |
| `shapefree_n_oldbin` | latent `z1`, `z2`, `z3` by default | Piecewise-uniform mass over configured finite age bins; stick breaking maps latent values to non-negative fractions summing to one. | Weighted mean of bin midpoints |

## Mathematical definitions

Let $T$ be transit time in years, $g(t)$ a continuous probability density,
$\delta_a$ a unit point mass at age $a$, and $r=\mathtt{rate}$. Every model
below has total probability one before the finite recharge-history truncation
described in {doc}`../scientific-methods`.

### Point-mass families

`dirac` is the piston-flow measure

```{math}
dF(t)=\delta_{\mu}(dt),
\qquad E[T]=\mu,
```

with `mu` in years. Scientific convolution evaluates the tracer response
directly at age $\mu$.

`dirac_double` is

```{math}
dF(t)=r\,\delta_{\mu_1}(dt)
 +(1-r)\,\delta_{\mu_1+\mu_2}(dt),
\qquad E[T]=\mu_1+(1-r)\mu_2.
```

`mu1` is the first age and `mu2` is the non-negative **additional delay** to
the second age. `rate` is dimensionless and lies in $[0,1]$. Either endpoint
reduces the model to one effective point mass; `mu2 = 0` makes the two atoms
coincident.

`dirac_double_1_set` uses the same family with one programmatically fixed age
$\mu_{set}$:

```{math}
dF(t)=r\,\delta_{\mu_{free}}(dt)
 +(1-r)\,\delta_{\mu_{set}}(dt).
```

Only `mufree` and `rate` are calibrated from `params.yaml`. `muset` is a
constructor argument, defaults to 70 years, and must be recorded by any
workflow that changes it. This variant is intended for workflows that possess
an externally fixed end member; it is not a third point-mass family.

The `pdf()` methods of these models return normalized finite-width
approximations so generic sampling and plotting code can display them. Those
approximations are never used for scientific convolution.

### Exponential families

For `exp`, `mu` is both the scale and mean in years:

```{math}
g(t)=\frac{1}{\mu}\exp\left(-\frac{t}{\mu}\right),
\quad t\geq0,\qquad E[T]=\mu,
```

with $\mu>0$. The density is maximal at age zero and has an infinite old-age
tail; interpretations requiring a minimum age should use a shifted family.

For `exp_shifted`, with $s=\mathtt{shift}$,

```{math}
g(t)=\frac{1}{\mu}\exp\left[-\frac{t-s}{\mu}\right]
1(t\geq s),
\qquad E[T]=s+\mu.
```

`mu` is the component scale, not the total mean. `shift` is the lower support
bound. The median is $s+\mu\ln 2$.

### Gamma, uniform, and Weibull families

For `gamma`, `k` is dimensionless and `scale` is $\theta$ in years:

```{math}
g(t)=\frac{t^{k-1}e^{-t/\theta}}
{\Gamma(k)\theta^k},
\quad t\geq0,
\qquad E[T]=k\theta,
```

with $k>0$ and $\theta>0$. $k=1$ is the exponential family. For $k<1$ the
density is singular at zero but remains integrable.

For `uniform`, $a=\mathtt{tmin}$ and
$d=\mathtt{delta}>0$:

```{math}
g(t)=\frac{1}{d}1(a\leq t\leq a+d),
\qquad E[T]=a+\frac{d}{2}.
```

`delta` is a width, not the upper support bound.

For `weibull`, `k` is dimensionless and `lambda` is the scale $\lambda_W$ in
years:

```{math}
g(t)=\frac{k}{\lambda_W}
\left(\frac{t}{\lambda_W}\right)^{k-1}
\exp\left[-\left(\frac{t}{\lambda_W}\right)^k\right],
\quad t\geq0,
```

```{math}
E[T]=\lambda_W\Gamma\left(1+\frac{1}{k}\right),
\qquad k>0,\quad\lambda_W>0.
```

`k = 1` is exponential. `k < 1` gives a decreasing density with a singular
limit at zero; `k > 1` gives an interior mode.

### Inverse-Gaussian families

For `ig`, `mu` is the physical mean $M$ and `sigma` is the physical standard
deviation $S$, both in years:

```{math}
g(t)=\sqrt{\frac{\lambda}{2\pi t^3}}
\exp\left[-\frac{\lambda(t-M)^2}{2M^2t}\right],
\quad t>0,
\qquad \lambda=\frac{M^3}{S^2}.
```

$M>0$ and $S>0$. The equivalent Péclet number under the convention used by
PyAges is $Pe=M^2/S^2$. These are not SciPy's native inverse-Gaussian
coordinates; the exact conversion and numerical treatment are in
{doc}`../scientific-methods`.

For `ig_shifted`, $T=s+X$, where $X$ follows the preceding distribution:

```{math}
g_T(t)=g_X(t-s)1(t>s),
\qquad E[T]=s+M,
\qquad \operatorname{sd}(T)=S.
```

`mu` and `sigma` describe the unshifted dispersive component; `shift` is the
lower support bound and must not be added to `sigma`.

### Mixed shifted-exponential family

`mix_exp_shifted` combines an exact young component at $\mu_1$ with a
normalized exponential component whose support begins at $\mu_1+s$:

```{math}
dF(t)=r\,\delta_{\mu_1}(dt)
 +(1-r)\frac{1}{\mu_2}
 \exp\left[-\frac{t-(\mu_1+s)}{\mu_2}\right]
 1(t\geq\mu_1+s)\,dt.
```

Here `rate` is in $[0,1]$, `mu1`, `mu2`, and `shift` are in years, and
`mu2 > 0`. `rate = 1` removes the continuous component; `rate = 0` removes
the point mass. The ordinary `pdf()` contains only the weighted continuous
density because an exact atom has no finite density value.

### Shape-free family

For configured finite edges $0=a_0<a_1<\dots<a_J$ and physical fractions
$f_1,\dots,f_J\geq0$ summing to one, `shapefree_n_oldbin` is piecewise
uniform:

```{math}
g(t)=\frac{f_j}{a_j-a_{j-1}},
\quad a_{j-1}\leq t<a_j.
```

With latent parameters $z_1,\dots,z_{J-1}$ and
$v_j=(1+e^{-z_j})^{-1}$, the stick-breaking transformation is

```{math}
f_j=v_j\prod_{k<j}(1-v_k),
\qquad
f_J=\prod_{k<J}(1-v_k).
```

In `bounded` mode all edges, including the upper edge of the old bin, are
explicit. In `support_open` mode the configured last edge starts the old bin
and `support_end_max` supplies its finite effective upper edge. Edges must be
finite, strictly increasing, and start at zero. The model does not represent
an infinite old-water tail.

## Packaged calibration ranges

The following inclusive ranges are shipped in `data_core/data_lpm`. They are
finite runtime calibration ranges for the default files, not mathematical
domains or universal physical limits. Each YAML now records its mathematical
domain separately.

| Model | Packaged calibration ranges |
|---|---|
| `dirac` | `mu`: [0, 100] yr |
| `dirac_double` | `mu1`: [0, 70] yr; `mu2`: [0, 70] yr; `rate`: [0, 1] |
| `dirac_double_1_set` | `mufree`: [0, 70] yr; `rate`: [0, 1] |
| `exp` | `mu`: [0.1, 100] yr |
| `exp_shifted` | `mu`: [0.1, 70] yr; `shift`: [0, 70] yr |
| `gamma` | `k`: [0.1, 10]; `scale`: [0.1, 80] yr |
| `ig` | `mu`: [0.1, 70] yr; `sigma`: [0.1, 70] yr |
| `ig_shifted` | `mu`: [0.1, 100] yr; `sigma`: [0.1, 30] yr; `shift`: [0.1, 50] yr |
| `mix_exp_shifted` | `rate`: [0, 1]; `mu1`, `mu2`, `shift`: [0.1, 50] yr |
| `shapefree_n_oldbin` | default `z1`, `z2`, `z3`: [-8, 8] each; edges: [0, 20, 40, 60, 200] yr |
| `uniform` | `tmin`: [0, 100] yr; `delta`: [0.5, 100] yr |
| `weibull` | `k`: [0.1, 10]; `lambda`: [0.1, 100] yr |

## Parameter conventions that require care

For the inverse Gaussian, PyAges exposes physical moments rather than SciPy's
native shape and scale. The equivalent Péclet number is
$Pe=\mu^2/\sigma^2$. The internal SciPy conversion is documented in
{doc}`../scientific-migration-ig-decay`.

For `exp_shifted`, the median transit time is

```{math}
t_{50}=\mathrm{shift}+\mu\ln(2),
```

whereas the mean is `shift + mu`. These quantities must not be interchanged.

For `dirac_double`, `mu2` is an additional delay, not the absolute position of
the second atom. The registered `dirac_double_1_set` key is a constrained
parameterization of this same scientific Double-Dirac family: `muset` is fixed
at construction, while `mufree` and the dimensionless `rate` are managed
parameters, and convolution still uses `DIRAC_DOUBLE`. It is not an additional
scientific family. For `mix_exp_shifted`, the continuous component is
normalized before multiplication by `1-rate`; the mixing weight must not be
applied twice.

The generic `shapefree_n_oldbin` model uses a finite final bin. The Holten H4
article benchmark is a distinct case-specific helper: its open-ended `>60 yr`
class is represented by a prescribed old-water tracer signature and is not a
mass located at one physical age.

## Calibration ranges are not universal mathematical domains

Distributed `params.yaml` files provide usable defaults for initialization,
proposal steps, calibration ranges, and priors. The separate `domain` field
states formula validity. A study-specific file may narrow or extend a
calibration range inside that domain when justified, but the resulting
inference remains conditional on that choice.

When adding a model, verify normalization, moments, CDF/quantile consistency,
partial first moments, and convolution behavior. See
{doc}`../user-guide/adding-lpm` for the implementation procedure.
