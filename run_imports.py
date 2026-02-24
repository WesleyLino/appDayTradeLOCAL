import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

def test_import(module_name):
    print(f"Testing import of {module_name}...")
    try:
        __import__(module_name)
        print(f"✅ Success: {module_name}")
    except Exception:
        print(f"❌ Failed: {module_name}")
        import traceback
        traceback.print_exc()
        print("-" * 50)

modules = [
    "backend.mt5_bridge",
    "backend.risk_manager",
    "backend.ai_core",
    "backend.persistence",
    "backend.rl_agent",
    "backend.microstructure_analyzer",
    "backend.data_collector",
    "backend.sentiment_analyzer",
    "backend.calendar_manager"
]

for m in modules:
    test_import(m)
