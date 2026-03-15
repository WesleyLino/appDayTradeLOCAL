import sys
import os

sys.path.append(os.getcwd())

import google.generativeai as genai
from backend.microstructure_analyzer import MicrostructureAnalyzer
from backend.meta_learner import MetaLearner
from backend.news_collector import NewsCollector
from sklearn.cluster import KMeans


def test_step_by_step():
    print("1. Testing KMeans...")
    km = KMeans(n_clusters=3, n_init=10)
    print("✅ KMeans OK")

    print("2. Testing MicrostructureAnalyzer...")
    ma = MicrostructureAnalyzer()
    print("✅ MicrostructureAnalyzer OK")

    print("3. Testing MetaLearner...")
    try:
        ml = MetaLearner()
        print("✅ MetaLearner OK")
    except Exception as e:
        print(f"❌ MetaLearner FAILED: {e}")
        import traceback

        traceback.print_exc()

    print("4. Testing NewsCollector...")
    nc = NewsCollector()
    print("✅ NewsCollector OK")

    print("5. Testing GenerativeModel...")
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        print("✅ GenerativeModel OK")
    except Exception as e:
        print(f"❌ GenerativeModel FAILED: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_step_by_step()
