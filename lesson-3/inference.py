import argparse
import json
from pathlib import Path

import torch
from PIL import Image
from torchvision import transforms


LABELS_FILE = Path(__file__).with_name("imagenet_labels.json")
DEFAULT_MODEL_PATH = Path(__file__).with_name("model.pt")
SUPPORTED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def is_valid_image(image_path: Path) -> bool:
    try:
        with Image.open(image_path) as image:
            image.verify()
        return True
    except Exception:
        return False


def load_labels() -> list[str]:
    if not LABELS_FILE.exists():
        raise FileNotFoundError(
            "Файл imagenet_labels.json не знайдено. Спочатку запусти export_model.py."
        )

    with open(LABELS_FILE, encoding="utf-8") as labels_file:
        return json.load(labels_file)


def resolve_image_path(input_path: str) -> Path:
    path = Path(input_path).expanduser().resolve()

    if path.is_file():
        return path

    if path.is_dir():
        candidates = sorted(
            file_path
            for file_path in path.iterdir()
            if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES
        )
        for candidate in candidates:
            if is_valid_image(candidate):
                return candidate
        raise FileNotFoundError(
            f"У папці {path} не знайдено валідних зображень підтримуваного формату."
        )

    raise FileNotFoundError(f"Шлях {path} не існує.")


def preprocess(image_path: Path) -> torch.Tensor:
    transform = transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
    image = Image.open(image_path).convert("RGB")
    return transform(image).unsqueeze(0)


def predict_top3(model_path: Path, image_path: Path) -> list[tuple[str, float]]:
    model = torch.jit.load(model_path)
    model.eval()
    labels = load_labels()
    tensor = preprocess(image_path)
    with torch.inference_mode():
        output = model(tensor)
    probabilities = torch.softmax(output[0], dim=0)
    top3 = torch.topk(probabilities, 3)
    return [(labels[idx.item()], round(score.item(), 4)) for score, idx in zip(top3.values, top3.indices)]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Запуск top-3 inference для TorchScript-моделі."
    )
    parser.add_argument(
        "input_path",
        help="Шлях до зображення або до папки, де є хоча б одне зображення.",
    )
    parser.add_argument(
        "model_path",
        nargs="?",
        default=str(DEFAULT_MODEL_PATH),
        help="Необов'язковий шлях до TorchScript-моделі.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    image_path = resolve_image_path(args.input_path)
    model_path = Path(args.model_path).expanduser().resolve()

    if not model_path.exists():
        raise FileNotFoundError(f"Модель {model_path} не знайдена.")

    results = predict_top3(model_path, image_path)
    print(f"Вхідне зображення: {image_path}")
    print("Top-3 передбачення:")
    for rank, (label, score) in enumerate(results, start=1):
        print(f"  {rank}. {label}: {score:.2%}")


if __name__ == "__main__":
    main()
