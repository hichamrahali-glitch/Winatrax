"""Reusable animated Plotly chart builders for rankings and time series."""
import plotly.graph_objects as go


def play_controls(labels, duration, start_index):
    """Plotly play/pause buttons and a period slider for animated figures."""
    return dict(
        updatemenus=[dict(type="buttons", direction="left", x=0, y=1.13, xanchor="left", yanchor="top",
                          pad=dict(r=8, t=0), showactive=False, buttons=[
                              dict(label="▶ Play", method="animate",
                                   args=[None, dict(frame=dict(duration=duration, redraw=True),
                                                    transition=dict(duration=int(duration * 0.8), easing="linear"),
                                                    fromcurrent=False, mode="immediate")]),
                              dict(label="❚❚ Pause", method="animate",
                                   args=[[None], dict(frame=dict(duration=0, redraw=False),
                                                      transition=dict(duration=0), mode="immediate")])])],
        sliders=[dict(active=start_index, x=0.12, len=0.88, y=1.13, yanchor="top", pad=dict(t=0, b=10),
                      currentvalue=dict(visible=False), steps=[
                          dict(label=label, method="animate",
                               args=[[label], dict(frame=dict(duration=0, redraw=True), mode="immediate",
                                                   transition=dict(duration=200))]) for label in labels])])


def big_period_label(text):
    return [dict(text=text, xref="paper", yref="paper", x=0.99, y=0.04, xanchor="right", yanchor="bottom",
                 showarrow=False, font=dict(size=46, color="rgba(120,120,120,0.25)"))]


def bar_race(items_at, indices, colour, n, value_title, *, frame_labels, period_label, controls, big_label):
    """items_at(i) -> list of dicts {id, value, text, hover}, sorted descending."""
    frames, labels = [], []
    for i in indices:
        # n visible bars + up to 5 below the chart, so countries leaving the top n slide out
        # downwards instead of jumping (their labels are blank and clipped by the axis range)
        items = items_at(i)[:n + 5]
        for k, d in enumerate(items):
            if k >= n:
                d["text"] = ""
        lab = frame_labels[i]
        labels.append(lab)
        # Each frame is scaled so the leader fills the width (Plotly does not animate axis
        # ranges reliably); the real values are in the labels and the hover text.
        vmax = max([d["value"] for d in items[:n]] + [1e-9])
        frames.append(go.Frame(name=lab, data=[go.Bar(
            x=[d["value"] / vmax for d in items], y=list(range(1, len(items) + 1)), ids=[d["id"] for d in items],
            orientation="h", marker_color=colour, text=[d["text"] for d in items], textposition="outside",
            cliponaxis=True, hovertext=[d["hover"] for d in items], hoverinfo="text")],
            layout=go.Layout(annotations=big_label(period_label(i)))))
    last = frames[-1]
    fig = go.Figure(data=last.data, frames=frames)
    fig.update_layout(height=max(420, 30 * n + 140), margin=dict(l=10, r=10, t=90, b=30),
                      xaxis=dict(range=[0, 1.75], showticklabels=False, showgrid=False, title=None),
                      yaxis=dict(range=[n + 0.5, 0.5], tickvals=list(range(1, n + 1)), title=None),
                      annotations=last.layout.annotations, showlegend=False,
                      **controls(labels, 140, len(labels) - 1))
    return fig


def line_race(codes, series, indices, label, colour_of, highlight, value_title, measure, *, frame_labels, dates, formatter, controls, big_label, grey):
    """Lines grow over time; top 5 (+ highlighted) in colour with a label at the line tip."""
    labels, frames = [], []
    top = set(codes[:5]) | set(highlight)
    order = [c for c in codes if c not in top] + [c for c in codes if c in top]
    for i in indices:
        data = []
        for c in order:
            col = colour_of(c) if c in codes[:5] else ("#0b0b0b" if c in highlight else grey)
            data.append(go.Scatter(x=dates[:i + 1], y=series[c][:i + 1], mode="lines", name=label(c),
                                   line=dict(color=col, width=2.4 if c in top else 1),
                                   hovertemplate=f"{label(c)}<br>%{{x|%b %Y}}: %{{y:,.2f}}<extra></extra>"))
        tips = [c for c in codes if c in top]
        data.append(go.Scatter(x=[dates[i]] * len(tips), y=[series[c][i] for c in tips], mode="markers+text",
                               text=[f"{label(c)}  {formatter(series[c][i], measure)}" for c in tips],
                               textposition="middle right", cliponaxis=False, hoverinfo="skip",
                               marker=dict(size=7, color=[colour_of(c) if c in codes[:5] else "#0b0b0b" for c in tips])))
        lab = frame_labels[i]
        labels.append(lab)
        frames.append(go.Frame(name=lab, data=data, layout=go.Layout(annotations=big_label(lab[:4]))))
    last = frames[-1]
    fig = go.Figure(data=last.data, frames=frames)
    fig.update_layout(height=560, margin=dict(l=10, r=230, t=90, b=30), showlegend=False,
                      xaxis=dict(range=[dates[0], dates[-1]]),
                      yaxis=dict(range=[0, max([max(series[c]) for c in codes] + [1e-9]) * 1.08], title=value_title),
                      annotations=last.layout.annotations, **controls(labels, 90, len(labels) - 1))
    return fig


