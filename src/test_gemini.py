import numpy as np
import cv2
import gemini_verifier as g

g.start()

if not g.is_available():
    raise SystemExit("Gemini did not start")

img = np.full((360, 640, 3), 255, np.uint8)
cv2.putText(img, "TEST", (220, 200), cv2.FONT_HERSHEY_SIMPLEX, 3, (0, 0, 0), 5)

try:
    result = g._ask([("Test image:", g._jpeg(img))], {}, ["Team A", "Team B"])
    print("GEMINI WORKS. Reply:", result)
except Exception as e:
    print("GEMINI FAILED:", e)