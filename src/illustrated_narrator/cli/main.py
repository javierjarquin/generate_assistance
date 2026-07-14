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
    if report.media_shots_resolved:
        typer.echo(f"Shots con medios reales: {report.media_shots_resolved}")
    typer.echo(f"Imágenes generadas: {report.images_generated}")
    for plano, error in report.images_failed:
        typer.echo(f"  FALLÓ imagen {plano.id}: {error}")
    typer.echo(f"Clips renderizados: {report.clips_rendered}")
    typer.echo(f"Video final: {report.final_video_path}")


@app.command()
def media(slug: str = typer.Argument(help="Nombre de la carpeta en projects/<slug>/")) -> None:
    """Corre solo la investigación de medios reales (sin generar el video),
    para revisar qué se encontró antes de correr `generate`."""
    from illustrated_narrator.domain.services.forced_aligner import AlignScriptToAudio
    from illustrated_narrator.domain.services.plano_state import load_planos_state, save_planos_state
    from illustrated_narrator.domain.services.render_timeline import compute_render_durations
    from illustrated_narrator.domain.services.retention_plan import plan_shots
    from illustrated_narrator.domain.services.script_loader import load_guion
    from illustrated_narrator.domain.services.transcript_store import load_transcript, save_transcript

    container = _container()
    project = _project(slug)
    if not project.script_path.exists():
        typer.echo(f"Falta {project.script_path} — coloca ahí el guion.json.")
        raise typer.Exit(code=1)
    if container.research_plano_media is None:
        typer.echo("Investigación de medios deshabilitada (NARR_ENABLE_MEDIA_RESEARCH=0).")
        raise typer.Exit(code=1)
    if not project.audio_path.exists():
        typer.echo(f"Falta {project.audio_path} — graba la narración antes de investigar medios.")
        raise typer.Exit(code=1)

    guion = load_guion(project.script_path)
    load_planos_state(guion.planos, project.planos_alineados_path)

    transcript = load_transcript(project.transcript_path)
    already_aligned = all(p.inicio_real_seg is not None for p in guion.planos)
    if not already_aligned or transcript is None:
        transcript = container.transcriber.transcribe(
            project.audio_path, language=guion.meta.idioma[:2]
        )
        save_transcript(transcript, project.transcript_path)
    if not already_aligned:
        AlignScriptToAudio().execute(guion, transcript)
        save_planos_state(guion.planos, project.planos_alineados_path)

    alignable = [p for p in guion.planos if p.inicio_real_seg is not None]
    render_durations = compute_render_durations(alignable, container.settings.xfade_duration)
    shots_by_plano = {p.id: plan_shots(p, render_durations[p.id]) for p in alignable}

    report = container.research_plano_media.execute(
        alignable, project.images_dir, project.media_dir, project.media_manifest_path, shots_by_plano
    )
    typer.echo(f"Shots resueltos con medios reales: {report.shots_resolved}/{sum(len(s) for s in shots_by_plano.values())}")
    typer.echo(f"Manifest: {project.media_manifest_path}")
    typer.echo("Revisa media/manifest.json; para forzar una foto elegida a mano, coloca")
    typer.echo("media/<plano_id>/elegido.<ext> antes de correr `generate`.")


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
