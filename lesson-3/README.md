# ДЗ3. Контейнеризація ML-моделей

## Структура проєкту

```
lesson-3/
├── inference.py           # скрипт для top-3 передбачень
├── export_model.py        # генерація model.pt та imagenet_labels.json
├── model.pt               # збережена TorchScript-модель
├── imagenet_labels.json   # назви класів ImageNet
├── Dockerfile.fat         # великий образ для локальної перевірки
├── Dockerfile.slim        # оптимізований образ з multi-stage збіркою
├── install_dev_tools.sh   # скрипт встановлення середовища
├── comparison.txt         # порівняння двох образів
└── README.md
```

## Крок 1. Генерація моделі

```bash
pip install torch torchvision pillow
python3 export_model.py
# Створює model.pt та imagenet_labels.json у поточній директорії
```

## Крок 2. Локальний запуск

```bash
python3 inference.py <шлях_до_зображення>
# Приклад:
python3 inference.py cat.jpg
# Або явно передати шлях до моделі:
python3 inference.py cat.jpg model.pt
# Або передати папку, тоді буде взято перше знайдене зображення:
python3 inference.py ./images
```

## Крок 3. Збірка Docker-образів

```bash
# Fat-образ
docker build -f Dockerfile.fat -t ml-fat .

# Slim-образ
docker build -f Dockerfile.slim -t ml-slim .
```

`Dockerfile.fat` навмисно залишає додаткові інструменти та wheel-файли
у фінальному образі. Через це після збірки на ARM64 його розмір перевищує 1 GB.

## Крок 4. Запуск у контейнері

```bash
# Підготувати власне тестове зображення
# Наприклад: cat.jpg або будь-який інший валідний JPEG/PNG-файл

# Локально
python3 inference.py /шлях/до/вашого_зображення.jpg

# Fat
docker run --rm \
  --mount type=bind,source="/абсолютний/шлях/до/вашого_зображення.jpg",target=/app/input.jpg \
  ml-fat python inference.py input.jpg

# Slim
docker run --rm \
  --mount type=bind,source="/абсолютний/шлях/до/вашого_зображення.jpg",target=/app/input.jpg \
  ml-slim python inference.py input.jpg
```

Тестове зображення не входить до обов'язкового переліку файлів для здачі.
Тому його зручно зберігати окремо від папки `lesson-3` і монтувати тільки під час запуску.

## Крок 5. Порівняння образів

```bash
docker image inspect ml-fat --format '{{.Size}}'
docker image inspect ml-slim --format '{{.Size}}'
docker history ml-fat
docker history ml-slim
```

Детальний звіт: [comparison.txt](./comparison.txt)

Актуальні результати після перевірки на Mac з Apple Silicon:

- `ml-fat`: `1,569,830,155` bytes (`~1.57 GB`), `18` шарів
- `ml-slim`: `212,508,092` bytes (`~212.5 MB`), `14` шарів

## Встановлення середовища в Linux

```bash
chmod +x install_dev_tools.sh
./install_dev_tools.sh
# Лог: install.log
```
