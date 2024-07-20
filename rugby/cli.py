import click
import rugby

import rugby.scrape

@click.version_option(rugby.__version__)
@click.group()
@click.pass_context
def app(ctx):
    """
    The rugby data CLI app.
    """
    click.echo("Rugby Data")

app.add_command(rugby.scrape.scrape)
app()
