import os

def count_lines_in_project(path="."):
    total_lines = 0
    file_stats = []

    for root, _, files in os.walk(path):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        line_count = sum(1 for _ in f)
                        file_stats.append((file_path, line_count))
                        total_lines += line_count
                except Exception as e:
                    print(f"Ошибка при чтении {file_path}: {e}")

    # Сортируем по убыванию количества строк
    file_stats.sort(key=lambda x: x[1], reverse=True)

    print("📊 Статистика строк кода:")
    for file_path, line_count in file_stats:
        print(f"{file_path} — {line_count} строк")

    print("\n======================")
    print(f"Всего строк кода: {total_lines}")
    print("======================")

if __name__ == "__main__":
    count_lines_in_project(".")

