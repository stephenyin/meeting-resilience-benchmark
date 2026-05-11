"""
Analyze sender-side bitrate behavior of Dialpad Meeting / Zoom Workspace / Google Meet
under various network impairments (1 v 1, p1 -> p2, p1 sender bitrate measured, kbps).

Generates a multi-panel PNG with comparisons, plus prints a textual analysis of the
congestion-control / rate-adaptation differences between the three apps.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

OUT_DIR = Path(__file__).parent / "out"
OUT_DIR.mkdir(exist_ok=True)
_CACHE = OUT_DIR / ".cache"
_CACHE.mkdir(exist_ok=True)
os.environ["MPLCONFIGDIR"] = str(_CACHE / "matplotlib")
os.environ["XDG_CACHE_HOME"] = str(_CACHE)
os.environ["FONTCONFIG_PATH"] = str(_CACHE / "fontconfig")
for sub in ("matplotlib", "fontconfig"):
    (_CACHE / sub).mkdir(exist_ok=True)

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

CSV_PATH = Path(__file__).parent / "Dialpad test result - Sheet1.csv"

APPS = ["Dialpad Meeting", "Zoom Workspace", "Google Meet"]
COLORS = {
    "Dialpad Meeting": "#7C3AED",   # purple
    "Zoom Workspace":  "#2D8CFF",   # blue
    "Google Meet":     "#34A853",   # green
}


# ---------------------------------------------------------------------------
# Load + classify
# ---------------------------------------------------------------------------
def parse_condition(cond: str):
    """Return (direction, kind, magnitude) for a condition label.

    direction: 'up' | 'down' | 'none'
    kind:      'loss' | 'bw' | 'delay' | 'none'
    magnitude: numeric value of the impairment (percent / kbps / ms)
    """
    if cond.lower() == "none":
        return ("none", "none", 0)
    m = re.match(r"(up|down)(\d+)(%|kbps|ms)", cond)
    if not m:
        raise ValueError(f"Unrecognized condition: {cond}")
    direction, val, unit = m.group(1), int(m.group(2)), m.group(3)
    kind = {"%": "loss", "kbps": "bw", "ms": "delay"}[unit]
    return (direction, kind, val)


df = pd.read_csv(CSV_PATH, keep_default_na=False)
df.columns = [c.strip() for c in df.columns]
df[["direction", "kind", "magnitude"]] = df["Network condition"].apply(
    lambda c: pd.Series(parse_condition(c))
)
df["magnitude"] = df["magnitude"].astype(int)

baseline = df[df["kind"] == "none"].iloc[0]


# ---------------------------------------------------------------------------
# Figure: 2x3 panels — (uplink/downlink) x (loss / bandwidth / delay)
# ---------------------------------------------------------------------------
fig, axes = plt.subplots(2, 3, figsize=(18, 10))
fig.suptitle(
    "p1 sender bitrate (kbps) vs. network impairment — Dialpad / Zoom / Google Meet\n"
    "1v1 call, p1 → p2; dashed line = no-impairment baseline",
    fontsize=14, fontweight="bold",
)

PANELS = [
    ("up",   "loss",  "Uplink random packet loss",   "Loss (%)",      "%"),
    ("up",   "bw",    "Uplink bandwidth cap",        "Cap (kbps)",    "kbps"),
    ("up",   "delay", "Uplink one-way delay",        "Delay (ms)",    "ms"),
    ("down", "loss",  "Downlink random packet loss", "Loss (%)",      "%"),
    ("down", "bw",    "Downlink bandwidth cap",      "Cap (kbps)",    "kbps"),
    ("down", "delay", "Downlink one-way delay",      "Delay (ms)",    "ms"),
]

for ax, (direction, kind, title, xlabel, unit) in zip(axes.flat, PANELS):
    sub = (
        df[(df["direction"] == direction) & (df["kind"] == kind)]
        .sort_values("magnitude")
        .reset_index(drop=True)
    )
    x = np.arange(len(sub))
    width = 0.26

    for i, app in enumerate(APPS):
        bars = ax.bar(
            x + (i - 1) * width, sub[app], width,
            label=app, color=COLORS[app], edgecolor="white", linewidth=0.5,
        )
        for b, v in zip(bars, sub[app]):
            ax.text(b.get_x() + b.get_width() / 2, v + 40, f"{int(v)}",
                    ha="center", va="bottom", fontsize=8)

    # Bandwidth-cap reference: dotted line = the cap itself
    if kind == "bw":
        for xi, mag in zip(x, sub["magnitude"]):
            ax.hlines(mag, xi - 1.5 * width, xi + 1.5 * width,
                      colors="black", linestyles=":", linewidth=1)
        ax.plot([], [], ls=":", color="black", label="Bandwidth cap")

    # Baseline reference per app
    for app in APPS:
        ax.axhline(baseline[app], ls="--", color=COLORS[app],
                   alpha=0.35, linewidth=1)

    ax.set_xticks(x)
    ax.set_xticklabels([f"{m}{unit}" for m in sub["magnitude"]])
    ax.set_title(title, fontsize=11, fontweight="bold")
    ax.set_xlabel(xlabel)
    ax.set_ylabel("p1 send bitrate (kbps)")
    ax.set_ylim(0, max(3300, df[APPS].values.max() * 1.1))
    ax.grid(axis="y", alpha=0.3)
    ax.legend(fontsize=8, loc="upper right")

plt.tight_layout(rect=[0, 0.02, 1, 0.95])
panel_path = OUT_DIR / "01_panels_by_impairment.png"
plt.savefig(panel_path, dpi=150)
plt.close()


# ---------------------------------------------------------------------------
# Figure: line plots — degradation curves vs. magnitude
# ---------------------------------------------------------------------------
fig, axes = plt.subplots(2, 2, figsize=(15, 10))
fig.suptitle("Sensitivity curves — how send bitrate degrades with impairment",
             fontsize=14, fontweight="bold")

CURVE_PANELS = [
    ("loss",  "up",   "Uplink loss sensitivity",   "Loss (%)"),
    ("loss",  "down", "Downlink loss sensitivity", "Loss (%)"),
    ("bw",    "up",   "Uplink bandwidth utilization",   "Available cap (kbps)"),
    ("bw",    "down", "Downlink bandwidth utilization", "Available cap (kbps)"),
]

for ax, (kind, direction, title, xlabel) in zip(axes.flat, CURVE_PANELS):
    sub = (
        df[(df["direction"] == direction) & (df["kind"] == kind)]
        .sort_values("magnitude")
    )
    for app in APPS:
        ax.plot(sub["magnitude"], sub[app], marker="o", linewidth=2.2,
                color=COLORS[app], label=app, markersize=8)
        for m, v in zip(sub["magnitude"], sub[app]):
            ax.annotate(f"{int(v)}", (m, v), textcoords="offset points",
                        xytext=(6, 6), fontsize=8, color=COLORS[app])
    if kind == "bw":
        caps = sorted(sub["magnitude"].unique())
        ax.plot(caps, caps, ls=":", color="black",
                label="100% utilisation (= cap)")

    ax.set_title(title, fontsize=11, fontweight="bold")
    ax.set_xlabel(xlabel)
    ax.set_ylabel("p1 send bitrate (kbps)")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=9)

plt.tight_layout(rect=[0, 0.02, 1, 0.95])
curve_path = OUT_DIR / "02_sensitivity_curves.png"
plt.savefig(curve_path, dpi=150)
plt.close()


# ---------------------------------------------------------------------------
# Figure: bandwidth utilisation ratio + retention-at-loss heatmap
# ---------------------------------------------------------------------------
fig, axes = plt.subplots(1, 2, figsize=(16, 6))

# (a) bandwidth utilisation ratio  (sent / cap)
ax = axes[0]
bw_rows = df[df["kind"] == "bw"].copy()
bw_rows["label"] = bw_rows["direction"] + " " + bw_rows["magnitude"].astype(str) + "kbps"
bw_rows = bw_rows.sort_values(["direction", "magnitude"], ascending=[True, False])
x = np.arange(len(bw_rows))
width = 0.26
for i, app in enumerate(APPS):
    ratios = bw_rows[app] / bw_rows["magnitude"]
    bars = ax.bar(x + (i - 1) * width, ratios, width,
                  label=app, color=COLORS[app])
    for b, r in zip(bars, ratios):
        ax.text(b.get_x() + b.get_width() / 2, r + 0.02, f"{r:.0%}",
                ha="center", va="bottom", fontsize=8)
ax.axhline(1.0, ls="--", color="black", alpha=0.6, label="cap = 100%")
ax.set_xticks(x)
ax.set_xticklabels(bw_rows["label"], rotation=20)
ax.set_ylabel("send bitrate ÷ link cap")
ax.set_title("Bandwidth utilisation efficiency under hard caps",
             fontsize=12, fontweight="bold")
ax.set_ylim(0, 1.25)
ax.grid(axis="y", alpha=0.3)
ax.legend(fontsize=9)

# (b) bitrate retention vs. baseline under loss
ax = axes[1]
loss_rows = df[df["kind"] == "loss"].copy()
loss_rows["label"] = loss_rows["direction"] + " " + loss_rows["magnitude"].astype(str) + "%"
loss_rows = loss_rows.sort_values(["direction", "magnitude"])
matrix = np.array([
    loss_rows[app].values / baseline[app] for app in APPS
])
im = ax.imshow(matrix, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1.1)
ax.set_xticks(range(len(loss_rows)))
ax.set_xticklabels(loss_rows["label"], rotation=20)
ax.set_yticks(range(len(APPS)))
ax.set_yticklabels(APPS)
for i in range(matrix.shape[0]):
    for j in range(matrix.shape[1]):
        ax.text(j, i, f"{matrix[i, j]:.0%}",
                ha="center", va="center",
                color="black" if matrix[i, j] > 0.4 else "white",
                fontsize=10, fontweight="bold")
ax.set_title("Bitrate retention vs. clean-network baseline (under packet loss)",
             fontsize=12, fontweight="bold")
fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02, label="retention ratio")

plt.tight_layout()
heat_path = OUT_DIR / "03_efficiency_and_retention.png"
plt.savefig(heat_path, dpi=150)
plt.close()


# ---------------------------------------------------------------------------
# Textual analysis
# ---------------------------------------------------------------------------
def fmt(row, app):
    return f"{int(row[app]):>5d}"

print("=" * 78)
print(" Sender-bitrate behaviour summary  (all values kbps; p1 sender of 1v1 call)")
print("=" * 78)

print("\n[Baseline — no impairment]")
for app in APPS:
    print(f"  {app:<18s} {int(baseline[app]):>5d} kbps")

print("\n[Bandwidth utilisation under hard caps]  utilisation = sent / cap")
util = df[df["kind"] == "bw"].copy()
util["label"] = util["direction"] + util["magnitude"].astype(str) + "kbps"
for _, r in util.iterrows():
    parts = [f"{r['label']:<14s}"]
    for app in APPS:
        parts.append(f"{app.split()[0]}={int(r[app]):>4d} ({r[app]/r['magnitude']:>4.0%})")
    print("  " + "  ".join(parts))

print("\n[Bitrate retention under packet loss]  retention = sent / baseline")
loss = df[df["kind"] == "loss"].copy()
for _, r in loss.iterrows():
    parts = [f"{r['direction']}{r['magnitude']}%".ljust(8)]
    for app in APPS:
        parts.append(f"{app.split()[0]}={int(r[app]):>4d} ({r[app]/baseline[app]:>4.0%})")
    print("  " + "  ".join(parts))

print("\n[Behaviour under added one-way delay]")
delay = df[df["kind"] == "delay"].copy()
for _, r in delay.iterrows():
    parts = [f"{r['direction']}{r['magnitude']}ms".ljust(10)]
    for app in APPS:
        parts.append(f"{app.split()[0]}={int(r[app]):>4d}")
    print("  " + "  ".join(parts))


# ---------------------------------------------------------------------------
# Qualitative observations  (printed for the operator)
# ---------------------------------------------------------------------------
NOTES = """
==============================================================================
 Congestion-control / rate-adaptation observations
==============================================================================

1. Default target rate (no impairment)
   - Google Meet  : 3000 kbps  → most aggressive default; targets HD by default.
   - Dialpad      : 1700 kbps  → moderate.
   - Zoom         : 1200 kbps  → most conservative default; leaves headroom.

2. Uplink bandwidth caps (sender knows the bottleneck)
   - Zoom fills the pipe almost perfectly (100% / 100% / 93% at 1000/500/300).
   - Google Meet also fills well (90% / 98% / 90%).
   - Dialpad systematically *under-utilises* (85% / 50% / 67%) — its probing /
     ramp-up appears very conservative; even with a clean 1 Mbps pipe it only
     reaches 850 kbps.

3. Uplink random loss (classic GCC / loss-based trigger territory)
   - Zoom is the most loss-tolerant: holds 1200–1500 kbps from 0% all the way
     to 30% loss. Strongly suggests heavy FEC / packet redundancy plus a
     loss-tolerant rate controller, not a pure loss-based AIMD.
   - Google Meet keeps the full 3000 kbps up to ~10%, then collapses to
     380 kbps @20% and 80 kbps @30% — a sharp loss-based threshold consistent
     with WebRTC GCC's loss-based controller (~10% trigger).
   - Dialpad shows the steepest cliff: 1700 → 1200 (10%) → 170 (20%) → 100
     (30%). Lowest tolerance to uplink loss of the three.

4. Downlink loss / bw / delay (impairment is on the receiver side)
   This row stresses the *feedback path*: the sender only learns about
   downlink trouble through RTCP/REMB/transport-CC reports.
   - Zoom keeps 900–1300 kbps across every downlink condition — its receiver
     feedback evidently distinguishes "bandwidth limited" from "use less".
   - Google Meet behaves symmetrically to its uplink case: holds the
     bandwidth, collapses on heavy loss (250 → 80).
   - Dialpad pins the rate at ~270 kbps the moment *any* downlink impairment
     is reported (loss, cap, even +100 ms delay) and refuses to recover.
     This looks like a hard fallback floor / "safe mode" triggered by any
     receiver-reported anomaly rather than a per-symptom controller.

5. Added one-way delay
   - Google Meet and Dialpad are largely insensitive to +100/+200 ms uplink
     delay (consistent with delay-based BWE that keys off *queue growth*,
     not absolute RTT).
   - Zoom actually *raises* its rate at up200ms (1000 → 2000) — likely a
     probing artefact when queue is steady. On the downlink side Zoom is
     again the most stable.
   - Dialpad's downlink-delay reaction (locked at 270) is the same fallback
     floor as the downlink loss / cap cases, which strongly implies a single
     state machine that demotes to a "safe" rate on any receiver complaint.

6. Net take-aways
   - Zoom  : conservative default + strong FEC + bandwidth-aware controller.
             Best resilience overall, sometimes leaves performance on the
             table on a clean network.
   - Google: aggressive default + classical GCC behaviour. Best on clean
             networks, but loss-based collapse above ~10% packet loss.
   - Dialpad: aggressive *cliff* on uplink loss and a coarse "safe mode"
             reaction to any downlink impairment. Two clear improvement
             targets: (a) make uplink ramp-up/probing more aggressive so it
             actually fills the pipe like Zoom/Meet do, and (b) replace the
             single-floor downlink fallback (~270 kbps) with a controller
             that distinguishes between bandwidth-limited and loss-driven
             feedback.
==============================================================================
"""
print(NOTES)

print(f"Charts written to:\n  {panel_path}\n  {curve_path}\n  {heat_path}")
