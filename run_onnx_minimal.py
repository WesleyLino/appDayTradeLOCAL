import onnxruntime as ort

try:
    print(f"ONNX Runtime Version: {ort.get_version_string()}")
    print(f"Available Providers: {ort.get_available_providers()}")
    
    # Simple check for DirectML
    if 'DmlExecutionProvider' in ort.get_available_providers():
        print("✅ DirectML Provider found!")
    else:
        print("❌ DirectML Provider NOT found.")
        
except Exception as e:
    print(f"❌ Error during ONNX initialization: {e}")
    import traceback
    traceback.print_exc()
