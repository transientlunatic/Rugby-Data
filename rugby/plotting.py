import matplotlib.pyplot as plt
import numpy as np
import matplotlib
import pandas as pd
import datetime

from cycler import cycler

style = {
    "xtick.labelsize":10,
    "xtick.major.size": 5,
    "xtick.minor.visible": True,
    "xtick.color": "k",
    "ytick.labelsize":10,
    "ytick.major.size": 5,
    "ytick.minor.visible": True,
    # Lines
    "lines.linewidth": 2,
    "axes.prop_cycle": cycler("color", ['#8dd3c7', '#ffffb3', '#bebada',
                                        '#fb8072', '#80b1d3', '#fdb462',
                                        '#b3de69', '#fccde5', '#d9d9d9',
                                        '#bc80bd', '#ccebc5', '#ffed6f']),
    # Fonts
    "font.monospace": ["Source code pro"],
    "font.sans-serif": ["Source sans pro"],
    "font.family": "monospace",
    # Grid
    "grid.color": "#4298bd",
    "grid.alpha": 0.5,
    # Display
    "figure.dpi": 300,
    # Face colors
    "axes.facecolor": "#ecf5f8",
    "figure.facecolor": "#FFFFFFFF"
}

def heatmap(data, row_labels, col_labels, ax=None, diagonal=False,
            cbar_kw={}, cbarlabel="", **kwargs):
    """
    Create a heatmap from a numpy array and two lists of labels.

    Parameters
    ----------
    data
        A 2D numpy array of shape (N, M).
    row_labels
        A list or array of length N with the labels for the rows.
    col_labels
        A list or array of length M with the labels for the columns.
    ax
        A `matplotlib.axes.Axes` instance to which the heatmap is plotted.  If
        not provided, use current axes or create a new one.  Optional.
    cbar_kw
        A dictionary with arguments to `matplotlib.Figure.colorbar`.  Optional.
    cbarlabel
        The label for the colorbar.  Optional.
    **kwargs
        All other arguments are forwarded to `imshow`.
    """

    
    norm = matplotlib.colors.TwoSlopeNorm(vmin=np.nanmin(data) if np.nanmin(data)!=0 else -1, vcenter=0, vmax=np.nanmax(data))
    
    if not ax:
        ax = plt.gca()

    # Plot the heatmap
    im = ax.imshow(data, norm=norm, **kwargs)

    # Create colorbar
    #cbar = ax.figure.colorbar(im, ax=ax, **cbar_kw)
    #cbar.ax.set_ylabel(cbarlabel, rotation=-90, va="bottom")

    # We want to show all ticks...
    ax.set_xticks(np.arange(data.shape[1]))
    ax.set_yticks(np.arange(data.shape[0]))
    # ... and label them with the respective list entries.
    ax.set_xticklabels(col_labels, fontdict={"fontsize":8})
    ax.set_yticklabels(row_labels, fontdict={"fontsize":8})

    # Let the horizontal axes labeling appear on top.
    ax.tick_params(top=True, bottom=False,
                   labeltop=True, labelbottom=False)

    # Rotate the tick labels and set their alignment.
    plt.setp(ax.get_xticklabels(), rotation=-30, ha="right",
             rotation_mode="anchor")

    # Turn spines off and create white grid.
    for edge, spine in ax.spines.items():
        spine.set_visible(False)

    ax.set_xticks(np.arange(data.shape[1]+1)-.5, minor=True)
    ax.set_yticks(np.arange(data.shape[0]+1)-.5, minor=True)
    ax.grid(which="minor", color="w", linestyle='-', linewidth=3.5, alpha=1)
    ax.tick_params(which="minor", bottom=False, left=False)
    if not diagonal:
        for i, label in enumerate(row_labels):
            rect = matplotlib.patches.Rectangle((i-0.5,i-0.5),1,1,linewidth=1,edgecolor=None,facecolor='white')
            ax.add_patch(rect)

    
    return im


def annotate_heatmap(im, data=None, valfmt="{x:.2f}",
                     textcolors=("black", "white"),
                     threshold=None, diagonal=False, **textkw):
    """
    A function to annotate a heatmap.

    Parameters
    ----------
    im
        The AxesImage to be labeled.
    data
        Data used to annotate.  If None, the image's data is used.  Optional.
    valfmt
        The format of the annotations inside the heatmap.  This should either
        use the string format method, e.g. "$ {x:.2f}", or be a
        `matplotlib.ticker.Formatter`.  Optional.
    textcolors
        A pair of colors.  The first is used for values below a threshold,
        the second for those above.  Optional.
    threshold
        Value in data units according to which the colors from textcolors are
        applied.  If None (the default) uses the middle of the colormap as
        separation.  Optional.
    **kwargs
        All other arguments are forwarded to each call to `text` used to create
        the text labels.
    """

    if not isinstance(data, (list, np.ndarray)):
        data = im.get_array()

    cell_data = im.get_array()
    def text_color(datum):
        if datum  < 0.75 * cell_data.min(): return "white"
        elif datum  > 0.75 * cell_data.max(): return "white"
        else: return "black"
    # Normalize the threshold to the images color range.
    #if threshold is not None:
    #    threshold = im.norm(threshold)
    #else:
    #    threshold = im.norm(data.max())/2.

    # Set default alignment to center, but allow it to be
    # overwritten by textkw.
    kw = dict(horizontalalignment="center",
              verticalalignment="center")
    kw.update(textkw)

    # Get the formatter in case a string is supplied
    if isinstance(valfmt, str):
        valfmt = matplotlib.ticker.StrMethodFormatter(valfmt)

    # Loop over the data and create a `Text` for each "pixel".
    # Change the text's color depending on the data.
    texts = []
    
    
    
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            if (i == j) and not diagonal: continue
            
            if "fontdict" in kw:
                kw['fontdict']["color"] = text_color(cell_data[i,j])
            else:
                kw['fontdict'] = {"color":text_color(cell_data[i,j])}
                
            text = im.axes.text(j, i, data[i, j], **kw)
            texts.append(text)

    return texts



def league_heatmap(results, league, season):


    pivot = results.pivot_table(index="home", columns="away", values="difference", aggfunc="first")#.fillna(0)
    home = results.pivot_table(index="home", columns="away", values="home_score", aggfunc="first").values
    dates = results.pivot_table(index="home", columns="away", values="date", aggfunc="first").values
    away = results.pivot_table(index="home", columns="away", values="away_score", aggfunc="first").values
    multiples_home = results.pivot_table(index="home", columns="away", values="home_score", aggfunc="count") >1
    multiples_away = results.pivot_table(index="home", columns="away", values="away_score", aggfunc="count") >1
    second_home = results.pivot_table(index="home", columns="away", values="home_score", aggfunc="last")[multiples_home].values
    second_away = results.pivot_table(index="home", columns="away", values="away_score", aggfunc="last")[multiples_away].values
    scorelines = []

    for h, a, hh, aa, f in zip(home.flatten(), away.flatten(),
                                second_home.flatten(), second_away.flatten(), dates.flatten()):
        if np.isnan(h) or (h==-200):
            if not pd.isna(f):
                scorelines.append(f"{pd.to_datetime(f):%d\n%b}")
            else:
                scorelines.append("-")
        elif np.isinf(h):
            scorelines.append("C")
        elif not np.isnan(hh):
            scorelines.append(f"{h:.0f}·{a:.0f}\n{hh:.0f}·{aa:.0f}")
        else:
            scorelines.append(f"{h:.0f}·{a:.0f}")

    
    fig, ax = plt.subplots()

    im = heatmap(pivot.values, 
                       pivot.index, [f"{name[:5].strip()}." for name in pivot.index], ax=ax,
                       cmap="RdBu", cbarlabel="Points Difference", alpha=0.7)

    texts = annotate_heatmap(im, data = np.array(scorelines).reshape(home.shape), fontdict={"fontsize":5})

    ax.grid(False)

    ax.tick_params(top=False, bottom=False, left=False,
                   labeltop=True, labelbottom=False)

    #ax.set_ylabel("Home")
    #ax.set_xlabel("Away")

    ax.set_xlim(-0.5,ax.get_xlim()[1]+0.01)

    ax.text(-2,0.6, s="← Home", rotation=90)
    ax.text(-2,-0.7, s="Away →", rotation=0)

    ax.text(-2.5, ax.get_ylim()[0]+0.5, s="Blue indicates a home win, red an away win.\nRead across rows for a team's home games, and down columns for their away games.", fontdict={"fontsize":5})


    ax.set_title(f"{league}\n{season}", fontdict={"fontsize":10})
    fig.tight_layout()
    return fig

def tournament_heatmap(tournament, ax=None, **kwargs):
    results = tournament.results_table()
    pivot = results.pivot_table(index="home", columns="away", values="difference", aggfunc="sum")#.fillna(0)
    home = results.pivot_table(index="home", columns="away", values="home_score", aggfunc="first").values
    away = results.pivot_table(index="home", columns="away", values="away_score", aggfunc="first").values

    multiples_home = results.pivot_table(index="home", columns="away", values="home_score", aggfunc="count") >1
    multiples_away = results.pivot_table(index="home", columns="away", values="away_score", aggfunc="count") >1
    second_home = results.pivot_table(index="home", columns="away", values="home_score", aggfunc="last")[multiples_home].values
    second_away = results.pivot_table(index="home", columns="away", values="away_score", aggfunc="last")[multiples_away].values
    scorelines = []

    if not isinstance(tournament.future, type(None)):
        fixtures_pivot = tournament.fixtures_table(future=True).pivot(index="home",
                                                         columns="away", values="date").values
    else:
        fixtures_pivot = np.ones(len(home.flatten()))*np.nan

    for h, a, hh, aa, f in zip(home.flatten(), away.flatten(),
                            second_home.flatten(), second_away.flatten(), fixtures_pivot.flatten()):
        if (np.isnan(h)) or (h==-200):
            if not pd.isna(f):
                scorelines.append(f"{pd.to_datetime(f):%d\n%b}")
            else:
                scorelines.append("-")
        elif np.isinf(h):
            scorelines.append("C")
        elif not np.isnan(hh):
            scorelines.append(f"{h:.0f}·{a:.0f}\n{hh:.0f}·{aa:.0f}")
        else:
            scorelines.append(f"{h:.0f}·{a:.0f}")


    if not ax:
        fig, ax = plt.subplots()

    kw = {"fontdict": {"fontsize":4}}
    kw.update(kwargs)
        
    im = heatmap(pivot.values, 
                       pivot.index, [f"{name[:5].strip()}." for name in pivot.index], ax=ax,
                       cmap="RdBu", cbarlabel="Points Difference", alpha=0.7)

    texts = annotate_heatmap(im, data = np.array(scorelines).reshape(home.shape), fontdict=kw['fontdict'])

    ax.grid(False)

    ax.tick_params(top=False, bottom=False, left=False,
                   labeltop=True, labelbottom=False)

    #ax.set_ylabel("Home")
    #ax.set_xlabel("Away")

    ax.set_xlim(-0.5,ax.get_xlim()[1]+0.05)

    ax.text(-6.15,0.6, s="← Home", rotation=90)
    ax.text(-5.7,-1.1, s="Away →", rotation=0)

    ax.text(-2.5, ax.get_ylim()[0]+0.5, s="Blue indicates a home win, red an away win.\nRead across rows for a team's home games, and down columns for their away games.", fontdict={"fontsize":5})


    ax.set_title(f"{tournament.name}\n{tournament.season}", fontdict={"fontsize":10})
    #fig.tight_layout()
    #fig.savefig("west3-2019.png")
    return ax


def player_score_matrix_plot(tournament, team, ax=None, squad=False, **kw):
    player_times = tournament.player_score_table(team)
    if squad:
        data = tournament.player_time_table(team).join(player_times, lsuffix="t", how='outer')
        data = data[data.columns[-int(len(data.columns)/2):]]
        player_times = data
    labelfont = kw['labelfont']
    del(kw['labelfont'])
    if not ax:
        f, ax = plt.subplots(1,1, dpi=300)
    norm = matplotlib.colors.TwoSlopeNorm(vmin=0, vcenter=40, vmax=80)
    im = ax.imshow(player_times.values, norm=norm, cmap="magma_r", alpha=0.7,)
    ax.grid(False)
    ax.tick_params(top=True, bottom=False,
                   labeltop=True, labelbottom=False)

    for edge, spine in ax.spines.items():
            spine.set_visible(False)

    ax.set_xticks(np.arange(player_times.shape[1]))
    ax.set_yticks(np.arange(player_times.shape[0]))
    ax.tick_params(which="minor", bottom=False, left=False)
    ax.set_xticklabels(player_times.columns, fontdict=labelfont)
    ax.set_yticklabels(player_times.index, fontdict=labelfont)

    for edge, spine in ax.spines.items():
            spine.set_visible(False)

    ax.set_xticks(np.arange(player_times.shape[1]+1)-.5, minor=True)
    ax.set_yticks(np.arange(player_times.shape[0]+1)-.5, minor=True)
    ax.grid(which="minor", color="w", linestyle='-', linewidth=.5, alpha=1)
    ax.tick_params(which="major", bottom=False, left=False, top=False)
    ax.tick_params(which="minor", bottom=False, left=False, top=False)

    plt.setp(ax.get_xticklabels(), rotation=-90, ha="right", va="center",
                 rotation_mode="anchor");

    def text_color(datum):
        if datum  > 40: return "white"
        else: return "black"

    texts = []
    times = player_times.values
    for i in range(player_times.shape[0]):
        for j in range(player_times.shape[1]):
            if not np.isnan(times[i,j]): s=f"{times[i,j]:.0f}"
            else: s="-"
                
            kw = dict(horizontalalignment="center",
                  verticalalignment="center")
            kw['fontdict'] = labelfont
            kw['fontdict']["color"] = text_color(times[i,j])
            text = im.axes.text(j, i, s, **kw)
            texts.append(text)

    ax.set_xlim(-0.5,ax.get_xlim()[1]+0.01);
    
    return ax


def player_time_matrix_plot(tournament, team, ax=None, **kw):
    """
    Produce a time matrix plot for a given tournament.
    
    Parameters
    ----------
    tournament : `rugby.Tournament`
       The tournament to draw matches from.
    team : `str`
       The name of the team.
    ax : matplotlib axis, optional
       The axis to draw the plot on.

    Examples
    --------

    ::

       from rugby.data import Tournament
       import rugby.plotting
       import pandas as pd

       import matplotlib
       import matplotlib.pyplot as plt
       plt.style.use(rugby.plotting.style)

       tournament = Tournament("Super Rugby Aotearoa", "2020", pd.read_json("/home/daniel/repositories/snippets/superrugby/superrugby_nz.json"))

   
       team = "Highlanders"
       f, ax = plt.subplots(1,1, sharey=True, figsize=(1.5,6), dpi=300)
       rugby.plotting.player_time_matrix_plot(tournament, team, ax, labelfont={"fontsize":5})
       f.text(0.08, 0.99, "Minutes played", fontdict={"fontsize":5}, ha="left")
       f.tight_layout()
    """
    
    player_times = tournament.player_time_table(team)
    labelfont = kw['labelfont']
    del(kw['labelfont'])
    if not(ax):
        f, ax = plt.subplots(1,1, dpi=300)
    norm = matplotlib.colors.TwoSlopeNorm(vmin=0, vcenter=40, vmax=80)
    im = ax.imshow(player_times.values, norm=norm, cmap="magma_r", alpha=0.7,)
    ax.grid(False)
    ax.tick_params(top=True, bottom=False,
                   labeltop=True, labelbottom=False)

    for edge, spine in ax.spines.items():
            spine.set_visible(False)

    ax.set_xticks(np.arange(player_times.shape[1]))
    ax.set_yticks(np.arange(player_times.shape[0]))
    ax.tick_params(which="minor", bottom=False, left=False)
    ax.set_xticklabels(player_times.columns, labelfont)
    ax.set_yticklabels(player_times.index, labelfont)

    for edge, spine in ax.spines.items():
            spine.set_visible(False)

    ax.set_xticks(np.arange(player_times.shape[1]+1)-.5, minor=True)
    ax.set_yticks(np.arange(player_times.shape[0]+1)-.5, minor=True)
    ax.grid(which="minor", color="w", linestyle='-', linewidth=.5, alpha=1)
    ax.tick_params(which="major", bottom=False, left=False, top=False)
    ax.tick_params(which="minor", bottom=False, left=False, top=False)

    plt.setp(ax.get_xticklabels(), rotation=-90, ha="right", va="center",
                 rotation_mode="anchor");

    def text_color(datum):
        if datum  > 40: return "white"
        else: return "black"

    texts = []
    times = player_times.values
    for i in range(player_times.shape[0]):
        for j in range(player_times.shape[1]):
            if not np.isnan(times[i,j]): s=f"{times[i,j]:.0f}"
            else: s="-"
            kw = dict(horizontalalignment="center",
                  verticalalignment="center")
            kw['fontdict'] = labelfont

            kw['fontdict']["color"] = text_color(times[i,j])
            text = im.axes.text(j, i, s, **kw)
            texts.append(text)

    ax.set_xlim(-0.5,ax.get_xlim()[1]+0.01);
    
    return ax
