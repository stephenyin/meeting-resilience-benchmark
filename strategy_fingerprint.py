"""
Combine the CSV-derived metrics with the visual observations from the
sender/receiver bitrate IO graphs (zoom_merged.png / google_merged.png /
dialpad_merged.png) into a single multi-axis "strategy fingerprint" figure.

Outputs out/04_strategy_fingerprint.png
"""

from __future__ import annotations

import os
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

CSV_PATH = Path(__file__).parent / "test_result.csv"
APPS = ["Dialpad Meeting", "Zoom Workspace", "Google Meet"]
COLORS = {
    "Dialpad Meeting": "#7C3AED",
    "Zoom Workspace":  "#2D8CFF",
    "Google Meet":     "#34A853",
}

df = pd.read_csv(CSV_PATH, keep_default_na=False)
df.columns = [c.strip() for c in df.columns]

baseline = df[df["Network condition"] == "None"].iloc[0]


def _to_score(value, vmin, vmax):
    """Linear map value -> 0..5; clipped."""
    return float(np.clip((value - vmin) / (vmax - vmin) * 5.0, 0.0, 5.0))


# ---------------------------------------------------------------------------
# Build numeric axes
# ---------------------------------------------------------------------------
# CSV-derived axes (objective)
def avg_util(direction):
    rows = df[df["Network condition"].str.match(rf"^{direction}\d+kbps$")]
    caps = rows["Network condition"].str.extract(r"(\d+)").astype(int).iloc[:, 0].values
    out = {}
    for app in APPS:
        out[app] = float(np.mean(rows[app].values / caps))
    return out


def avg_loss_retention(direction):
    rows = df[df["Network condition"].str.match(rf"^{direction}\d+%$")]
    out = {}
    for app in APPS:
        out[app] = float(np.mean(rows[app].values / baseline[app]))
    return out


ul_util = avg_util("up")
dl_util = avg_util("down")
ul_loss = avg_loss_retention("up")
dl_loss = avg_loss_retention("down")
default_rate = {app: float(baseline[app]) for app in APPS}

# Visual / qualitative axes (scored 0..5 from the IO-graph inspection).
# IMPORTANT: blue line = p1 TX, orange line = p2 RX, with a media server (SFU)
# in between. So  (blue - orange)  =  loss(p1->SFU) + loss(SFU->p2)
#                                   + SFU-absorbed packets (FEC/RTX/padding).
# A persistently positive gap therefore indicates client redundancy that the
# SFU consumes / repairs from, NOT just sender-side overhead.
client_redundancy_visual = {  # client-injected FEC/RTX absorbed by the SFU
    "Dialpad Meeting": 0.5,
    "Zoom Workspace":  4.5,
    "Google Meet":     1.0,
}
probe_aggression_visual = {   # tall narrow blue spikes that DON'T cross to p2
    "Dialpad Meeting": 1.0,
    "Zoom Workspace":  4.5,
    "Google Meet":     3.0,
}
sfu_resilience_visual = {     # does the SFU shield p2 from upstream loss?
    "Dialpad Meeting": 1.0,   # transparent forwarder
    "Zoom Workspace":  4.5,   # repairs / smooths before forwarding
    "Google Meet":     1.5,   # mostly transparent, has simulcast layer drop
}
recovery_visual = {           # speed of climbing back after impairment removed
    "Dialpad Meeting": 1.0,   # gets stuck at the floor
    "Zoom Workspace":  4.5,   # continuous gradual ramp
    "Google Meet":     4.0,   # quick step jumps
}

# Assemble the radar matrix
AXES = [
    ("Default target rate",      lambda app: _to_score(default_rate[app], 0, 3500)),
    ("Uplink BW utilisation",    lambda app: _to_score(ul_util[app] * 100, 0, 100)),
    ("Downlink BW utilisation",  lambda app: _to_score(dl_util[app] * 100, 0, 100)),
    ("Uplink loss tolerance",    lambda app: _to_score(ul_loss[app] * 100, 0, 100)),
    ("Downlink loss tolerance",  lambda app: _to_score(dl_loss[app] * 100, 0, 100)),
    ("Client redundancy",        lambda app: client_redundancy_visual[app]),
    ("Probe isolation from p2",  lambda app: probe_aggression_visual[app]),
    ("SFU repair / shielding",   lambda app: sfu_resilience_visual[app]),
    ("Recovery speed",           lambda app: recovery_visual[app]),
]

scores = {app: [fn(app) for _, fn in AXES] for app in APPS}
labels = [name for name, _ in AXES]


# ---------------------------------------------------------------------------
# Figure: radar (left) + score table (right)
# ---------------------------------------------------------------------------
fig = plt.figure(figsize=(17, 8.5))
fig.suptitle(
    "Strategy fingerprint — CSV-measured + PCAP-observed behaviour\n"
    "(0 = passive/poor, 5 = aggressive/strong)",
    fontsize=14, fontweight="bold",
)

ax = fig.add_subplot(1, 2, 1, projection="polar")
N = len(labels)
angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
angles += angles[:1]

for app in APPS:
    vals = scores[app] + scores[app][:1]
    ax.plot(angles, vals, color=COLORS[app], linewidth=2.2, label=app)
    ax.fill(angles, vals, color=COLORS[app], alpha=0.12)

ax.set_xticks(angles[:-1])
ax.set_xticklabels(labels, fontsize=9)
ax.set_yticks([1, 2, 3, 4, 5])
ax.set_yticklabels(["1", "2", "3", "4", "5"], fontsize=8, color="#666")
ax.set_ylim(0, 5)
ax.grid(alpha=0.4)
ax.legend(loc="upper right", bbox_to_anchor=(1.18, 1.10), fontsize=9)

# Tabular view next to the radar
ax2 = fig.add_subplot(1, 2, 2)
ax2.axis("off")
table_data = []
header = ["Axis"] + [a.split()[0] for a in APPS]
for i, name in enumerate(labels):
    row = [name]
    for app in APPS:
        row.append(f"{scores[app][i]:.1f}")
    table_data.append(row)
tbl = ax2.table(
    cellText=table_data, colLabels=header,
    cellLoc="center", loc="center",
    colWidths=[0.48, 0.16, 0.16, 0.16],
)
tbl.auto_set_font_size(False)
tbl.set_fontsize(10)
tbl.scale(1, 1.7)

for i, app in enumerate(APPS):
    tbl[0, i + 1].set_facecolor(COLORS[app])
    tbl[0, i + 1].set_text_props(color="white", weight="bold")
tbl[0, 0].set_facecolor("#333")
tbl[0, 0].set_text_props(color="white", weight="bold")

# Highlight the best and worst per row
for i in range(len(labels)):
    vals = [scores[app][i] for app in APPS]
    best, worst = int(np.argmax(vals)), int(np.argmin(vals))
    tbl[i + 1, best + 1].set_facecolor("#E6F4EA")
    tbl[i + 1, worst + 1].set_facecolor("#FCE8E6")

plt.tight_layout(rect=[0, 0.02, 1, 0.93])
out = OUT_DIR / "04_strategy_fingerprint.png"
plt.savefig(out, dpi=150, bbox_inches="tight")
plt.close()
print(f"Wrote {out}")

# Print the underlying numbers for the record
print("\nNumeric breakdown of each axis:")
print(f"  default rate (kbps):        " + ", ".join(f"{a.split()[0]}={int(default_rate[a])}" for a in APPS))
print(f"  uplink BW util (avg):       " + ", ".join(f"{a.split()[0]}={ul_util[a]:.0%}" for a in APPS))
print(f"  downlink BW util (avg):     " + ", ".join(f"{a.split()[0]}={dl_util[a]:.0%}" for a in APPS))
print(f"  uplink loss retention (avg):" + ", ".join(f"{a.split()[0]}={ul_loss[a]:.0%}" for a in APPS))
print(f"  downlink loss retention:    " + ", ".join(f"{a.split()[0]}={dl_loss[a]:.0%}" for a in APPS))
