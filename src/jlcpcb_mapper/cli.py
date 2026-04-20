import click


@click.group()
def main():
    """LLM-assisted JLCPCB part mapping for KiCad schematics."""


@main.command()
@click.argument("project", type=click.Path(exists=True, dir_okay=False))
@click.option("--config", "config_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--non-interactive", is_flag=True)
@click.option("--force", is_flag=True)
@click.option("--allow-stale-db", is_flag=True)
@click.option("--fill-lcsc-only", is_flag=True)
@click.option("--include-dnp", is_flag=True)
@click.option("--apply-2nd-pass-suggestions", "apply_suggestions", is_flag=True)
def map(project, config_path, non_interactive, force, allow_stale_db,
        fill_lcsc_only, include_dnp, apply_suggestions):
    """Map empty-footprint components to JLCPCB parts."""
    from pathlib import Path
    from .commands.map_cmd import run_map
    from .config import load_config
    cfg_path = Path(config_path) if config_path else Path(project).parent / "jlcpcb-mapper.yaml"
    cfg = load_config(cfg_path)
    report = run_map(
        project_pro=Path(project),
        config=cfg,
        non_interactive=non_interactive,
        force=force,
        allow_stale_db=allow_stale_db,
        fill_lcsc_only=fill_lcsc_only,
        include_dnp=include_dnp,
        apply_suggestions=apply_suggestions,
    )
    click.echo(report.to_text())


@main.command()
@click.argument("project", type=click.Path(exists=True, dir_okay=False))
@click.option("--config", "config_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--non-interactive", is_flag=True)
@click.option("--force", is_flag=True)
@click.option("--allow-stale-db", is_flag=True)
def verify(project, config_path, non_interactive, force, allow_stale_db):
    """Re-check existing mappings against current DB."""
    from pathlib import Path
    from .commands.verify_cmd import run_verify
    from .config import load_config
    cfg_path = Path(config_path) if config_path else Path(project).parent / "jlcpcb-mapper.yaml"
    cfg = load_config(cfg_path)
    report = run_verify(
        project_pro=Path(project),
        config=cfg,
        non_interactive=non_interactive,
        force=force,
        allow_stale_db=allow_stale_db,
    )
    click.echo(report.to_text())


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
