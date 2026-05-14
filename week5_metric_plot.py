"""Generate Week 5 metric trajectory plot."""
import csv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from pathlib import Path

REPO = Path(__file__).parent
CSV = REPO / "week5_results.csv"
OUT = REPO / "week5_metric_trajectory.png"

rows = []
with open(CSV, encoding="utf-8") as f:
    for r in csv.DictReader(f):
        rows.append(r)

iterations = [int(r["iteration"]) for r in rows]
win_pcts = [float(r["win_pct"]) for r in rows]
names = [r["experiment"] for r in rows]
decisions = [r["decision"] for r in rows]

# Color by category of change
categories = {
    "table_size_20M": "Search/Memory",
    "table_size_5M": "Search/Memory",
    "eval_roughness_20": "Search/Memory",
    "eval_roughness_5": "Search/Memory",
    "pawn_pst_center": "Positional (PST)",
    "knight_pst_central": "Positional (PST)",
    "bishop_value_330": "Piece Values",
    "queen_value_940": "Piece Values",
    "early_exit_0.95": "Time Management",
    "combo_table20M_roughness20": "Combination",
}
cat_colors = {
    "Search/Memory": "#4A90D9",
    "Positional (PST)": "#E8A838",
    "Piece Values": "#50C878",
    "Time Management": "#C77DFF",
    "Combination": "#FF6B6B",
}

fig, ax = plt.subplots(figsize=(12, 6))

# Plot each point
for i, (it, wp, nm, dec) in enumerate(zip(iterations, win_pcts, names, decisions)):
    cat = categories.get(nm, "Other")
    color = cat_colors.get(cat, "gray")
    marker = "o" if dec == "DISCARD" else "^"
    ax.scatter(it, wp, c=color, s=120, marker=marker, zorder=5, edgecolors="black", linewidth=0.5)

# Connect with line
ax.plot(iterations, win_pcts, color="gray", alpha=0.4, linewidth=1, zorder=2)

# Reference lines
ax.axhline(y=55, color="green", linestyle="--", linewidth=1.5, alpha=0.7, label="KEEP threshold (55%)")
ax.axhline(y=50, color="gray", linestyle=":", linewidth=1, alpha=0.5, label="50% (no effect)")
# Null-condition band from Week 4: mean=55%, std=4%
ax.axhspan(51, 59, color="red", alpha=0.08, label="Null-condition band (Week 4: 55+/-4%)")

# Labels on each point
for it, wp, nm in zip(iterations, win_pcts, names):
    short = nm.replace("_", "\n")
    ax.annotate(nm, (it, wp), textcoords="offset points",
                xytext=(0, 14), ha="center", fontsize=6.5, rotation=30)

ax.set_xlabel("Iteration", fontsize=12)
ax.set_ylabel("Win Rate vs Baseline (%)", fontsize=12)
ax.set_title("Week 5 Autonomous Block: Metric Trajectory (10 iterations)", fontsize=14, fontweight="bold")
ax.set_xticks(iterations)
ax.set_ylim(35, 65)
ax.set_xlim(min(iterations) - 0.5, max(iterations) + 0.5)
ax.grid(True, alpha=0.3)

# Legend for categories
handles = [mpatches.Patch(color=c, label=l) for l, c in cat_colors.items()]
handles.append(plt.Line2D([0], [0], color="green", linestyle="--", label="KEEP threshold (55%)"))
handles.append(plt.Line2D([0], [0], color="gray", linestyle=":", label="50% null"))
ax.legend(handles=handles, loc="lower left", fontsize=8, framealpha=0.9)

# Stats annotation
mean_wp = np.mean(win_pcts)
std_wp = np.std(win_pcts)
ax.text(0.98, 0.02, f"Mean: {mean_wp:.1f}%  Std: {std_wp:.1f}pp\nKEEPs: 0/10  Best: {max(win_pcts):.0f}%",
        transform=ax.transAxes, ha="right", va="bottom", fontsize=9,
        bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow", alpha=0.9))

plt.tight_layout()
plt.savefig(OUT, dpi=150)
print(f"Saved: {OUT}")
