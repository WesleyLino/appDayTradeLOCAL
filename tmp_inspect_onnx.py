import onnxruntime as ort

try:
    path = "backend/models/patchtst_weights_sota_optimized.onnx"
    sess = ort.InferenceSession(path)
    for i in sess.get_inputs():
        print(f"Input: {i.name}, Shape: {i.shape}, Type: {i.type}")
    for o in sess.get_outputs():
        print(f"Output: {o.name}, Shape: {o.shape}, Type: {o.type}")
except Exception as e:
    print(f"Error: {e}")
