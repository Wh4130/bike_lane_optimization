import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import lognorm

# ──────────────────────────────────────────────────────────────
# 1.  Log-normal parameters of R  (taken from your legend)
#     σ = 0.65   ,   μ = ln(807)  →  scale = e^μ = 807
# ──────────────────────────────────────────────────────────────
sigma  = 0.65
scale  = 807.0
r_dist = lognorm(s=sigma, scale=scale)        # SciPy “frozen” distribution

# ──────────────────────────────────────────────────────────────
# 2.  Monte-Carlo sampling
# ──────────────────────────────────────────────────────────────
N      = 200_00000
rng    = np.random.default_rng(42)

r_samples   = r_dist.rvs(size=N, random_state=rng)
phi_samples = rng.uniform(0.0, 0.5 * np.pi, size=N)        # φ ∼ U(0, π/2)

d_samples   = r_samples * (np.sin(phi_samples) + np.cos(phi_samples))

print(d_samples.mean(), r_samples.mean())
# print(d_samples.median(), r_samples.median())

# ──────────────────────────────────────────────────────────────
# 3.  Plot: histogram of d  +  log-normal PDF of r
# ──────────────────────────────────────────────────────────────
bin_width = 50.0
bins      = np.arange(0, d_samples.max() + bin_width, bin_width)


fig, ax = plt.subplots(figsize=(10, 4))

# Monte-Carlo PDF of d
ax.hist(d_samples,
        bins=bins,
        density=True,
        color="#9bbdff",
        label="Manhatten (Monte-Carlo)")

# Smooth x-grid wide enough for both curves
x_line = np.linspace(0, d_samples.max(), 600)

# Log-normal PDF of R (same y-axis: already integrates to 1)
ax.plot(x_line, r_dist.pdf(x_line),
        color="#ff7f0e", lw=2,
        label="Euclidian")

ax.set_xlabel(r"$d \;=\; R\,(\sin\phi+\cos\phi)$")
ax.set_xlim(0, 3500)
ax.set_ylabel("Probability density")
ax.set_title("Monte-Carlo distribution of $d$ with source log-normal of $R$")
ax.legend()
plt.tight_layout()
plt.show()
