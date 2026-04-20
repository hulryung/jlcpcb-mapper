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
@click.option("--output", type=click.Path(dir_okay=False), default="jlcpcb-mapper.yaml")
@click.option("--force", is_flag=True)
def init(output, force):
    """Scaffold a default jlcpcb-mapper.yaml in the current directory."""
    import importlib.resources as resources
    from pathlib import Path
    out = Path(output)
    if out.exists() and not force:
        raise click.ClickException(f"{out} exists; use --force to overwrite")
    text = resources.files("jlcpcb_mapper").joinpath("default_config.yaml").read_text()
    out.write_text(text)
    click.echo(f"wrote {out}")
