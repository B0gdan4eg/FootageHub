"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { adminApi, User } from "@/lib/api";

interface Stats {
  total_users: number;
  total_downloads: number;
  total_revenue_usd: number;
  active_subscriptions: number;
}

interface UserRow extends User {
  created_at: string;
  tg_id?: number | null;
}

interface EditModal {
  user: UserRow;
  credits: string;
  ai_credits: string;
  role: string;
  saving: boolean;
  error: string;
}

export default function AdminPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [users, setUsers] = useState<UserRow[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [modal, setModal] = useState<EditModal | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [statsRes, usersRes] = await Promise.all([
        adminApi.stats(),
        adminApi.users(page, search || undefined),
      ]);
      setStats(statsRes.data as Stats);
      const data = usersRes.data as { items: UserRow[]; total_pages: number };
      setUsers(data.items ?? []);
      setTotalPages(data.total_pages ?? 1);
    } catch (e: unknown) {
      const err = e as { response?: { status?: number } };
      if (err.response?.status === 403) {
        setError("Доступ запрещён");
      } else {
        setError("Ошибка загрузки");
      }
    } finally {
      setLoading(false);
    }
  }, [page, search]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  function openEdit(user: UserRow) {
    setModal({
      user,
      credits: String(user.credits),
      ai_credits: String(user.ai_credits),
      role: user.role,
      saving: false,
      error: "",
    });
  }

  async function handleSave() {
    if (!modal) return;
    setModal((m) => m ? { ...m, saving: true, error: "" } : m);
    try {
      await adminApi.updateUser(modal.user.id, {
        role: modal.role,
        credits: Number(modal.credits),
        ai_credits: Number(modal.ai_credits),
      });
      setModal(null);
      loadData();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setModal((m) => m ? { ...m, saving: false, error: err.response?.data?.detail || "Ошибка" } : m);
    }
  }

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setSearch(searchInput);
    setPage(1);
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center text-white">
        <div className="text-center">
          <p className="text-red-400 text-lg mb-4">{error}</p>
          <Link href="/dashboard" className="text-blue-400 hover:underline">← Назад</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Header */}
      <header className="border-b border-gray-800 px-6 py-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/dashboard" className="text-xl font-bold text-blue-400">FootageHub</Link>
            <span className="text-xs bg-yellow-500/20 text-yellow-400 px-2 py-1 rounded-full">Admin</span>
          </div>
          <Link href="/dashboard" className="text-sm text-gray-400 hover:text-white transition">← Кабинет</Link>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-10 space-y-8">
        <h1 className="text-2xl font-bold">Панель администратора</h1>

        {/* Stats */}
        {stats && (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { label: "Пользователей", value: stats.total_users, color: "text-blue-400" },
              { label: "Скачиваний", value: stats.total_downloads, color: "text-green-400" },
              { label: "Выручка", value: `$${stats.total_revenue_usd?.toFixed(2) ?? "0"}`, color: "text-yellow-400" },
              { label: "Подписок активных", value: stats.active_subscriptions, color: "text-purple-400" },
            ].map((s) => (
              <div key={s.label} className="bg-gray-900 border border-gray-800 rounded-xl p-5">
                <p className="text-gray-400 text-sm mb-1">{s.label}</p>
                <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
              </div>
            ))}
          </div>
        )}

        {/* Search */}
        <form onSubmit={handleSearch} className="flex gap-2">
          <input
            type="text"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Поиск по username, телефону..."
            className="flex-1 bg-gray-900 border border-gray-800 rounded-lg px-4 py-2 text-white placeholder-gray-600 focus:outline-none focus:border-blue-500"
          />
          <button
            type="submit"
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm transition"
          >
            Найти
          </button>
          {search && (
            <button
              type="button"
              onClick={() => { setSearch(""); setSearchInput(""); setPage(1); }}
              className="px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm transition"
            >
              Сброс
            </button>
          )}
        </form>

        {/* Users table */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 text-gray-400">
                  <th className="text-left px-4 py-3 font-medium">ID</th>
                  <th className="text-left px-4 py-3 font-medium">Пользователь</th>
                  <th className="text-left px-4 py-3 font-medium">Телефон</th>
                  <th className="text-left px-4 py-3 font-medium">Роль</th>
                  <th className="text-right px-4 py-3 font-medium">Кредиты</th>
                  <th className="text-right px-4 py-3 font-medium">AI</th>
                  <th className="text-left px-4 py-3 font-medium">Дата</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td colSpan={8} className="text-center py-8 text-gray-500">Загрузка...</td>
                  </tr>
                ) : users.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="text-center py-8 text-gray-500">Ничего не найдено</td>
                  </tr>
                ) : (
                  users.map((u) => (
                    <tr key={u.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                      <td className="px-4 py-3 text-gray-500">{u.id}</td>
                      <td className="px-4 py-3">
                        <div>
                          <p className="text-white">{u.username || "—"}</p>
                          {u.tg_id && <p className="text-xs text-gray-500">tg: {u.tg_id}</p>}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-gray-300">{u.phone_number || "—"}</td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                          u.role === "admin"
                            ? "bg-yellow-500/20 text-yellow-400"
                            : u.role === "premium"
                            ? "bg-blue-500/20 text-blue-400"
                            : "bg-gray-700 text-gray-400"
                        }`}>
                          {u.role}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right text-green-400">{u.credits}</td>
                      <td className="px-4 py-3 text-right text-purple-400">{u.ai_credits}</td>
                      <td className="px-4 py-3 text-gray-500 text-xs">
                        {new Date(u.created_at).toLocaleDateString("ru-RU")}
                      </td>
                      <td className="px-4 py-3">
                        <button
                          onClick={() => openEdit(u)}
                          className="text-xs text-blue-400 hover:underline"
                        >
                          Изменить
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-3 py-1 bg-gray-800 hover:bg-gray-700 disabled:opacity-40 rounded text-sm transition"
            >
              ←
            </button>
            <span className="text-sm text-gray-400">
              {page} / {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="px-3 py-1 bg-gray-800 hover:bg-gray-700 disabled:opacity-40 rounded text-sm transition"
            >
              →
            </button>
          </div>
        )}
      </main>

      {/* Edit modal */}
      {modal && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 px-4">
          <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6 w-full max-w-sm space-y-4">
            <h2 className="font-bold text-lg">
              Редактировать: {modal.user.username || modal.user.phone_number || `#${modal.user.id}`}
            </h2>

            <div>
              <label className="block text-sm text-gray-400 mb-1">Роль</label>
              <select
                value={modal.role}
                onChange={(e) => setModal((m) => m ? { ...m, role: e.target.value } : m)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500"
              >
                <option value="user">user</option>
                <option value="premium">premium</option>
                <option value="admin">admin</option>
              </select>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm text-gray-400 mb-1">Кредиты</label>
                <input
                  type="number"
                  value={modal.credits}
                  onChange={(e) => setModal((m) => m ? { ...m, credits: e.target.value } : m)}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">AI-кредиты</label>
                <input
                  type="number"
                  value={modal.ai_credits}
                  onChange={(e) => setModal((m) => m ? { ...m, ai_credits: e.target.value } : m)}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>

            {modal.error && <p className="text-red-400 text-sm">{modal.error}</p>}

            <div className="flex gap-2 pt-2">
              <button
                onClick={() => setModal(null)}
                className="flex-1 py-2 border border-gray-700 rounded-lg text-sm hover:border-gray-500 transition"
              >
                Отмена
              </button>
              <button
                onClick={handleSave}
                disabled={modal.saving}
                className="flex-1 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded-lg text-sm font-medium transition"
              >
                {modal.saving ? "Сохраняем..." : "Сохранить"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
