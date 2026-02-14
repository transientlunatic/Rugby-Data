"""
Configuration CLI commands: show, set, init.
"""

from pathlib import Path

import click

from ..config import (
    get_config_path, load_config, save_config,
    get_data_dir, get_squads_dir
)


@click.group()
def config():
    """Manage rugby configuration."""
    pass


@config.command()
def show():
    """Display current configuration."""
    config_path = get_config_path()
    cfg = load_config()

    if not cfg:
        click.echo(f"No config file found at {config_path}")
        click.echo("Run 'rugby config init' to create one.")
        return

    click.echo(f"Config file: {config_path}")
    click.echo()

    for section, values in cfg.items():
        click.echo(f"[{section}]")
        if isinstance(values, dict):
            for key, val in values.items():
                click.echo(f"  {key} = {val}")
        click.echo()

    # Show resolved paths
    click.echo("Resolved paths:")
    data_dir = get_data_dir()
    squads_dir = get_squads_dir()
    click.echo(f"  data_dir: {data_dir or '(not set)'}")
    click.echo(f"  squads_dir: {squads_dir or '(not set)'}")


@config.command(name='set')
@click.argument('key')
@click.argument('value')
def set_value(key, value):
    """Set a config value (e.g., 'rugby config set paths.data_dir /path/to/data')."""
    parts = key.split('.', 1)
    if len(parts) != 2:
        click.echo("Key must be in format 'section.key' (e.g., 'paths.data_dir')", err=True)
        return

    section, setting = parts
    cfg = load_config()

    if section not in cfg:
        cfg[section] = {}
    cfg[section][setting] = value

    save_config(cfg)
    click.echo(f"Set {key} = {value}")


@config.command()
def init():
    """Interactive configuration setup."""
    config_path = get_config_path()
    cfg = load_config()

    click.echo("Rugby Configuration Setup")
    click.echo("=" * 40)
    click.echo()

    # Data directory
    current_data_dir = cfg.get("paths", {}).get("data_dir", "")
    default_data_dir = current_data_dir or str(Path.cwd())

    data_dir = click.prompt(
        "Rugby-Data directory (contains json/ folder)",
        default=default_data_dir
    )

    data_path = Path(data_dir).expanduser().resolve()
    if not (data_path / "json").exists():
        click.echo(f"Warning: {data_path}/json/ does not exist.")
        if not click.confirm("Continue anyway?"):
            return

    # Squads directory
    default_squads = str(data_path / "squads")
    squads_dir = click.prompt("Squads directory", default=default_squads)

    cfg["paths"] = {
        "data_dir": str(data_path),
        "squads_dir": str(Path(squads_dir).expanduser().resolve()),
    }

    save_config(cfg)
    click.echo()
    click.echo(f"Config saved to {config_path}")
    click.echo()
    click.echo("You can now use rugby-ranking commands without --data-dir:")
    click.echo("  rugby-ranking update")
    click.echo("  rugby-ranking rankings")
