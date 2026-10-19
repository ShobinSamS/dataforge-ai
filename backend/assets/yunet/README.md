# Bundled local photo proposal model

`face_detection_yunet_2023mar.onnx` is the small YuNet face detector from
[OpenCV Zoo](https://github.com/opencv/opencv_zoo/tree/47534e27c9851bb1128ccc0102f1145e27f23f98/models/face_detection_yunet).
The original MIT license is in `LICENSE`. `source.json` records the upstream
commit and the SHA-256 of the actual ONNX bytes (not a Git LFS pointer).

The model is bundled so document uploads work offline without runtime model
downloads. Inference finds faces only; the surrounding photo bounds are inferred
from an enclosing panel or estimated head/shoulder bounds. This does not identify
people or recognize their names. Users can correct or delete all proposals.
