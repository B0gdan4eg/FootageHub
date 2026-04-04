"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { aiApi } from "@/lib/api";

type GenType = "IMAGE" | "VIDEO" | "IMAGE_TO_VIDEO";
type TaskStatus = "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED";

interface Task {
  task_id: number;
  status: TaskStatus;
  result_url?: string;
  error_message?: string;
}

interface PricingItem {
  provider: string;
  type: GenType;
  credits_per_request: number;
  description: string;
}

const TABS: { id: GenType; label: string }[] = [
  { id: "IMAGE", label: "Изображение" },
  { id: "VIDEO", label: "Видео" },
  { id: "IMAGE_TO_VIDEO", label: "Из изображения" },
];

const ASPECT_RATIOS = ["16:9", "9:16", "1:1", "4:3"];
const DURATIONS = [5, 10, 15, 30];

export default function AIPage() {
  const [tab, setTab] = useState<GenType>("IMAGE");
  const [prompt, setPrompt] = useState("");
  const [provider, setProvider] = useState("");
  const [aspectRatio, setAspectRatio] = useState("16:9");
  const [duration, setDuration] = useState(5);
  const [imageUrl, setImageUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [task, setTask] = useState<Task | null>(null);
  const [pricing, setPricing] = useState<PricingItem[]>([]);

  useEffect(() => {
    aiApi.pricing().then((res) => {
      const items = res.data as PricingItem[];
      setPricing(items);
      const first = items.find((p) => p.type === tab);
      if (first) setProvider(first.provider);
    }).catch(() => {});
  }, [tab]);

  useEffect(() => {
    const first = pricing.find((p) => p.type === tab);
    if (first) setProvider(first.provider);
  }, [tab, pricing]);

  const pollTask = useCallback((taskId: number) => {
    const interval = setInterval(async () => {
      try {
        const res = await aiApi.status(taskId);
        const data = res.data;
        setTask(data as Task);
        if (data.status === "COMPLETED" || data.status === "FAILED") {
          clearInterval(interval);
          setLoading(false);
        }
      } catch {
        clearInterval(interval);
        setLoading(false);
      }
    }, 4000);
  }, []);

  async function handleGenerate() {
    if (!prompt.trim()) {
      setError("Введите промпт");
      return;
    }
    setError("");
    setLoading(true);
    setTask(null);

    const params: Record<string, unknown> = { aspect_ratio: aspectRatio };
    if (tab === "VIDEO" || tab === "IMAGE_TO_VIDEO") {
      params.duration = duration;
    }
    if (tab === "IMAGE_TO_VIDEO" && imageUrl) {
      params.image_url = imageUrl;
    }

    try {
      const res = await aiApi.generate({ type: tab, provider, prompt, parameters: params });
      const newTask: Task = { task_id: res.data.task_id, status: "PENDING" };
      setTask(newTask);
      pollTask(res.data.task_id);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setError(err.response?.data?.detail || "Ошибка генерации");
      setLoading(false);
    }
  }

  const availableProviders = pricing.filter((p) => p.type === tab);

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Header */}
      <header className="border-b border-gray-800 px-6 py-4">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <Link href="/dashboard" className="text-xl font-bold text-blue-400">FootageHub</Link>
          <Link href="/dashboard" className="text-sm text-gray-400 hover:text-white transition">← Назад</Link>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-12">
        <h1 className="text-2xl font-bold mb-2">AI Генерация</h1>
        <p className="text-gray-400 mb-8">Создавайте изображения и видео по текстовому описанию</p>

        {/* Tabs */}
        <div className="flex gap-1 bg-gray-900 rounded-xl p-1 mb-6 border border-gray-800">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => { setTab(t.id); setTask(null); setError(""); }}
              className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium transition ${
                tab === t.id
                  ? "bg-purple-700 text-white"
                  : "text-gray-400 hover:text-white"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 space-y-4">
          {/* Prompt */}
          <div>
            <label className="block text-sm text-gray-400 mb-2">Промпт</label>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              rows={3}
              placeholder={tab === "IMAGE" ? "Красивый закат над горами в стиле аниме..." : "Cinematic drone shot of forest, 4K..."}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-600 focus:outline-none focus:border-purple-500 resize-none"
            />
          </div>

          {/* Image URL for IMAGE_TO_VIDEO */}
          {tab === "IMAGE_TO_VIDEO" && (
            <div>
              <label className="block text-sm text-gray-400 mb-2">URL исходного изображения</label>
              <input
                type="url"
                value={imageUrl}
                onChange={(e) => setImageUrl(e.target.value)}
                placeholder="https://..."
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-600 focus:outline-none focus:border-purple-500"
              />
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Provider */}
            <div>
              <label className="block text-sm text-gray-400 mb-2">Провайдер</label>
              <select
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-purple-500"
              >
                {availableProviders.length === 0 && (
                  <option value="">Загрузка...</option>
                )}
                {availableProviders.map((p) => (
                  <option key={p.provider} value={p.provider}>
                    {p.provider} — {p.credits_per_request} кр.
                  </option>
                ))}
              </select>
            </div>

            {/* Aspect ratio */}
            <div>
              <label className="block text-sm text-gray-400 mb-2">Соотношение сторон</label>
              <div className="flex gap-2">
                {ASPECT_RATIOS.map((ar) => (
                  <button
                    key={ar}
                    onClick={() => setAspectRatio(ar)}
                    className={`flex-1 py-2 text-xs rounded-lg border transition ${
                      aspectRatio === ar
                        ? "border-purple-500 bg-purple-900/30 text-white"
                        : "border-gray-700 text-gray-400 hover:border-gray-500"
                    }`}
                  >
                    {ar}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Duration for video */}
          {(tab === "VIDEO" || tab === "IMAGE_TO_VIDEO") && (
            <div>
              <label className="block text-sm text-gray-400 mb-2">Длительность (сек)</label>
              <div className="flex gap-2">
                {DURATIONS.map((d) => (
                  <button
                    key={d}
                    onClick={() => setDuration(d)}
                    className={`w-14 py-2 text-sm rounded-lg border transition ${
                      duration === d
                        ? "border-purple-500 bg-purple-900/30 text-white"
                        : "border-gray-700 text-gray-400 hover:border-gray-500"
                    }`}
                  >
                    {d}s
                  </button>
                ))}
              </div>
            </div>
          )}

          {error && (
            <div className="bg-red-950 border border-red-800 rounded-lg px-4 py-3 text-red-400 text-sm">
              {error}
            </div>
          )}

          {/* Task status */}
          {task && (
            <div className={`rounded-xl p-4 border ${
              task.status === "COMPLETED"
                ? "bg-green-950 border-green-800"
                : task.status === "FAILED"
                ? "bg-red-950 border-red-800"
                : "bg-purple-950 border-purple-800"
            }`}>
              {task.status === "PENDING" && (
                <p className="text-purple-300 text-sm animate-pulse">⏳ В очереди...</p>
              )}
              {task.status === "PROCESSING" && (
                <p className="text-purple-300 text-sm animate-pulse">🔄 Генерируем...</p>
              )}
              {task.status === "COMPLETED" && task.result_url && (
                <div className="space-y-3">
                  <p className="text-green-400 font-medium">✓ Готово!</p>
                  {tab === "IMAGE" ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={task.result_url}
                      alt="Результат генерации"
                      className="w-full rounded-lg max-h-80 object-contain"
                    />
                  ) : (
                    <video
                      src={task.result_url}
                      controls
                      className="w-full rounded-lg max-h-80"
                    />
                  )}
                  <a
                    href={task.result_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block w-full py-2 bg-green-600 hover:bg-green-700 rounded-lg text-center text-sm font-medium transition"
                  >
                    ⬇ Скачать
                  </a>
                </div>
              )}
              {task.status === "FAILED" && (
                <p className="text-red-400 text-sm">
                  Ошибка: {task.error_message || "неизвестная ошибка"}
                </p>
              )}
            </div>
          )}

          <button
            onClick={handleGenerate}
            disabled={loading}
            className="w-full py-3 bg-purple-700 hover:bg-purple-600 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg font-semibold transition"
          >
            {loading ? "Генерируем..." : "Сгенерировать"}
          </button>
        </div>
      </main>
    </div>
  );
}
