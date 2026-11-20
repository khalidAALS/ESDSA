
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator


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
    "savefig.facecolor": "white",
})

METHODS = [
    "Scoring-only",
    "Evidence-aware",
    "Traceability v2",
    "Integrated ESDSA v2",
]

COLORS = {
    "Scoring-only": "#64748B",
    "Evidence-aware": "#D08B45",
    "Traceability v2": "#527FAD",
    "Integrated ESDSA v2": "#24876C",
}

MARKERS = {
    "Scoring-only": "o",
    "Evidence-aware": "s",
    "Traceability v2": "^",
    "Integrated ESDSA v2": "D",
}


DATA = {
    "VALIDATION": {
        "Scoring-only": (144, 9),
        "Evidence-aware": (198, 26),
        "Traceability v2": (192, 26),
        "Integrated ESDSA v2": (166, 15),
    },
    "TEST": {
        "Scoring-only": (154, 3),
        "Evidence-aware": (200, 9),
        "Traceability v2": (195, 8),
        "Integrated ESDSA v2": (184, 7),
    },
}

N_RESPONSES = 216


OFFSETS = {
    "VALIDATION": {
        "Scoring-only": (9, 10),
        "Evidence-aware": (-9, -18),
        "Traceability v2": (-9, 12),
        "Integrated ESDSA v2": (-9, 12),
    },
    "TEST": {
        "Scoring-only": (9, 10),
        "Evidence-aware": (-9, 12),
        "Traceability v2": (-9, -19),
        "Integrated ESDSA v2": (-9, 12),
    },
}

fig, axes = plt.subplots(
    1, 2,
    figsize=(13.5, 5.5),
    sharex=True,
    sharey=True,
)

for ax, (partition, values) in zip(axes, DATA.items()):

    for method in METHODS:
        actionable, disagreements = values[method]

        assert 0 <= disagreements <= actionable <= N_RESPONSES

        coverage = 100 * actionable / N_RESPONSES
        disagreement = 100 * disagreements / actionable

        ax.scatter(
            coverage,
            disagreement,
            s=115,
            marker=MARKERS[method],
            color=COLORS[method],
            edgecolor="white",
            linewidth=1.1,
            zorder=5,
        )

        dx, dy = OFFSETS[partition][method]

        ax.annotate(
            f"{method}\n({coverage:.1f}%, {disagreement:.2f}%)",
            xy=(coverage, disagreement),
            xytext=(dx, dy),
            textcoords="offset points",
            ha="left" if dx >= 0 else "right",
            va="bottom" if dy >= 0 else "top",
            fontsize=8.0,
            color="#263548",
            linespacing=1.3,
        )

    ax.set_title(
        f"{partition} (n = {N_RESPONSES})",
        fontsize=12,
        fontweight="bold",
        color="#253448",
        pad=13,
    )

    ax.set_xlim(59, 106)
    ax.set_ylim(0, 17)
    ax.xaxis.set_major_locator(MultipleLocator(10))
    ax.yaxis.set_major_locator(MultipleLocator(4))

    ax.grid(
        True,
        linestyle="--",
        linewidth=0.65,
        color="#DCE3E9",
    )

    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_xlabel("Actionable coverage (%)", labelpad=10)

axes[0].set_ylabel(
    "Disagreement among actionable decisions (%)",
    labelpad=10,
)

fig.suptitle(
    "Actionable Coverage and Provisional Reference Disagreement",
    fontsize=15,
    fontweight="bold",
    color="#253448",
    y=1.04,
)

fig.text(
    0.5, -0.035,
    "Primary comparison uses AI-assisted pre-stability provisional references. "
    "Lower disagreement and higher coverage are preferable, "
    "but methods retain different response subsets.",
    ha="center",
    va="center",
    fontsize=8.3,
    color="#58687A",
)

fig.subplots_adjust(
    left=0.085,
    right=0.985,
    bottom=0.18,
    top=0.84,
    wspace=0.18,
)

for extension in ("pdf", "svg", "png"):
    path = OUTPUT_DIR / f"figure_2_coverage_disagreement.{extension}"

    save_kwargs = {
        "bbox_inches": "tight",
        "pad_inches": 0.23,
    }

    if extension == "png":
        save_kwargs["dpi"] = 350

    fig.savefig(path, **save_kwargs)

plt.close(fig)

print("Figure 2 generated successfully.")

for extension in ("pdf", "svg", "png"):
    print(
        OUTPUT_DIR /
        f"figure_2_coverage_disagreement.{extension}"
    )

print("\nVerified plotting inputs:")
for partition, values in DATA.items():
    print(f"\n{partition}")
    for method, (actionable, disagreements) in values.items():
        print(
            f"{method}: "
            f"coverage={100*actionable/N_RESPONSES:.2f}%, "
            f"disagreement={100*disagreements/actionable:.2f}%"
        )
