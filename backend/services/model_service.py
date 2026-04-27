from __future__ import annotations

import json
import re
import traceback
from pathlib import Path

import torch
from PIL import Image
from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

from backend.config import MODEL_ID, MODELS_DIR


class QwenVlService:
    def __init__(self) -> None:
        self.device = "cpu"
        self.model = None
        self.processor = None

    def ensure_loaded(self) -> None:
        if self.model is not None and self.processor is not None:
            return
        if torch.cuda.is_available():
            # CPU-first default for compatibility; GPU can be enabled by env override.
            self.device = "cpu"
        model_cache = str(MODELS_DIR)
        self.processor = AutoProcessor.from_pretrained(MODEL_ID, cache_dir=model_cache, trust_remote_code=True)
        self.model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            MODEL_ID,
            cache_dir=model_cache,
            torch_dtype=torch.float32,
            low_cpu_mem_usage=True,
            trust_remote_code=True,
        ).to(self.device)
        self.model.eval()

    def analyze_image(self, image_path: Path) -> dict:
        self.ensure_loaded()
        image = Image.open(image_path).convert("RGB")
        prompt = (
            "You are an OCR and marketing metadata extractor. Return strict JSON with keys: "
            "visible_text, marketing_intent, importance_score, confidence_score. "
            "marketing_intent must be one of branding|awareness|conversion|product promo|CTA|informational|unclear. "
            "importance_score must be integer 1-10, confidence_score float 0-1. Preserve line breaks in visible_text."
        )
        chat_template = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": prompt},
                ],
            }
        ]
        text = self.processor.apply_chat_template(chat_template, tokenize=False, add_generation_prompt=True)
        inputs = self.processor(text=[text], images=[image], return_tensors="pt")
        inputs = {k: v.to(self.device) if hasattr(v, "to") else v for k, v in inputs.items()}
        with torch.no_grad():
            output_ids = self.model.generate(**inputs, max_new_tokens=768, do_sample=False)
        response = self.processor.batch_decode(output_ids, skip_special_tokens=True)[0]
        return self._parse_response(response)

    @staticmethod
    def _parse_response(response: str) -> dict:
        match = re.search(r"\{.*\}", response, re.DOTALL)
        if not match:
            return {
                "visible_text": response.strip(),
                "marketing_intent": "unclear",
                "importance_score": 1,
                "confidence_score": 0.2,
            }
        try:
            parsed = json.loads(match.group())
            parsed["importance_score"] = int(max(1, min(10, int(parsed.get("importance_score", 1)))))
            parsed["confidence_score"] = float(max(0.0, min(1.0, float(parsed.get("confidence_score", 0.2)))))
            if parsed.get("marketing_intent") not in {
                "branding",
                "awareness",
                "conversion",
                "product promo",
                "CTA",
                "informational",
                "unclear",
            }:
                parsed["marketing_intent"] = "unclear"
            parsed.setdefault("visible_text", "")
            return parsed
        except Exception:
            return {
                "visible_text": response[:4000],
                "marketing_intent": "unclear",
                "importance_score": 1,
                "confidence_score": 0.1,
                "parse_error": traceback.format_exc(limit=2),
            }
