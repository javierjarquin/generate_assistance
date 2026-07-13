import sys

import typer

from illustrated_narrator.domain.entities.project import NarrationProject
from illustrated_narrator.infrastructure.config import load_settings
from illustrated_narrator.infrastructure.container import Container
from illustrated_narrator.infrastructure.logging_config import setup_logging

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

app = typer.Typer(
    help="Genera un video narrado con ilustraciones dinámicas a partir de un guion por planos.",
    no_args_is_help=True,
)


def _container() -> Container:
    settings = load_settings()
    setup_logging(settings.log_level)
    return Container(settings)


def _project(slug: str) -> NarrationProject:
    settings = load_settings()
    project = NarrationProject(slug=slug, root_dir=settings.projects_dir / slug)
    project.ensure_dirs()
    return project


@app.command()
def generate(
    slug: str = typer.Argument(help="Nombre de la carpeta en projects/<slug>/"),
    vertical: bool = typer.Option(
        False, "--vertical", help="Lienzo 9:16 (Shorts/Reels) en lugar de 16:9"
    ),
) -> None:
    """Corre el pipeline completo: transcribe, alinea, genera imágenes, ensambla."""
    import os

    if vertical:
        os.environ["NARR_VERTICAL"] = "1"
    container = _container()
    project = _project(slug)
    if not project.script_path.exists():
        typer.echo(f"Falta {project.script_path} — coloca ahí el guion.json.")
        raise typer.Exit(code=1)

    try:
        report = container.generate_narration_video.execute(project)
    except FileNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc

    if report.alignment:
        typer.echo(
            f"Alineación: {report.alignment.aligned_count}/{report.alignment.total_planos} planos"
        )
        if report.alignment.unaligned_planos:
            typer.echo(f"  Sin alinear: {', '.join(report.alignment.unaligned_planos)}")
    typer.echo(f"Imágenes generadas: {report.images_generated}")
    for plano, error in report.images_failed:
        typer.echo(f"  FALLÓ imagen {plano.id}: {error}")
    typer.echo(f"Clips renderizados: {report.clips_rendered}")
    typer.echo(f"Video final: {report.final_video_path}")


@app.command()
def status(slug: str = typer.Argument(help="Nombre de la carpeta en projects/<slug>/")) -> None:
    """Muestra cuántos planos hay, cuántos están alineados/con imagen/con clip."""
    from illustrated_narrator.domain.services.plano_state import load_planos_state
    from illustrated_narrator.domain.services.script_loader import load_guion

    project = _project(slug)
    if not project.script_path.exists():
        typer.echo(f"Falta {project.script_path}")
        raise typer.Exit(code=1)

    guion = load_guion(project.script_path)
    load_planos_state(guion.planos, project.planos_alineados_path)

    total = len(guion.planos)
    aligned = sum(1 for p in guion.planos if p.inicio_real_seg is not None)
    with_image = sum(1 for p in guion.planos if p.imagen_path)
    with_clip = sum(1 for p in guion.planos if p.clip_path)
    typer.echo(f"{guion.meta.titulo} — {total} planos")
    typer.echo(f"  Alineados: {aligned}/{total}")
    typer.echo(f"  Con imagen: {with_image}/{total}")
    typer.echo(f"  Con clip: {with_clip}/{total}")
    typer.echo(f"  Audio: {'OK' if project.audio_path.exists() else 'falta ' + str(project.audio_path)}")
    typer.echo(f"  Video final: {'OK' if project.final_video_path.exists() else 'no generado aún'}")


if __name__ == "__main__":
    app()
