from __future__ import annotations

_model = None


def _get_model():
    global _model
    if _model is None:
        from backend.config import HF_TOKEN
        if HF_TOKEN:
            import huggingface_hub
            huggingface_hub.login(token=HF_TOKEN, add_to_git_credential=False)
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def split_into_paragraphs(text: str, min_length: int = 100) -> list[str]:
    raw = [p.strip() for p in text.split("\n\n") if p.strip()]
    merged: list[str] = []
    buffer = ""
    for para in raw:
        buffer = (buffer + "\n\n" + para).strip() if buffer else para
        if len(buffer) >= min_length:
            merged.append(buffer)
            buffer = ""
    if buffer:
        if merged:
            merged[-1] = merged[-1] + "\n\n" + buffer
        else:
            merged.append(buffer)
    return merged


def embed_text(text: str) -> list[float]:
    model = _get_model()
    return model.encode(text, convert_to_numpy=True).tolist()


def embed_batch(texts: list[str]) -> list[list[float]]:
    model = _get_model()
    return model.encode(texts, convert_to_numpy=True).tolist()
