
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


OUTPUT_DIR = Path("figures")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.labelsize": 10,
    "axes.titlesize": 12,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "svg.fonttype": "none",
})

PARTITIONS = ["VALIDATION", "TEST"]


PREVIOUSLY_AGREED = np.array([15, 10])
PREVIOUSLY_DISAGREED = np.array([11, 1])

TOTALS = PREVIOUSLY_AGREED + PREVIOUSLY_DISAGREED

assert list(TOTALS) == [26, 11]

COLORS = {
    "agreed": "#5484B0",
    "disagreed": "#D08B45",
    "ink": "#253448",
    "muted": "#5C6D7E",
}

fig, ax = plt.subplots(figsize=(8.6, 5.9))
fig.patch.set_facecolor("white")

x = np.arange(len(PARTITIONS))
width = 0.48

bars_agreed = ax.bar(
    x,
    PREVIOUSLY_AGREED,
    width,
    label="Previously agreed with reference",
    color=COLORS["agreed"],
    edgecolor="white",
    linewidth=0.9,
)

bars_disagreed = ax.bar(
    x,
    PREVIOUSLY_DISAGREED,
    width,
    bottom=PREVIOUSLY_AGREED,
    label="Previously disagreed with reference",
    color=COLORS["disagreed"],
    edgecolor="white",
    linewidth=0.9,
)


for i in range(len(PARTITIONS)):
    if PREVIOUSLY_AGREED[i] > 0:
        ax.text(
            x[i],
            PREVIOUSLY_AGREED[i] / 2,
            str(PREVIOUSLY_AGREED[i]),
            ha="center",
            va="center",
            fontsize=13,
            fontweight="bold",
            color="white",
        )

    if PREVIOUSLY_DISAGREED[i] > 0:
        ax.text(
            x[i],
            PREVIOUSLY_AGREED[i] + PREVIOUSLY_DISAGREED[i] / 2,
            str(PREVIOUSLY_DISAGREED[i]),
            ha="center",
            va="center",
            fontsize=11,
            fontweight="bold",
            color=COLORS["ink"] if PREVIOUSLY_DISAGREED[i] <= 2 else "white",
        )

    ax.text(
        x[i],
        TOTALS[i] + 0.75,
        f"{TOTALS[i]} additional deferrals",
        ha="center",
        va="bottom",
        fontsize=10,
        fontweight="bold",
        color=COLORS["ink"],
    )

ax.set_xticks(x)
ax.set_xticklabels(PARTITIONS, fontweight="bold")

ax.set_ylabel("Additional deferred decisions")
ax.set_ylim(0, 31)
ax.set_xlim(-0.6, 1.6)

ax.set_title(
    "Composition of Stability-Based Deferrals",
    fontsize=14,
    fontweight="bold",
    color=COLORS["ink"],
    pad=20,
)

ax.grid(
    axis="y",
    linestyle="--",
    linewidth=0.65,
    color="#DCE3E9",
)
ax.set_axisbelow(True)

ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

ax.legend(
    loc="upper right",
    frameon=False,
    fontsize=9,
)

fig.text(
    0.5,
    0.035,
    "Agreement refers to AI-assisted pre-stability provisional references, "
    "not independently verified correctness.",
    ha="center",
    fontsize=8.3,
    color=COLORS["muted"],
)

fig.subplots_adjust(
    left=0.13,
    right=0.95,
    top=0.83,
    bottom=0.18,
)

for extension in ("pdf", "svg", "png"):
    path = OUTPUT_DIR / f"figure_3_stability_effects.{extension}"

    options = {
        "bbox_inches": "tight",
        "pad_inches": 0.20,
    }

    if extension == "png":
        options["dpi"] = 350

    fig.savefig(path, **options)

plt.close(fig)

print("Figure 3 generated successfully.")

for extension in ("pdf", "svg", "png"):
    print(OUTPUT_DIR / f"figure_3_stability_effects.{extension}")
