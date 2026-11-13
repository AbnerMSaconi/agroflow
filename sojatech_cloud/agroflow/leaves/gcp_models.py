"""Vision API (label detection) e endpoint do Vertex AI.

O endpoint do Vertex cobra por hora enquanto estiver implantado: implante só
para testes/demo e remova logo depois (infra/vertex_endpoint.sh).
"""
import base64

from .. import config


def baseline(path, k=5) -> list[tuple[str, float]]:
    from google.cloud import vision

    client = vision.ImageAnnotatorClient()
    with open(path, "rb") as f:
        resp = client.label_detection(image=vision.Image(content=f.read()), max_results=k)
    if resp.error.message:
        raise RuntimeError(resp.error.message)
    return [(l.description, round(l.score, 4)) for l in resp.label_annotations]


def classify(path) -> tuple[str, float, dict]:
    from google.cloud import aiplatform

    aiplatform.init(project=config.GCP_PROJECT, location=config.VERTEX_REGION)
    endpoint = aiplatform.Endpoint(config.VERTEX_ENDPOINT_ID)
    with open(path, "rb") as f:
        content = base64.b64encode(f.read()).decode()
    pred = endpoint.predict(instances=[{"content": content}],
                            parameters={"confidenceThreshold": 0.0, "maxPredictions": 10}).predictions[0]
    scores = dict(zip(pred["displayNames"], (round(c, 4) for c in pred["confidences"])))
    best = max(scores, key=scores.get)
    return best, scores[best], scores
