"""Shared look for the static matplotlib charts."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#8a8984"
GRID = "#ebeae6"
GREY = "#b4b2a9"
# Fixed categorical order: colour follows the country, never its rank.
PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]


def setup():
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "font.size": 11, "axes.edgecolor": SURFACE, "axes.labelcolor": INK_2,
        "xtick.color": INK_2, "ytick.color": INK_2, "xtick.major.size": 0, "ytick.major.size": 0,
        "axes.grid": True, "axes.grid.axis": "y", "grid.color": GRID, "grid.linewidth": 0.8,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.spines.left": False, "axes.spines.bottom": False,
    })


def titles(fig, title, subtitle, caption, top=0.97):
    fig.text(0.012, top, title, fontsize=16, fontweight="bold", color=INK, va="top")
    fig.text(0.012, top - 0.045, subtitle, fontsize=11, color=INK_2, va="top", linespacing=1.4)
    fig.text(0.012, 0.012, caption, fontsize=8, color=MUTED, va="bottom", linespacing=1.4)


def dodge(values, gap):
    """Push label positions apart (ascending) so they never overlap."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = list(values)
    for a, b in zip(order, order[1:]):
        out[b] = max(out[b], out[a] + gap)
    return out
