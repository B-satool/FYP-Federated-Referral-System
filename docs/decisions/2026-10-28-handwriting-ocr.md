# Decision: read handwritten prescriptions with Google Cloud Vision

- **Date:** 2026-10-28
- **Status:** decided by the project lead on 2026-10-28. Built the same day. Not yet tried against the real
  service, because no `GOOGLE_VISION_API_KEY` is set yet.

## What it does

With `OCR_ENGINE=google_vision`, each scanned page or photo is sent to Google Cloud Vision
(`DOCUMENT_TEXT_DETECTION`), which reads printed text and handwriting. It returns lines with their positions and a
confidence (0–100), in the same format as Tesseract. The highlight on the page image and the existing field reader
therefore work unchanged. Staff still check every field against the image before it is used. Handwriting misreads
are expected.

If Vision is unavailable (no key, network, quota, or an error), the page is read with Tesseract and the paper says
so. The key is sent in the `X-Goog-Api-Key` header, never in the URL.

## Privacy

The page image leaves this computer. Unlike text, it cannot be de-identified: names and CNICs written on the paper
go to Google. Use synthetic papers only until the operating institution agrees. Restrict the API key to the Cloud
Vision API in the Google Cloud console.

## Tests

`services/central/tests/test_vision_ocr.py` tests the request shape, line building, the key in the header, and the
fallback, all against a fake endpoint.
