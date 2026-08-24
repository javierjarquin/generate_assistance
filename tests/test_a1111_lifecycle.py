from illustrated_narrator.adapters.video import a1111_lifecycle


class _FakeCompletedProcess:
    def __init__(self, stdout: str = "") -> None:
        self.stdout = stdout


def test_restart_a1111_mata_todos_los_procesos_launch_py(monkeypatch):
    # launch.py arranca varios procesos python.exe relacionados -- matar
    # solo el que escucha el puerto dejaba huérfanos (confirmado en una
    # corrida real: hasta 6 procesos acumulados tras varios reinicios,
    # cada uno reteniendo VRAM). El fix busca y mata TODOS los que matchean
    # 'launch.py' en una sola pasada, no un PID puntual.
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if "Select-Object -ExpandProperty ProcessId" in cmd[-1] and "Stop-Process" not in cmd[-1]:
            return _FakeCompletedProcess(stdout="4242\n7777\n")
        return _FakeCompletedProcess()

    monkeypatch.setattr(a1111_lifecycle.subprocess, "run", fake_run)
    monkeypatch.setattr(a1111_lifecycle.subprocess, "Popen", lambda *a, **kw: None)
    monkeypatch.setattr(a1111_lifecycle.time, "sleep", lambda *_: None)
    monkeypatch.setattr(
        a1111_lifecycle.requests, "get",
        lambda *a, **kw: type("R", (), {"ok": True})(),
    )

    ok = a1111_lifecycle.restart_a1111(
        "http://127.0.0.1:7860", "run_a1111.bat", "C:\\tools", ready_timeout=5,
    )

    assert ok is True
    kill_calls = [c for c in calls if "Stop-Process" in c[-1]]
    assert len(kill_calls) == 1
    # El filtro se arma partido (concatenado) dentro del script, no como
    # literal en el comando que Python invoca -- si el string completo
    # apareciera literal, el filtro podría automatchearse a sí mismo (bug
    # real ya confirmado: exit code 255 por autoeliminación).
    assert "launch.py" not in kill_calls[0][-1]
    assert "'launch' + '.py'" in kill_calls[0][-1]


def test_restart_a1111_sin_proceso_previo_solo_relanza(monkeypatch):
    monkeypatch.setattr(
        a1111_lifecycle.subprocess, "run", lambda *a, **kw: _FakeCompletedProcess(stdout="")
    )
    popen_calls = []
    monkeypatch.setattr(
        a1111_lifecycle.subprocess, "Popen", lambda *a, **kw: popen_calls.append((a, kw))
    )
    monkeypatch.setattr(a1111_lifecycle.time, "sleep", lambda *_: None)
    monkeypatch.setattr(
        a1111_lifecycle.requests, "get",
        lambda *a, **kw: type("R", (), {"ok": True})(),
    )

    ok = a1111_lifecycle.restart_a1111(
        "http://127.0.0.1:7860", "run_a1111.bat", "C:\\tools", ready_timeout=5,
    )

    assert ok is True
    assert len(popen_calls) == 1


def test_restart_a1111_devuelve_false_si_nunca_responde(monkeypatch):
    monkeypatch.setattr(
        a1111_lifecycle.subprocess, "run", lambda *a, **kw: _FakeCompletedProcess(stdout="")
    )
    monkeypatch.setattr(a1111_lifecycle.subprocess, "Popen", lambda *a, **kw: None)
    monkeypatch.setattr(a1111_lifecycle.time, "sleep", lambda *_: None)

    import requests as real_requests

    def always_fails(*a, **kw):
        raise real_requests.RequestException("no conecta")

    monkeypatch.setattr(a1111_lifecycle.requests, "get", always_fails)

    ok = a1111_lifecycle.restart_a1111(
        "http://127.0.0.1:7860", "run_a1111.bat", "C:\\tools", ready_timeout=0.01,
    )

    assert ok is False
