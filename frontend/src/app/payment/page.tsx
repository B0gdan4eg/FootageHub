"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { paymentsApi } from "@/lib/api";

type PayProvider = "webpay" | "cryptobot";

interface Plan {
  key: string;
  name: string;
  price_usd: number;
  credits: number;
  ai_credits: number;
  description: string;
  popular?: boolean;
}

export default function PaymentPage() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);
  const [payProvider, setPayProvider] = useState<PayProvider>("webpay");
  const [paying, setPaying] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    paymentsApi.plans()
      .then((res) => setPlans(res.data as Plan[]))
      .catch(() => setError("Не удалось загрузить тарифы"))
      .finally(() => setLoading(false));
  }, []);

  async function handlePay() {
    if (!selected) {
      setError("Выберите тариф");
      return;
    }
    setError("");
    setPaying(true);
    try {
      const res = await paymentsApi.create(selected, payProvider);
      window.location.href = res.data.invoice_url;
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setError(err.response?.data?.detail || "Ошибка создания платежа");
      setPaying(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Header */}
      <header className="border-b border-gray-800 px-6 py-4">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <Link href="/dashboard" className="text-xl font-bold text-blue-400">FootageHub</Link>
          <Link href="/dashboard" className="text-sm text-gray-400 hover:text-white transition">← Назад</Link>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-12">
        <h1 className="text-2xl font-bold mb-2">Пополнить баланс</h1>
        <p className="text-gray-400 mb-8">Выберите тариф и способ оплаты</p>

        {loading && (
          <div className="text-gray-400 text-center py-12">Загрузка тарифов...</div>
        )}

        {!loading && plans.length === 0 && !error && (
          <div className="text-gray-400 text-center py-12">Тарифы не найдены</div>
        )}

        {error && (
          <div className="bg-red-950 border border-red-800 rounded-lg px-4 py-3 text-red-400 text-sm mb-6">
            {error}
          </div>
        )}

        {/* Plans grid */}
        {plans.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
            {plans.map((plan) => (
              <button
                key={plan.key}
                onClick={() => setSelected(plan.key)}
                className={`text-left rounded-xl p-5 border transition ${
                  selected === plan.key
                    ? "border-blue-500 bg-blue-950"
                    : plan.popular
                    ? "border-blue-700 bg-gray-900 hover:border-blue-500"
                    : "border-gray-700 bg-gray-900 hover:border-gray-500"
                }`}
              >
                {plan.popular && (
                  <div className="text-xs text-blue-400 font-semibold mb-2">ПОПУЛЯРНЫЙ</div>
                )}
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <p className="font-bold text-lg">{plan.name}</p>
                    <p className="text-2xl font-bold text-blue-400">${plan.price_usd}</p>
                  </div>
                  {selected === plan.key && (
                    <div className="w-5 h-5 rounded-full bg-blue-500 flex items-center justify-center text-xs">✓</div>
                  )}
                </div>
                <div className="space-y-1 text-sm text-gray-400">
                  <p>⬇ {plan.credits} кредитов на скачивание</p>
                  {plan.ai_credits > 0 && <p>🤖 {plan.ai_credits} AI-кредитов</p>}
                  {plan.description && <p className="text-gray-500 text-xs mt-2">{plan.description}</p>}
                </div>
              </button>
            ))}
          </div>
        )}

        {/* Payment method */}
        {plans.length > 0 && (
          <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 space-y-4">
            <h2 className="font-semibold">Способ оплаты</h2>

            <div className="grid grid-cols-2 gap-3">
              <button
                onClick={() => setPayProvider("webpay")}
                className={`py-4 rounded-xl border flex flex-col items-center gap-2 transition ${
                  payProvider === "webpay"
                    ? "border-blue-500 bg-blue-950"
                    : "border-gray-700 hover:border-gray-500"
                }`}
              >
                <span className="text-2xl">💳</span>
                <span className="text-sm font-medium">Банковская карта</span>
                <span className="text-xs text-gray-500">WebPay</span>
              </button>

              <button
                onClick={() => setPayProvider("cryptobot")}
                className={`py-4 rounded-xl border flex flex-col items-center gap-2 transition ${
                  payProvider === "cryptobot"
                    ? "border-blue-500 bg-blue-950"
                    : "border-gray-700 hover:border-gray-500"
                }`}
              >
                <span className="text-2xl">₿</span>
                <span className="text-sm font-medium">Криптовалюта</span>
                <span className="text-xs text-gray-500">CryptoBot</span>
              </button>
            </div>

            <button
              onClick={handlePay}
              disabled={!selected || paying}
              className="w-full py-3 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg font-semibold transition"
            >
              {paying
                ? "Перенаправление..."
                : selected
                ? `Оплатить $${plans.find((p) => p.key === selected)?.price_usd}`
                : "Выберите тариф"}
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
