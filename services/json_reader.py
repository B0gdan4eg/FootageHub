import json
from types import SimpleNamespace

def dict_to_namespace(d):
    if isinstance(d, dict):
        # Рекурсивно преобразуем все вложенные словари
        return SimpleNamespace(**{k: dict_to_namespace(v) for k, v in d.items()})
    elif isinstance(d, list):
        # Если список, то преобразуем каждый элемент
        return [dict_to_namespace(i) for i in d]
    else:
        return d

# Читаем JSON из файла
with open(r"bot\prices_list.json", "r", encoding="utf-8") as f:
    data_dict = json.load(f)
