"use client";

import { useState } from "react";
import Link from "next/link";
import { downloadsApi } from "@/lib/api";

type Status = "idle" | "loading" | "done" | "error";

const PROVIDERS: Record<string, { name: string; color: string }> = {
  envato: { name: "Envato Elements", color: "text-green-400" },
  freepik: { name: "Freepik", color: "text-orange-400" },
  motionarray: { name: "Motion Array", color: "text-blue-400" },
};

function detectProvider(url: string): string | null {
  if (url.includes("elements.envato.com") || url.includes("envato.com")) return "envato";
  if (url.includes("freepik.com") || url.includes("magnific.com")) return "freepik";
  if (url.includes("motionarray.com")) return "motionarray";
  return null;
}

export default function DownloadPage() {
  const [url, setUrl] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [downloadUrl, setDownloadUrl] = useState("");
  const [remainingCredits, setRemainingCredits] = useState<number | null>(null);
  const [isToken, setIsToken] = useState(false);
  const [error, setError] = useState("");

  const detectedProvider = url ? detectProvider(url) : null;

  async function handleDownload() {
    if (!url.trim()) {
      setError("Введите ссылку");
      return;
    }
    setError("");
    setStatus("loading");
    setDownloadUrl("");

    try {
      const res = await downloadsApi.download(url.trim(), detectedProvider ?? undefined);
      setDownloadUrl(res.data.download_url);
      setRemainingCredits(res.data.remaining_credits);
      setIsToken(res.data.is_file_token);
      setStatus("done");
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setError(err.response?.data?.detail || "Ошибка при скачивании");
      setStatus("error");
    }
  }

  function handleFileDownload() {
    if (!downloadUrl) return;
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "https://envato-freepik-download.store/api";
    const href = isToken ? `${apiBase}/downloads/file/${downloadUrl}` : downloadUrl;
    window.open(href, "_blank");
  }

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
        <h1 className="text-2xl font-bold mb-2">Скачивание медиа</h1>
        <p className="text-gray-400 mb-8">Вставьте ссылку с Envato Elements, Freepik или Motion Array</p>

        {/* URL input */}
        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-2">Ссылка на файл</label>
            <div className="relative">
              <input
                type="url"
                value={url}
                onChange={(e) => { setUrl(e.target.value); setStatus("idle"); setError(""); }}
                placeholder="https://elements.envato.com/..."
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-600 focus:outline-none focus:border-blue-500 pr-32"
                onKeyDown={(e) => e.key === "Enter" && handleDownload()}
              />
              {detectedProvider && (
                <span className={`absolute right-3 top-1/2 -translate-y-1/2 text-xs font-medium ${PROVIDERS[detectedProvider].color}`}>
                  {PROVIDERS[detectedProvider].name}
                </span>
              )}
            </div>
          </div>

          {error && (
            <div className="bg-red-950 border border-red-800 rounded-lg px-4 py-3 text-red-400 text-sm">
              {error}
            </div>
          )}

          {/* Progress */}
          {status === "loading" && (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm text-gray-400">
                <span>Обрабатываем запрос...</span>
              </div>
              <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                <div className="h-full bg-blue-600 rounded-full animate-pulse w-3/4" />
              </div>
            </div>
          )}

          {/* Result */}
          {status === "done" && downloadUrl && (
            <div className="bg-green-950 border border-green-800 rounded-xl p-4 space-y-3">
              <div className="flex items-center gap-2 text-green-400">
                <span>✓</span>
                <span className="font-medium">Файл готов к скачиванию</span>
              </div>
              <button
                onClick={handleFileDownload}
                className="w-full py-3 bg-green-600 hover:bg-green-700 rounded-lg font-semibold transition flex items-center justify-center gap-2"
              >
                <span>⬇</span> Скачать файл
              </button>
              {remainingCredits !== null && (
                <p className="text-xs text-green-600 text-center">
                  Осталось кредитов: {remainingCredits}
                </p>
              )}
            </div>
          )}

          <button
            onClick={handleDownload}
            disabled={status === "loading"}
            className="w-full py-3 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg font-semibold transition"
          >
            {status === "loading" ? "Скачиваем..." : "Скачать"}
          </button>
        </div>

        {/* Supported platforms */}
        <div className="mt-8">
          <p className="text-gray-500 text-sm mb-4">Поддерживаемые платформы</p>
          <div className="grid grid-cols-3 gap-3">
            {Object.entries(PROVIDERS).map(([key, val]) => (
              <div key={key} className="bg-gray-900 border border-gray-800 rounded-lg p-3 text-center">
                <p className={`text-sm font-medium ${val.color}`}>{val.name}</p>
              </div>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}
