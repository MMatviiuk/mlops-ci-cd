import json

import torch
import torchvision.models as models


def export_mobilenet(
    output_path: str = "model.pt",
    labels_path: str = "imagenet_labels.json",
) -> None:
    weights = models.MobileNet_V2_Weights.DEFAULT
    model = models.mobilenet_v2(weights=weights)
    model.eval()
    dummy_input = torch.rand(1, 3, 224, 224)
    scripted = torch.jit.trace(model, dummy_input)
    scripted.save(output_path)

    labels = weights.meta.get("categories", [])
    if not labels:
        raise ValueError("Не вдалося отримати перелік класів ImageNet.")

    with open(labels_path, "w", encoding="utf-8") as labels_file:
        json.dump(labels, labels_file, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    export_mobilenet()
