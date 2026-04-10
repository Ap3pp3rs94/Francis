from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

try:  # pragma: no cover - optional dependency
    import torch
    import torch.nn as nn
except Exception:  # pragma: no cover
    torch = None
    nn = None

__all__ = [
    "AdversarialTraining",
    "AttackConfig",
    "AdvTrainConfig",
    "fgsm_attack",
    "pgd_attack",
    "generate_adversarial_examples",
    "train_adversarial",
    "evaluate",
]


def _torch_ready() -> bool:
    if torch is None or nn is None:
        logger.warning("PyTorch not available; adversarial training disabled.")
        return False
    return True


@dataclass(frozen=True)
class AttackConfig:
    method: str = "pgd"
    epsilon: float = 8 / 255.0
    alpha: float = 2 / 255.0
    steps: int = 10
    random_start: bool = True
    clamp_min: float = 0.0
    clamp_max: float = 1.0

    def validate(self) -> bool:
        method = self.method.lower().strip()
        if method not in {"fgsm", "pgd"}:
            logger.error("Unknown attack method: %s", self.method)
            return False
        if self.epsilon < 0 or self.alpha < 0 or self.steps < 1:
            logger.error("Invalid attack parameters")
            return False
        if not (self.clamp_min < self.clamp_max):
            logger.error("Invalid clamp range")
            return False
        return True


@dataclass(frozen=True)
class AdvTrainConfig:
    epochs: int = 1
    device: str | None = None
    adv_ratio: float = 0.5
    grad_clip_norm: float = 0.0
    amp: bool = True
    log_every: int = 50


def _default_device() -> str:
    if torch is None:
        return "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"


def _clamp(x: Any, clamp_min: float, clamp_max: float) -> Any:
    if torch is None:
        return x
    return torch.clamp(x, min=clamp_min, max=clamp_max)


def fgsm_attack(
    model: Any,
    x: Any,
    y: Any,
    loss_fn: Callable[[Any, Any], Any],
    epsilon: float,
    clamp_min: float = 0.0,
    clamp_max: float = 1.0,
) -> Any:
    if not _torch_ready():
        return x

    model.eval()
    x_adv = x.detach().clone()
    x_adv.requires_grad_(True)
    logits = model(x_adv)
    loss = loss_fn(logits, y)
    grad = torch.autograd.grad(loss, x_adv, retain_graph=False, create_graph=False)[0]
    x_adv = _clamp(x_adv + epsilon * grad.sign(), clamp_min, clamp_max)
    return x_adv.detach()


def pgd_attack(
    model: Any,
    x: Any,
    y: Any,
    loss_fn: Callable[[Any, Any], Any],
    epsilon: float,
    alpha: float,
    steps: int,
    random_start: bool = True,
    clamp_min: float = 0.0,
    clamp_max: float = 1.0,
) -> Any:
    if not _torch_ready():
        return x

    model.eval()
    x0 = x.detach()

    if random_start and epsilon > 0:
        x_adv = x0 + (2.0 * torch.rand_like(x0) - 1.0) * epsilon
        x_adv = _clamp(x_adv, clamp_min, clamp_max)
    else:
        x_adv = x0.clone()

    for _ in range(int(steps)):
        x_adv = x_adv.detach().clone().requires_grad_(True)
        logits = model(x_adv)
        loss = loss_fn(logits, y)
        grad = torch.autograd.grad(loss, x_adv, retain_graph=False, create_graph=False)[0]
        x_adv = x_adv + alpha * grad.sign()
        delta = torch.clamp(x_adv - x0, min=-epsilon, max=epsilon)
        x_adv = _clamp(x0 + delta, clamp_min, clamp_max)

    return x_adv.detach()


def generate_adversarial_examples(
    model: Any,
    x: Any,
    y: Any,
    loss_fn: Callable[[Any, Any], Any],
    attack: AttackConfig,
) -> Any:
    if not attack.validate():
        return x

    method = attack.method.lower().strip()
    if method == "fgsm":
        return fgsm_attack(model, x, y, loss_fn, attack.epsilon, attack.clamp_min, attack.clamp_max)
    return pgd_attack(
        model,
        x,
        y,
        loss_fn,
        attack.epsilon,
        attack.alpha,
        attack.steps,
        attack.random_start,
        attack.clamp_min,
        attack.clamp_max,
    )


def train_adversarial(
    model: Any,
    train_loader: Iterable[tuple[Any, Any]],
    optimizer: Any,
    *,
    loss_fn: Callable[[Any, Any], Any] | None = None,
    attack: AttackConfig | None = None,
    cfg: AdvTrainConfig | None = None,
    scheduler: Any | None = None,
) -> dict[str, float | int | str]:
    if not _torch_ready():
        return {"status": "error", "reason": "pytorch_unavailable"}

    loss_fn = loss_fn or nn.CrossEntropyLoss()
    attack = attack or AttackConfig()
    cfg = cfg or AdvTrainConfig()

    if not (0.0 <= cfg.adv_ratio <= 1.0):
        logger.error("cfg.adv_ratio must be between 0 and 1")
        return {"status": "error", "reason": "invalid_config"}

    device = cfg.device or _default_device()
    model.to(device)

    use_amp = bool(cfg.amp and device.startswith("cuda"))
    scaler = torch.cuda.amp.GradScaler(enabled=use_amp)

    seen = 0
    running_loss = 0.0
    start = time.time()

    for _ in range(int(cfg.epochs)):
        model.train()
        for x, y in train_loader:
            x = x.to(device, non_blocking=True)
            y = y.to(device, non_blocking=True)

            x_adv = None
            if cfg.adv_ratio > 0.0 and attack.epsilon > 0.0:
                x_adv = generate_adversarial_examples(model, x, y, loss_fn, attack)

            optimizer.zero_grad(set_to_none=True)
            with torch.cuda.amp.autocast(enabled=use_amp):
                logits_clean = model(x)
                loss_clean = loss_fn(logits_clean, y)
                if x_adv is not None:
                    logits_adv = model(x_adv)
                    loss_adv = loss_fn(logits_adv, y)
                    loss = (1.0 - cfg.adv_ratio) * loss_clean + cfg.adv_ratio * loss_adv
                else:
                    loss = loss_clean

            scaler.scale(loss).backward()
            if cfg.grad_clip_norm > 0:
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=cfg.grad_clip_norm)
            scaler.step(optimizer)
            scaler.update()

            if scheduler is not None:
                try:
                    scheduler.step()
                except TypeError:
                    pass

            bsz = int(y.shape[0])
            seen += bsz
            running_loss += float(loss.detach().item()) * bsz

    elapsed = time.time() - start
    return {
        "status": "ok",
        "train_loss": float(running_loss / max(1, seen)),
        "train_seconds": float(elapsed),
    }


def evaluate(
    model: Any,
    data_loader: Iterable[tuple[Any, Any]],
    *,
    loss_fn: Callable[[Any, Any], Any] | None = None,
    device: str | None = None,
) -> dict[str, float | str]:
    if not _torch_ready():
        return {"status": "error", "reason": "pytorch_unavailable"}

    loss_fn = loss_fn or nn.CrossEntropyLoss()
    device = device or _default_device()

    model.eval()
    model.to(device)

    total = 0
    sum_loss = 0.0

    with torch.no_grad():
        for x, y in data_loader:
            x = x.to(device, non_blocking=True)
            y = y.to(device, non_blocking=True)
            logits = model(x)
            loss = loss_fn(logits, y)
            bsz = int(y.shape[0])
            total += bsz
            sum_loss += float(loss.item()) * bsz

    return {"status": "ok", "loss": float(sum_loss / max(1, total))}


class AdversarialTraining:
    _active: bool = False

    @classmethod
    def initialize(cls) -> None:
        cls._active = True

    @classmethod
    def is_active(cls) -> bool:
        return cls._active

    def __init__(self, attack: AttackConfig | None = None, cfg: AdvTrainConfig | None = None) -> None:
        self.attack = attack or AttackConfig()
        self.cfg = cfg or AdvTrainConfig()

    def train(
        self,
        model: Any,
        train_loader: Iterable[tuple[Any, Any]],
        optimizer: Any,
        *,
        loss_fn: Callable[[Any, Any], Any] | None = None,
        scheduler: Any | None = None,
    ) -> dict[str, float | int | str]:
        return train_adversarial(
            model,
            train_loader,
            optimizer,
            loss_fn=loss_fn,
            attack=self.attack,
            cfg=self.cfg,
            scheduler=scheduler,
        )

    def eval(
        self,
        model: Any,
        data_loader: Iterable[tuple[Any, Any]],
        *,
        loss_fn: Callable[[Any, Any], Any] | None = None,
        device: str | None = None,
    ) -> dict[str, float | str]:
        return evaluate(model, data_loader, loss_fn=loss_fn, device=device)
