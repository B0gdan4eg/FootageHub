"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { usersApi, User } from "@/lib/api";
import { clearToken } from "@/lib/auth";

interface Download {
  id: number;
  url: string;
  provider: string;
  created_at: string;
}

interface Subscription {
  id: number;
  plan_name: string;
  downloads_used: number;
  downloads_limit: number;
  expires_at: string;
}

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [downloads, setDownloads] = useState<Download[]>([]);
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [profileRes, downloadsRes, subsRes] = await Promise.all([
          usersApi.profile(),
          usersApi.downloads(1),
          usersApi.subscriptions(),
        ]);
        setUser(profileRes.data);
        setDownloads((downloadsRes.data as { items?: Download[] }).items?.slice(0, 5) ?? []);
        setSubscriptions((subsRes.data as Subscription[]) ?? []);
      } catch {
        router.push("/auth");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [router]);

  function handleLogout() {
    clearToken();
    router.push("/");
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="text-gray-400">Загрузка...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Header */}
      <header className="border-b border-gray-800 px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <Link href="/" className="text-xl font-bold text-blue-400">FootageHub</Link>
          <nav className="flex items-center gap-4">
            <Link href="/download" className="text-sm text-gray-400 hover:text-white transition">Скачать</Link>
            <Link href="/ai" className="text-sm text-gray-400 hover:text-white transition">AI</Link>
            <Link href="/payment" className="text-sm text-gray-400 hover:text-white transition">Тарифы</Link>
            {user?.role === "admin" && (
              <Link href="/admin" className="text-sm text-yellow-400 hover:text-yellow-300 transition">Админ</Link>
            )}
            <button
              onClick={handleLogout}
              className="text-sm text-gray-500 hover:text-white transition"
            >
              Выйти
            </button>
          </nav>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-10 space-y-8">
        {/* Welcome */}
        <div>
          <h1 className="text-2xl font-bold">
            Привет, {user?.username || user?.phone_number || "пользователь"} 👋
          </h1>
        </div>

        {/* Balance cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
            <p className="text-gray-400 text-sm mb-1">Кредиты на скачивание</p>
            <p className="text-3xl font-bold text-blue-400">{user?.credits ?? 0}</p>
            <Link
              href="/payment"
              className="mt-4 inline-block text-sm text-blue-400 hover:underline"
            >
              Пополнить →
            </Link>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
            <p className="text-gray-400 text-sm mb-1">AI-кредиты</p>
            <p className="text-3xl font-bold text-purple-400">{user?.ai_credits ?? 0}</p>
            <Link
              href="/payment"
              className="mt-4 inline-block text-sm text-purple-400 hover:underline"
            >
              Пополнить →
            </Link>
          </div>
        </div>

        {/* Quick actions */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Link
            href="/download"
            className="bg-blue-600 hover:bg-blue-700 rounded-xl p-5 transition flex items-center gap-3"
          >
            <span className="text-2xl">⬇️</span>
            <div>
              <p className="font-semibold">Скачать медиа</p>
              <p className="text-sm text-blue-200">Envato, Freepik, Motion Array</p>
            </div>
          </Link>
          <Link
            href="/ai"
            className="bg-purple-700 hover:bg-purple-800 rounded-xl p-5 transition flex items-center gap-3"
          >
            <span className="text-2xl">🤖</span>
            <div>
              <p className="font-semibold">Генерация AI</p>
              <p className="text-sm text-purple-200">Изображения и видео по промпту</p>
            </div>
          </Link>
        </div>

        {/* Active subscriptions */}
        {subscriptions.length > 0 && (
          <div>
            <h2 className="text-lg font-semibold mb-4">Активные подписки</h2>
            <div className="space-y-3">
              {subscriptions.map((sub) => (
                <div key={sub.id} className="bg-gray-900 border border-gray-800 rounded-xl p-4 flex items-center justify-between">
                  <div>
                    <p className="font-medium">{sub.plan_name}</p>
                    <p className="text-sm text-gray-400">
                      Использовано: {sub.downloads_used} / {sub.downloads_limit}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-gray-400">
                      До {new Date(sub.expires_at).toLocaleDateString("ru-RU")}
                    </p>
                    <div className="mt-1 w-32 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-blue-500 rounded-full"
                        style={{ width: `${Math.min((sub.downloads_used / sub.downloads_limit) * 100, 100)}%` }}
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Recent downloads */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold">Последние скачивания</h2>
            <Link href="/download" className="text-sm text-blue-400 hover:underline">
              Скачать ещё →
            </Link>
          </div>

          {downloads.length === 0 ? (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-8 text-center">
              <p className="text-gray-500 mb-4">Скачиваний пока нет</p>
              <Link
                href="/download"
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm transition"
              >
                Первое скачивание
              </Link>
            </div>
          ) : (
            <div className="space-y-2">
              {downloads.map((d) => (
                <div key={d.id} className="bg-gray-900 border border-gray-800 rounded-lg px-4 py-3 flex items-center justify-between">
                  <div className="min-w-0">
                    <p className="text-sm text-gray-300 truncate">{d.url}</p>
                    <p className="text-xs text-gray-500 mt-0.5">
                      {d.provider} · {new Date(d.created_at).toLocaleString("ru-RU")}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
