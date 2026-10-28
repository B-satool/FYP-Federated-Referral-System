"""Google Cloud Vision OCR (handwriting), against a local fake endpoint: no key, no network, no cost."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from PIL import Image

from app.config import settings
from app.documents import processing

CAPTURED: dict = {}
REPLY: dict = {"status": 200, "body": {}}


class FakeVision(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("content-length", 0))
        CAPTURED.update(path=self.path, headers=dict(self.headers), body=json.loads(self.rfile.read(length)))
        body = json.dumps(REPLY["body"]).encode()
        self.send_response(REPLY["status"])
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture()
def vision(monkeypatch):
    srv = HTTPServer(("127.0.0.1", 0), FakeVision)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(settings, "google_vision_endpoint", f"http://127.0.0.1:{srv.server_port}/v1/images:annotate")
    monkeypatch.setattr(settings, "google_vision_api_key", "test-key")
    monkeypatch.setattr(settings, "ocr_engine", "google_vision")
    yield
    srv.shutdown()


def word(text, x, y, conf=0.9, brk=None):
    symbols = [{"text": ch} for ch in text]
    if brk:
        symbols[-1]["property"] = {"detectedBreak": {"type": brk}}
    return {"boundingBox": {"vertices": [{"x": x, "y": y}, {"x": x + 10 * len(text), "y": y},
                                         {"x": x + 10 * len(text), "y": y + 20}, {"x": x, "y": y + 20}]},
            "confidence": conf, "symbols": symbols}


def handwritten_prescription():
    words = [word("Tab", 10, 100, brk="SPACE"), word("Glucophage", 50, 100, brk="SPACE"), word("500mg", 160, 100, brk="SPACE"),
             word("BD", 220, 100, 0.6, brk="EOL_SURE_SPACE"),
             word("Tab", 10, 140, brk="SPACE"), word("Loprin", 50, 140, 0.7, brk="SPACE"), word("75mg", 120, 140, brk="LINE_BREAK")]
    return {"responses": [{"fullTextAnnotation": {"pages": [{"blocks": [{"paragraphs": [{"words": words}]}]}]}}]}


PAGE = Image.new("RGB", (1000, 500), "white")


def test_handwriting_is_read_line_by_line_with_boxes(vision):
    REPLY.update(status=200, body=handwritten_prescription())
    lines, conf = processing.vision_page(PAGE)
    assert [ln["text"] for ln in lines] == ["Tab Glucophage 500mg BD", "Tab Loprin 75mg"]
    assert lines[0]["bbox"]["x"] == pytest.approx(0.01) and lines[0]["bbox"]["y"] == pytest.approx(0.2)
    assert lines[0]["ocr_confidence"] == pytest.approx(82.5)  # 0-100, like Tesseract
    assert conf is not None
    req = CAPTURED["body"]["requests"][0]
    assert req["features"] == [{"type": "DOCUMENT_TEXT_DETECTION"}] and req["image"]["content"]
    assert CAPTURED["headers"].get("X-Goog-Api-Key") == "test-key" and "key=" not in CAPTURED["path"]  # key never in the URL


def test_vision_failure_falls_back_to_tesseract_and_says_so(vision, monkeypatch):
    monkeypatch.setattr(processing, "ocr_page", lambda img: ([{"text": "printed", "bbox": None, "ocr_confidence": 90}], 90.0))
    for status, body in ((403, {}), (200, {"responses": [{"error": {"code": 7, "message": "API key not valid"}}]})):
        REPLY.update(status=status, body=body)
        notes: list[str] = []
        lines, _, engine = processing.read_page(PAGE, notes)
        assert engine == "tesseract" and lines[0]["text"] == "printed"
        assert notes and "Google Vision" in notes[0]


def test_no_key_never_calls_google(monkeypatch):
    monkeypatch.setattr(settings, "ocr_engine", "google_vision")
    monkeypatch.setattr(settings, "google_vision_api_key", "")
    monkeypatch.setattr(processing, "ocr_page", lambda img: ([], None))
    notes: list[str] = []
    assert processing.read_page(PAGE, notes)[2] == "tesseract" and "no GOOGLE_VISION_API_KEY" in notes[0]
