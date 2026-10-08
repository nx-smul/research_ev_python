import pytest

import main as cli
from src.pipeline import RealDataPreflightError


def test_real_data_preflight_error_is_reported_without_traceback(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["main.py"])
    monkeypatch.setattr(
        cli,
        "run_full_pipeline",
        lambda *args, **kwargs: (_ for _ in ()).throw(RealDataPreflightError("missing provenance")),
    )

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 2
    output = capsys.readouterr().err
    assert "missing provenance" in output
    assert "python main.py --data-mode demo" in output
    assert "Traceback" not in output


def test_sensitivity_flag_is_passed_to_pipeline(monkeypatch):
    monkeypatch.setattr("sys.argv", ["main.py", "--sensitivity"])
    captured = {}

    def fake_pipeline(*args, **kwargs):
        captured.update(kwargs)
        raise RealDataPreflightError("expected test stop")

    monkeypatch.setattr(cli, "run_full_pipeline", fake_pipeline)
    with pytest.raises(SystemExit):
        cli.main()

    assert captured["sensitivity"] is True
