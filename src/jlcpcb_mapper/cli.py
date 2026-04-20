import click


@click.group()
def main():
    """LLM-assisted JLCPCB part mapping for KiCad schematics."""


@main.command()
@click.argument("project", type=click.Path(exists=True, dir_okay=False))
@click.option("--config", type=click.Path(exists=True, dir_okay=False))
@click.option("--non-interactive", is_flag=True)
@click.option("--force", is_flag=True)
@click.option("--allow-stale-db", is_flag=True)
@click.option("--fill-lcsc-only", is_flag=True)
@click.option("--include-dnp", is_flag=True)
@click.option("--apply-2nd-pass-suggestions", "apply_suggestions", is_flag=True)
def map(project, **kwargs):
    """Map empty-footprint components to JLCPCB parts."""
    click.echo(f"map: {project}")


@main.command()
@click.argument("project", type=click.Path(exists=True, dir_okay=False))
@click.option("--config", type=click.Path(exists=True, dir_okay=False))
@click.option("--non-interactive", is_flag=True)
@click.option("--force", is_flag=True)
@click.option("--allow-stale-db", is_flag=True)
def verify(project, **kwargs):
    """Re-check existing mappings against current DB."""
    click.echo(f"verify: {project}")


@main.command()
def init():
    """Scaffold a default jlcpcb-mapper.yaml in the current directory."""
    click.echo("init")
