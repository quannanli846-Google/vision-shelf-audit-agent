"""Concrete `VisionClient` implementations, one module per provider.

Each provider module is only imported lazily, from `vision/client.py`'s
`build_vision_client()` factory, once its provider name is actually
selected - so e.g. the `openai` SDK is never imported at all in a
mock-only/Groq-only run, and vice versa.
"""
