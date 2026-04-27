from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

import torch
from PIL import Image
from transformers import AutoModelForVision2Seq, AutoProcessor

from .schemas import OCRResult


@dataclass
class InferenceRuntime:
    processor: AutoProcessor
    model: AutoModelForVision2Seq
    device: str
    model_id: str


class QwenOCRService:
    def __init__(self, model_dir: Path) -> None:
        self.model_dir = model_dir
        self.runtime: InferenceRuntime | None = None

    def load(self) -> InferenceRuntime:
        if self.runtime:
            return self.runtime

        model_id = os.getenv("QWEN_MODEL_ID", "Qwen/Qwen2.5-VL-3B-Instruct")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if device == "cuda" else torch.float32

        processor = AutoProcessor.from_pretrained(model_id, cache_dir=str(self.model_dir))
        model = AutoModelForVision2Seq.from_pretrained(
            model_id,
            cache_dir=str(self.model_dir),
            torch_dtype=dtype,
            low_cpu_mem_usage=True,
            trust_remote_code=True,
        ).to(device)
        model.eval()

        self.runtime = InferenceRuntime(
            processor=processor,
            model=model,
            device=device,
            model_id=model_id,
        )
        return self.runtime

    def run(self, image_path: Path) -> OCRResult:
        rt = self.load()
        image = Image.open(image_path).convert("RGB")

        prompt = (
            "You are an OCR + marketing analyzer. Return JSON only with keys: "
            "visible_text (string with line breaks), marketing_intent "
            "(branding|awareness|conversion|product promo|CTA|informational|unclear), "
            "importance_score (1-10 integer), confidence_score (0-1 float), processing_status. "
            "Extract all visible text exactly as seen and infer meaning."
        )

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": prompt},
                ],
            }
        ]

        text = rt.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = rt.processor(text=[text], images=[image], return_tensors="pt").to(rt.device)

        with torch.inference_mode():
            generated = rt.model.generate(**inputs, max_new_tokens=768, do_sample=False)

        decoded = rt.processor.batch_decode(generated[:, inputs.input_ids.shape[1]:], skip_special_tokens=True)[0]
        data = self._extract_json(decoded)
        return OCRResult(
            visible_text=str(data.get("visible_text", "")).strip(),
            marketing_intent=self._normalize_intent(str(data.get("marketing_intent", "unclear"))),
            importance_score=max(1, min(10, int(float(data.get("importance_score", 1))))),
            confidence_score=max(0.0, min(1.0, float(data.get("confidence_score", 0.5)))),
            processing_status="completed",
        )

    @staticmethod
    def _extract_json(text: str) -> dict:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return {"visible_text": text, "marketing_intent": "unclear", "importance_score": 1, "confidence_score": 0.3}
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return {"visible_text": text, "marketing_intent": "unclear", "importance_score": 1, "confidence_score": 0.3}

    @staticmethod
    def _normalize_intent(intent: str) -> str:
        valid = {"branding", "awareness", "conversion", "product promo", "CTA", "informational", "unclear"}
        cleaned = intent.strip()
        return cleaned if cleaned in valid else "unclear"
