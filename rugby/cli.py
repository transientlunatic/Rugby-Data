import click
import rugby

from rugby.commands.data import data
from rugby.commands.analysis import analysis
from rugby.commands.plot import plot
from rugby.commands.config import config


@click.version_option(rugby.__version__)
@click.group()
def app():
    """Rugby Data - data acquisition, storage, and analysis tools."""
    pass


app.add_command(data)
app.add_command(analysis)
app.add_command(plot)
app.add_command(config)
