import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import gamma
from scipy.stats import lognorm, kstest
import matplotlib.ticker as mticker


def approxLocalDemand(r, n=3, a=0.0012):
    # simpler approximate form of the distance dependent demand, should be fster to calculate
    # default paramters already a good fit for our data
    return 1 / ((r * a)**n + 1)


if __name__ == "__main__":
    # Load the pivot table
    df_2d = pd.read_parquet("../data/processed/travelMatrix_sum.parquet")  
    df_distance_2d = pd.read_parquet("../data/processed/travelMatrix_distanceMeters.parquet")

    # Flatten both pivot tables into 1D arrays
    x = df_distance_2d.values.flatten()
    y = df_2d.values.flatten()

    maxDistance = 4000
    mask = (
        ~np.isnan(x) & ~np.isnan(y) & 
        (x > 0) & (x <= maxDistance) & 
        (y > 0) & (y <= maxDistance)
    )

    x_clean = x[mask]
    y_clean = y[mask]

    # ───────────────────────── 1. Histogram bins ───────────────────────────────
    bin_width = 50.0                                       # adjust to taste
    bins       = np.arange(0, x_clean.max() + bin_width, bin_width)
    counts, edges = np.histogram(x_clean, bins=bins, weights=y_clean)
    centres        = edges[:-1] + np.diff(edges) / 2
    total_trips    = y_clean.sum()

    # cumulative (normalised to 1)
    cum_counts = np.concatenate([[0], counts.cumsum()])
    cum_emp_n  = cum_counts / cum_counts[-1]

    # ──────────────────────── 2. Gamma fit (weighted) ──────────────────────────
    w     = y_clean
    mu_w  = np.average(x_clean, weights=w)
    var_w = np.average((x_clean - mu_w) ** 2, weights=w)
    k_hat     = mu_w ** 2 / var_w
    theta_hat = var_w / mu_w
    gamma_dist = gamma(a=k_hat, scale=theta_hat)

    # ──────────────────────── 3. Log-normal fit (replicated) ───────────────────
    x_rep = np.repeat(x_clean, np.round(y_clean).astype(int))
    sigma_hat, loc_hat, scale_hat = lognorm.fit(x_rep, floc=0)
    logn_dist = lognorm(s=sigma_hat, scale=scale_hat)

    # ──────────────────────── 4. Smooth curves (NO normalisation) ──────────────
    x_line = np.linspace(0, edges[-1], 600)
    pdf_gamma = gamma_dist.pdf(x_line) * bin_width * total_trips
    pdf_logn  = logn_dist.pdf(x_line)  * bin_width * total_trips
    cdf_gamma = gamma_dist.cdf(x_line)
    cdf_logn  = logn_dist.cdf(x_line)

    # ──────────────────────── 5. Colours & style helpers ───────────────────────
    DARK_BLUE  = "#1f77b4"
    LIGHT_BLUE = "#c6ddff"

    # ───────────────────────── 6. Plotting ─────────────────────────────────────
    fig, (ax_hist, ax_cdf, ax_demand) = plt.subplots(
        3, 1, figsize=(10, 7), sharex=True,
        gridspec_kw={"height_ratios": [2, 1, 1], "hspace": 0.1}
    )

    # -- 6a Histogram  (filled + step outline) ----------------------------------
    ax_hist.bar(centres, counts,
                width=np.diff(edges),
                color=LIGHT_BLUE, edgecolor="none")

    # top edges as a step line
    ax_hist.stairs(counts, edges, color=DARK_BLUE, linewidth=1.5,
                label="Data")

    ax_hist.plot(x_line, pdf_gamma, lw=2, color="#ff7f0e",
                label=fr"Gamma PDF $k={k_hat:.2f},\ \theta={theta_hat:.1f}$")
    ax_hist.plot(x_line, pdf_logn,  lw=2, color="#2ca02c",
                label=fr"Log-normal PDF $\sigma={sigma_hat:.2f},\ \mu=\ln({scale_hat:.1f})$")

    ax_hist.set_ylabel("Number of trips")
    ax_hist.set_title("Travel-distance distribution")
    ax_hist.legend()

    # -- 6b Cumulative  (same colour scheme) ------------------------------------
    ax_cdf.fill_between(edges, 0, cum_emp_n, step="post",
                        color=LIGHT_BLUE, alpha=0.6)
    ax_cdf.step(edges, cum_emp_n, where="post",
                color=DARK_BLUE, linewidth=1.5, label="Data cumulative")

    ax_cdf.plot(x_line, cdf_gamma, lw=2, color="#ff7f0e", label="Gamma CDF")
    ax_cdf.plot(x_line, cdf_logn, lw=2, color="#2ca02c", label="Log-normal CDF")

    ax_cdf.set_ylabel("Cum. proportion")
    ax_cdf.legend(loc=4)


    # -- Demand plot --------------
    ax_demand.plot(x_line, 1-cdf_logn, lw=2, color="#2ca02c", label="rel. demand = 1 - Log-normal CDF")
    ax_demand.plot(x_line, 1/((x_line*0.0012)**1 + 1), lw=2, color="blue", linestyle="--", label="approx. as:   $\\frac{1}{r \cdot 0.0012 + 1}$")
    ax_demand.plot(x_line, 1/((x_line*0.0012)**3 + 1), lw=2, color="red", linestyle="--", label="approx. as:   $\\frac{1}{(r \cdot 0.0012)^3 + 1}$")

    ax_demand.set_xlabel(f"Distance r / m ")
    ax_demand.set_ylabel("rel. demand")
    ax_demand.set_ylim(0, 1.05)
    ax_demand.legend(loc=1)

    # -- Plotting adjustment
    ax_hist.set_xlim(0, 3000)
    ax_hist.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, pos: f"{x/1_000:.0f}k"))
    ax_hist.set_ylabel("Number of trips")   # optional: clarify the unit

    ax_cdf.set_ylim(0, 1.05)

    plt.tight_layout()
    plt.show()

    # ───────────────────────── 7. Goodness-of-fit summary (optional) ───────────
    ll_gamma = gamma_dist.logpdf(x_rep).sum()
    ll_logn  = logn_dist.logpdf(x_rep).sum()
    AIC_gamma = 2*2 - 2*ll_gamma
    AIC_logn  = 2*2 - 2*ll_logn
    D_gamma   = kstest(x_rep,  gamma_dist.cdf).statistic
    D_logn    = kstest(x_rep,  logn_dist.cdf).statistic

    print("Fit quality:")
    print(f"  AIC   – Gamma: {AIC_gamma:,.0f} | Log-normal: {AIC_logn:,.0f}")
    print(f"  KS-D  – Gamma: {D_gamma:.4f}  | Log-normal: {D_logn:.4f}")

