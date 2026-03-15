"""
Smoke test — Roadmap IA (ASCII only, sem emojis)
"""

import sys
import os
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.abspath("."))

# Patch de compatibilidade onnxscript antes de qualquer import
try:
    import onnxscript.values as _ov

    if not hasattr(_ov, "ParamSchema"):
        _ov.ParamSchema = type("ParamSchema", (), {})
except Exception:
    pass

import logging

logging.disable(logging.CRITICAL)  # suprimir todos os logs internos

results = []


def check(label, fn):
    try:
        fn()
        results.append(("PASS", label))
        print(f"  [PASS] {label}", flush=True)
    except Exception as e:
        results.append(("FAIL", f"{label}: {type(e).__name__}: {e}"))
        print(f"  [FAIL] {label}: {type(e).__name__}: {e}", flush=True)


def test_ai_core():
    from backend.ai_core import AICore

    e = AICore()
    r = e.calculate_decision(obi=0.8, sentiment=0.5, patchtst_score=0.90)
    assert "quantile_confidence" in r, "quantile_confidence ausente"
    assert r["direction"] in ("BUY", "SELL", "NEUTRAL")


def test_ai_core_quantile_dict():
    from backend.ai_core import AICore

    e = AICore()
    # Simula o dict retornado pelo PatchTST com quantis
    score_dict = {
        "score": 0.92,
        "q10": 0.80,
        "q50": 0.91,
        "q90": 0.98,
        "forecast_norm": 100.0,
        "uncertainty_norm": 1.0,
    }
    r = e.calculate_decision(obi=0.9, sentiment=0.6, patchtst_score=score_dict)
    assert r["breakdown"]["q10"] == 0.80, "q10 nao propagado"
    assert r["breakdown"]["q90"] == 0.98, "q90 nao propagado"
    # Com spread_up > spread_down * 1.2, deve ser HIGH ou VERY_HIGH
    assert r["quantile_confidence"] in ("HIGH", "VERY_HIGH"), (
        f"confidence esperada HIGH|VERY_HIGH, recebeu: {r['quantile_confidence']}"
    )


def test_rl_agent():
    from backend.rl_agent import PPOAgent

    agent = PPOAgent(input_dim=8, n_actions=3)
    state = [0.5, 0.2, 1.0, 0.8, 1.0, 0.1, 1.0, 0.02]
    action, log_prob = agent.select_action(state)
    assert action in (0, 1, 2)


def test_rl_shadow_build_state():
    from backend.rl_shadow_monitor import build_state

    pos = {
        "ticket": 1,
        "type": 0,
        "volume": 1.0,
        "price_open": 130000,
        "sl": 129850,
        "tp": 130150,
        "profit": 20.0,
        "time_open_mins": 15.0,
    }
    state = build_state(pos, current_price=130050.0, atr=50.0)
    assert state.shape == (8,), f"shape errada: {state.shape}"
    assert all(x is not None and (x == x) for x in state), "NaN no estado"


def test_cvd_ofi():
    import pandas as pd
    from backend.data_collector_historical import HistoricalDataCollector

    col = HistoricalDataCollector.__new__(HistoricalDataCollector)
    df = pd.DataFrame(
        {
            "open": [100.0, 101.0, 99.0],
            "high": [102.0, 103.0, 101.0],
            "low": [99.0, 100.0, 98.0],
            "close": [101.0, 102.0, 98.0],
            "real_volume": [1000.0, 1200.0, 800.0],
            "time": pd.date_range("2026-01-01", periods=3, freq="1min"),
        }
    )
    out = col.calculate_cvd_ofi_from_candles(df)
    for col_name in ["cvd", "ofi", "volume_ratio"]:
        assert col_name in out.columns, f"coluna {col_name} ausente"
        assert out[col_name].isna().sum() == 0, f"NaN em {col_name}"


def test_train_module():
    import backend.train_patchtst as tr

    for fn in ["load_all_sota_data", "export_to_onnx", "train_sota"]:
        assert hasattr(tr, fn), f"funcao {fn} ausente"


def test_onnx_exists():
    path = "backend/patchtst_weights_sota.onnx"
    assert os.path.isfile(path), "ONNX nao encontrado"
    assert os.path.getsize(path) > 1_000_000, "ONNX muito pequeno"


def test_pth_exists():
    assert os.path.isfile("backend/patchtst_weights_sota.pth"), ".pth nao encontrado"


def test_best_params():
    import json

    assert os.path.isfile("best_params_WIN.json"), "best_params_WIN.json nao encontrado"
    with open("best_params_WIN.json") as f:
        p = json.load(f)
    assert len(p) > 0, "JSON vazio"


def test_csv_with_cvd():
    import glob
    import pandas as pd

    files = glob.glob("data/sota_training/training_WIN*MASTER.csv")
    if not files:
        files = glob.glob("**/training_WIN*MASTER.csv", recursive=True)
    assert files, "MASTER CSV WIN$ nao encontrado"
    df = pd.read_csv(files[0], nrows=10)
    for col_name in ["cvd", "ofi", "volume_ratio"]:
        assert col_name in df.columns, (
            f"coluna {col_name} ausente no CSV. Colunas: {list(df.columns)}"
        )


def test_bot_sniper_lot_scaling():
    src = open("backend/bot_sniper_win.py", encoding="utf-8").read()
    # Garantir que lot_map existe no codigo
    assert "lot_map" in src, "lot_map nao encontrado em bot_sniper_win.py"
    # Garantir que quantile_confidence esta na assinatura
    assert "quantile_confidence" in src, (
        "quantile_confidence ausente em bot_sniper_win.py"
    )
    # Garantir que calculate_decision substituiu predict_regime
    assert "calculate_decision" in src, "calculate_decision nao encontrado"
    assert "predict_regime" not in src, (
        "predict_regime ainda presente (deveria ter sido substituido)"
    )
    # Verificar os 3 niveis de lote
    assert '"NORMAL": 1.0' in src or '"NORMAL": 1.0' in src, (
        "lote NORMAL=1 nao encontrado"
    )
    assert '"VERY_HIGH": 3.0' in src or '"VERY_HIGH": 3.0' in src, (
        "lote VERY_HIGH=3 nao encontrado"
    )


TESTS = [
    ("ai_core - quantile_confidence presente", test_ai_core),
    ("ai_core - Q10/Q90 propagados no breakdown", test_ai_core_quantile_dict),
    ("rl_agent - PPOAgent select_action OK", test_rl_agent),
    ("rl_shadow - build_state shape=(8,) sem NaN", test_rl_shadow_build_state),
    ("data_collector - CVD/OFI/vol_ratio calculados", test_cvd_ofi),
    ("train_patchtst - funcoes presentes", test_train_module),
    ("artefato ONNX gerado (>=1MB)", test_onnx_exists),
    ("artefato .pth gerado", test_pth_exists),
    ("best_params_WIN.json valido", test_best_params),
    ("WIN$ CSV MASTER com CVD/OFI", test_csv_with_cvd),
    ("bot_sniper - lot_map quantile_confidence (F22)", test_bot_sniper_lot_scaling),
]


if __name__ == "__main__":
    print("", flush=True)
    print("=== SMOKE TEST ROADMAP IA ===", flush=True)
    print("", flush=True)
    for label, fn in TESTS:
        check(label, fn)

    fails = [r for r in results if r[0] == "FAIL"]
    passes = len(results) - len(fails)

    print("", flush=True)
    print(f"Resultado: {passes}/{len(results)} PASS", flush=True)
    if fails:
        print("FALHAS:", flush=True)
        for _, msg in fails:
            print(f"  - {msg}", flush=True)
        sys.exit(1)
    else:
        print("TODOS OS TESTES PASSARAM.", flush=True)
        sys.exit(0)
