import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

import logging

logging.basicConfig(level=logging.DEBUG)


def test_instantiation():
    print("--- Starting Instantiation Test ---")
    try:
        from backend.mt5_bridge import MT5Bridge
        from backend.risk_manager import RiskManager
        from backend.ai_core import AICore
        from backend.persistence import PersistenceManager
        from backend.rl_agent import PPOAgent
        from backend.microstructure_analyzer import MicrostructureAnalyzer

        print("Instantiating components...")
        bridge = MT5Bridge()
        risk = RiskManager()
        ai = AICore()
        persistence = PersistenceManager()
        rl_agent = PPOAgent(input_dim=7, n_actions=3)
        micro_analyzer = MicrostructureAnalyzer()

        print("✅ Instantiation Success!")

        # Test InferenceEngine specifically
        from backend.ai_core import InferenceEngine

        weights_path = os.path.join(os.getcwd(), "backend", "patchtst_weights_sota.pth")
        print(f"Testing InferenceEngine with {weights_path}...")
        inference = InferenceEngine(weights_path)
        print("✅ InferenceEngine Instantiation Success!")

    except Exception as e:
        print(f"❌ Instantiation Failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_instantiation()
