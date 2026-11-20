
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT_DIR = Path("figures")
OUT_DIR.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "svg.fonttype": "none",
})

COLORS = {
    "ink": "#243446",
    "muted": "#637487",
    "line": "#607286",
    "input": "#EAF1F8",
    "assessment": "#E7F1FA",
    "trace": "#EDF0FA",
    "policy": "#E5F2EE",
    "equivalence": "#FFF2D9",
    "decision": "#F2F5F8",
    "defer": "#FBE9E6",
    "white": "#FFFFFF",
}

fig, ax = plt.subplots(figsize=(14, 10))
fig.patch.set_facecolor("white")

ax.set_xlim(0, 14)
ax.set_ylim(0, 10)
ax.axis("off")


def box(x, y, w, h, title, subtitle="", color="white",
        title_size=10, subtitle_size=8.5):
    rect = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.025,rounding_size=0.12",
        linewidth=1.15,
        edgecolor=COLORS["line"],
        facecolor=color,
        zorder=2,
    )
    ax.add_patch(rect)

    if subtitle:
        ax.text(
            x + w / 2, y + h * 0.76,
            title, ha="center", va="center",
            fontsize=title_size, fontweight="bold",
            color=COLORS["ink"], zorder=3,
        )
        ax.text(
            x + w / 2, y + h * 0.36,    
            subtitle, ha="center", va="center",
            fontsize=subtitle_size,
            color=COLORS["muted"],
            linespacing=1.3, zorder=3,
        )
    else:
        ax.text(
            x + w / 2, y + h / 2,
            title, ha="center", va="center",
            fontsize=title_size, fontweight="bold",
            color=COLORS["ink"], zorder=3,
        )


def arrow(x1, y1, x2, y2, label=None, label_xy=None):
    a = FancyArrowPatch(
        (x1, y1), (x2, y2),
        arrowstyle="-|>",
        mutation_scale=13,
        linewidth=1.35,
        color=COLORS["line"],
        connectionstyle="arc3",
        zorder=1,
    )
    ax.add_patch(a)

    if label:
        lx, ly = label_xy or ((x1+x2)/2, (y1+y2)/2)
        ax.text(
            lx, ly, label,
            ha="center", va="center",
            fontsize=8.3, color=COLORS["ink"],
            bbox=dict(facecolor="white", edgecolor="none", pad=2),
            zorder=4,
        )


# ------------------------------------------------------------
# Header
# ------------------------------------------------------------

ax.text(
    7, 9.72,
    "ESDSA v2: Evidence-Constrained Assessment and Stability Gating",
    ha="center", va="center",
    fontsize=14, fontweight="bold", color=COLORS["ink"]
)

# ------------------------------------------------------------
# Main evidence-assessment pipeline
# ------------------------------------------------------------

box(
    4.6, 8.45, 4.8, 0.82,
    "Synthetic interview response",
    "Competency-specific rubric: three criteria",
    COLORS["input"]
)

box(
    4.6, 7.20, 4.8, 0.90,
    "Criterion-level evidence assessment",
    "POSITIVE / NEGATIVE / INSUFFICIENT",
    COLORS["assessment"]
)

box(
    4.6, 5.95, 4.8, 0.90,
    "Deterministic quotation traceability",
    "VERIFIED / CONTEXT_ONLY / UNVERIFIABLE / NOT_APPLICABLE",
    COLORS["trace"],
    subtitle_size=7.7,
)

box(
    4.6, 4.48, 4.8, 1.12,
    "Frozen evidence decision policy",
    "Any verified negative: DO_NOT_ADVANCE\n"
    "All three verified positive: ADVANCE\n"
    "Otherwise: DEFER",
    COLORS["policy"],
    title_size=9.5,
    subtitle_size=7.8,
)

arrow(7, 8.45, 7, 8.10)
arrow(7, 7.20, 7, 6.85)
arrow(7, 5.95, 7, 5.60)

# ------------------------------------------------------------
# Semantic-equivalence annotation
# ------------------------------------------------------------

box(
    0.35, 4.55, 3.55, 1.12,
    "Semantic-equivalence annotation",
    "Three variants per evidence condition\n"
    "YES / NO / UNCERTAIN",
    COLORS["equivalence"],
    title_size=8.8,
    subtitle_size=7.5,
)

# ------------------------------------------------------------
# Gate / routing
# ------------------------------------------------------------

box(
    4.6, 3.35, 4.8, 0.88,
    "Apply frozen semantic stability policy",
    "Based on equivalence annotation and pre-stability decisions",
    COLORS["equivalence"],
    subtitle_size=8,
)

arrow(3.90, 5.12, 4.60, 3.79)


arrow(3.80, 5.12, 4.60, 3.79)

# ------------------------------------------------------------
# Branches
# ------------------------------------------------------------

box(
    0.45, 1.85, 5.2, 0.95,
    "Equivalence = YES",
    "Unanimous identical actionable decision required",
    COLORS["assessment"],
)

box(
    8.35, 1.85, 5.2, 0.95,
    "Equivalence = NO or UNCERTAIN",
    "Retain individual pre-stability decisions",
    COLORS["assessment"],
)

arrow(6.2, 3.35, 3.05, 2.80, "YES", (4.72, 3.10))
arrow(7.8, 3.35, 10.95, 2.80, "NO / UNCERTAIN", (9.45, 3.10))

# ------------------------------------------------------------
# Outputs
# ------------------------------------------------------------

box(
    0.45, 0.42, 5.2, 0.95,
    "Stable actionable recommendation",
    "Retain ADVANCE or DO_NOT_ADVANCE;\notherwise DEFER all three variants",
    COLORS["decision"],
)

box(
    8.35, 0.42, 5.2, 0.95,
    "Individual recommendations retained",
    "ADVANCE / DO_NOT_ADVANCE / DEFER",
    COLORS["decision"],
)

arrow(3.05, 1.85, 3.05, 1.37)
arrow(10.95, 1.85, 10.95, 1.37)


ax.text(
    7, 0.10,
    "Textual verification confirms excerpt occurrence, not semantic correctness. "
    "DEFER is an experimental assessment outcome.",
    ha="center", va="center",
    fontsize=8.4, color=COLORS["muted"],
)

# ------------------------------------------------------------
# Export
# ------------------------------------------------------------

fig.savefig(
    OUT_DIR / "figure_1_esdsa_architecture.pdf",
    bbox_inches="tight",
    pad_inches=0.15,
)

fig.savefig(
    OUT_DIR / "figure_1_esdsa_architecture.svg",
    bbox_inches="tight",
    pad_inches=0.15,
)

fig.savefig(
    OUT_DIR / "figure_1_esdsa_architecture.png",
    dpi=350,
    bbox_inches="tight",
    pad_inches=0.15,
)

plt.close(fig)

print("Figure 1 generated successfully:")
for ext in ["pdf", "svg", "png"]:
    print(f"  {OUT_DIR / ('figure_1_esdsa_architecture.' + ext)}")
