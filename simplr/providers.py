from __future__ import annotations

import os
import sys
from abc import ABC, abstractmethod
from typing import Any

from dotenv import load_dotenv
import httpx

load_dotenv()

from .parser import ErrorInfo, IndependentError
from .prompt import build_messages, build_warning_messages


class Provider(ABC):
    @abstractmethod
    def explain_error(
        self,
        error: ErrorInfo,
        infer_cfg: dict[str, Any],
        independent_errors: list[IndependentError] | None = None,
    ) -> str:
        ...

    def explain_warning(
        self,
        warning: IndependentError,
        infer_cfg: dict[str, Any],
    ) -> str:
        raise NotImplementedError("explain_warning not implemented by this provider")


class OllamaProvider(Provider):
    def __init__(self, config: dict[str, Any]) -> None:
        self.model = config["model"]
        self.host = config["host"].rstrip("/")

    def _check_connection(self) -> None:
        try:
            r = httpx.get(f"{self.host}/api/tags", timeout=5)
            r.raise_for_status()
        except httpx.ConnectError:
            print(
                f"error: cannot connect to Ollama at {self.host}\n"
                f"  Make sure Ollama is running (ollama serve)",
                file=sys.stderr,
            )
            sys.exit(1)

    def explain_error(
        self,
        error: ErrorInfo,
        infer_cfg: dict[str, Any],
        independent_errors: list[IndependentError] | None = None,
    ) -> str:
        self._check_connection()

        messages = build_messages(error, independent_errors)
        payload = {
            "model": self.model,
            "messages": messages,
            "options": {
                "temperature": infer_cfg["temperature"],
                "num_predict": infer_cfg["max_new_tokens"],
            },
            "stream": False,
        }

        r = httpx.post(f"{self.host}/api/chat", json=payload, timeout=120)
        r.raise_for_status()
        return r.json()["message"]["content"].strip()

    def explain_warning(
        self,
        warning: IndependentError,
        infer_cfg: dict[str, Any],
    ) -> str:
        self._check_connection()
        messages = build_warning_messages(warning)
        payload = {
            "model": self.model,
            "messages": messages,
            "options": {
                "temperature": infer_cfg["temperature"],
                "num_predict": infer_cfg["max_new_tokens"],
            },
            "stream": False,
        }
        r = httpx.post(f"{self.host}/api/chat", json=payload, timeout=120)
        r.raise_for_status()
        return r.json()["message"]["content"].strip()


class HuggingFaceAPIProvider(Provider):
    def __init__(self, config: dict[str, Any]) -> None:
        self.model = config["model"]
        self.token = os.environ.get("HF_TOKEN")

    def explain_error(
        self,
        error: ErrorInfo,
        infer_cfg: dict[str, Any],
        independent_errors: list[IndependentError] | None = None,
    ) -> str:
        from huggingface_hub import InferenceClient

        client = InferenceClient(token=self.token)
        messages = build_messages(error, independent_errors)

        result = client.chat_completion(
            model=self.model,
            messages=messages,
            max_tokens=infer_cfg["max_new_tokens"],
            temperature=infer_cfg["temperature"],
        )

        return result.choices[0].message.content.strip()

    def explain_warning(
        self,
        warning: IndependentError,
        infer_cfg: dict[str, Any],
    ) -> str:
        from huggingface_hub import InferenceClient
        messages = build_warning_messages(warning)
        client = InferenceClient(token=self.token)
        result = client.chat_completion(
            model=self.model,
            messages=messages,
            max_tokens=infer_cfg["max_new_tokens"],
            temperature=infer_cfg["temperature"],
        )
        return result.choices[0].message.content.strip()


class HuggingFaceProvider(Provider):
    def __init__(self, config: dict[str, Any]) -> None:
        self.model_cfg = config["huggingface"]
        self.infer_cfg = config["inference"]
        self._model = None
        self._tokenizer = None

    def _load(self) -> None:
        if self._model is not None:
            return

        model_name = self.model_cfg["model"]
        quantize = (
            self.model_cfg["quantize"]
            if self.model_cfg["quantize"] != "none"
            else None
        )
        cfg_device = self.model_cfg["device"]
        device = _pick_device(cfg_device)

        print(
            f"Loading model {model_name} (device={device})...",
            file=sys.stderr,
        )
        sys.stderr.flush()

        from transformers import AutoModelForCausalLM, AutoTokenizer

        load_kwargs: dict[str, Any] = {
            "device_map": device,
        }

        if quantize and device != "cpu":
            try:
                from transformers import BitsAndBytesConfig
                import torch

                if quantize == "4bit":
                    quant_config = BitsAndBytesConfig(
                        load_in_4bit=True,
                        bnb_4bit_compute_dtype=torch.bfloat16,
                        bnb_4bit_use_double_quant=True,
                        bnb_4bit_quant_type="nf4",
                    )
                elif quantize == "8bit":
                    quant_config = BitsAndBytesConfig(load_in_8bit=True)
                else:
                    quant_config = None

                if quant_config:
                    load_kwargs["quantization_config"] = quant_config
                    load_kwargs["torch_dtype"] = torch.bfloat16
            except ImportError:
                print(
                    "warning: bitsandbytes not installed; quantization requires GPU",
                    file=sys.stderr,
                )

        if device == "cpu" and quantize:
            print(
                "note: quantization disabled on CPU (requires GPU + bitsandbytes)",
                file=sys.stderr,
            )

        self._tokenizer = AutoTokenizer.from_pretrained(model_name)
        self._model = AutoModelForCausalLM.from_pretrained(
            model_name, **load_kwargs
        )

        model_size = sum(
            p.numel() for p in self._model.parameters()
        )
        print(
            f"Model loaded ({model_size / 1e9:.1f}B parameters).",
            file=sys.stderr,
        )
        sys.stderr.flush()

    def explain_error(
        self,
        error: ErrorInfo,
        infer_cfg: dict[str, Any],
        independent_errors: list[IndependentError] | None = None,
    ) -> str:
        self._load()

        messages = build_messages(error, independent_errors)
        prompt = self._tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self._tokenizer(prompt, return_tensors="pt").to(
            self._model.device
        )

        outputs = self._model.generate(
            **inputs,
            max_new_tokens=infer_cfg["max_new_tokens"],
            temperature=infer_cfg["temperature"],
            top_p=0.95,
            do_sample=True,
            pad_token_id=self._tokenizer.eos_token_id,
        )

        response = self._tokenizer.decode(
            outputs[0][inputs.input_ids.shape[1] :],
            skip_special_tokens=True,
        )
        return response.strip()

    def explain_warning(
        self,
        warning: IndependentError,
        infer_cfg: dict[str, Any],
    ) -> str:
        self._load()
        messages = build_warning_messages(warning)
        prompt = self._tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True,
        )
        inputs = self._tokenizer(prompt, return_tensors="pt").to(
            self._model.device
        )
        outputs = self._model.generate(
            **inputs,
            max_new_tokens=infer_cfg["max_new_tokens"],
            temperature=infer_cfg["temperature"],
            top_p=0.95,
            do_sample=True,
            pad_token_id=self._tokenizer.eos_token_id,
        )
        response = self._tokenizer.decode(
            outputs[0][inputs.input_ids.shape[1] :],
            skip_special_tokens=True,
        )
        return response.strip()


def _detect_cuda() -> tuple[bool, str]:
    try:
        import torch
    except ImportError:
        return False, "PyTorch not installed"

    if not torch.cuda.is_available():
        return False, "No CUDA-capable GPU detected"

    try:
        _ = torch.zeros(1).cuda()
        return True, "CUDA available"
    except (RuntimeError, AssertionError) as e:
        return False, f"CUDA GPU not compatible: {e}"


def _pick_device(cfg_device: str) -> str:
    if cfg_device == "cpu":
        return "cpu"
    ok, msg = _detect_cuda()
    if ok:
        return cfg_device
    if cfg_device != "cpu":
        print(f"note: {msg}; falling back to CPU", file=sys.stderr)
    return "cpu"


def create_provider(config: dict[str, Any]) -> Provider:
    provider_name = config["provider"]["name"]
    if provider_name == "ollama":
        return OllamaProvider(config["ollama"])
    elif provider_name == "huggingface":
        return HuggingFaceProvider(config)
    elif provider_name == "huggingface-api":
        return HuggingFaceAPIProvider(config["huggingface-api"])
    else:
        print(
            f"error: unknown provider '{provider_name}'. "
            f"Use 'ollama', 'huggingface', or 'huggingface-api'",
            file=sys.stderr,
        )
        sys.exit(1)
