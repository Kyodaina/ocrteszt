from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import torch
from PIL import Image
from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

from .config import settings


@dataclass
class ModelOutput:
    visible_text: str
    marketing_intent: str
    importance_score: int
    confidence_score: int


class QwenService:
    def __init__(self) -> None:
        self._model = None
        self._processor = None
        self._device = "cpu"

    @property
    def loaded(self) -> bool:
        return self._model is not None and self._processor is not None

    def load(self) -> None:
        if self.loaded:
            return
        use_cuda = torch.cuda.is_available() and not settings.prefer_cpu
        self._device = "cuda" if use_cuda else "cpu"
        dtype = torch.float16 if self._device == "cuda" else torch.float32
        self._processor = AutoProcessor.from_pretrained(
            settings.model_id,
            trust_remote_code=True,
            max_pixels=settings.max_pixels,
        )
        self._model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            settings.model_id,
            torch_dtype=dtype,
            trust_remote_code=True,
        ).to(self._device)

    def analyze_image(self, image_path: Path) -> ModelOutput:
        if not self.loaded:
            self.load()
        assert self._model is not None
        assert self._processor is not None
        image = Image.open(image_path).convert("RGB")
        image = self._resize_for_memory(image)
        prompt = (
            "You are an OCR + marketing analysis engine. Return strict JSON with keys: "
            "visible_text (string with line breaks), marketing_intent (one of branding, awareness, conversion, "
            "product promo, CTA, informational, unclear), importance_score (int 1-10), confidence_score (int 1-10)."
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
        text = self._processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = self._processor(
            text=[text],
            images=[image],
            return_tensors="pt",
            max_pixels=settings.max_pixels,
        )
        inputs = {k: v.to(self._device) for k, v in inputs.items()}
        with torch.inference_mode():
            generated_ids = self._safe_generate(inputs)
        decoded = self._processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
        json_block = self._extract_json(decoded)
        data = json.loads(json_block)
        return ModelOutput(
            visible_text=str(data.get("visible_text", "")).strip(),
            marketing_intent=str(data.get("marketing_intent", "unclear")).strip() or "unclear",
            importance_score=self._clamp_int(data.get("importance_score", 1)),
            confidence_score=self._clamp_int(data.get("confidence_score", 1)),
        )

    def _safe_generate(self, inputs: dict[str, torch.Tensor]) -> torch.Tensor:
        try:
            return self._model.generate(
                **inputs,
                max_new_tokens=settings.max_new_tokens,
                do_sample=False,
                num_beams=1,
                use_cache=False,
            )
        except RuntimeError as exc:
            message = str(exc).lower()
            if "not enough memory" not in message and "out of memory" not in message:
                raise
            if self._device == "cuda":
                torch.cuda.empty_cache()
            return self._model.generate(
                **inputs,
                max_new_tokens=settings.low_memory_max_new_tokens,
                do_sample=False,
                num_beams=1,
                use_cache=False,
            )

    @staticmethod
    def _resize_for_memory(image: Image.Image) -> Image.Image:
        width, height = image.size
        longest = max(width, height)
        if longest <= settings.max_image_side:
            return image
        scale = settings.max_image_side / float(longest)
        new_size = (max(32, int(width * scale)), max(32, int(height * scale)))
        return image.resize(new_size, Image.Resampling.LANCZOS)

    @staticmethod
    def _extract_json(text: str) -> str:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            raise ValueError(f"Model did not return JSON. Raw response: {text[:500]}")
        return match.group(0)

    @staticmethod
    def _clamp_int(value: object) -> int:
        try:
            ivalue = int(value)
        except (TypeError, ValueError):
            return 1
        return max(1, min(10, ivalue))


qwen_service = QwenService()
