from illustrated_narrator.adapters.video import a1111_lifecycle


class _FakeCompletedProcess:
    def __init__(self, stdout: str = "") -> None:
        self.stdout = stdout


def test_restart_a1111_mata_el_pid_que_escucha_el_puerto(monkeypatch):
    # Se busca el pid por el puerto (Get-NetTCPConnection), no por texto de
    # línea de comando -- un filtro de PowerShell con 'launch.py' en el
    # string puede automatchearse a sí mismo (bug real ya visto en esta
    # misma investigación: exit code 255 por autoeliminación).
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if "Get-NetTCPConnection" in cmd[-1]:
            return _FakeCompletedProcess(stdout="4242\n")
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
    assert "-Id 4242" in kill_calls[0][-1]


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
