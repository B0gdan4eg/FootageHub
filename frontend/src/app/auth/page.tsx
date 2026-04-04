"use client";

import { useState, useRef, useEffect, useCallback, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { authApi, TelegramAuthResult } from "@/lib/api";
import { setToken } from "@/lib/auth";

type Step = "choose" | "phone" | "code" | "link";

declare global {
  interface Window {
    onTelegramAuth?: (user: TelegramAuthResult) => void;
  }
}

function AuthPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirect = searchParams.get("redirect") || "/dashboard";

  const [step, setStep] = useState<Step>("choose");
  const [phone, setPhone] = useState("+7");
  const [code, setCode] = useState(["", "", "", "", "", ""]);
  const [timer, setTimer] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [refCode, setRefCode] = useState("");
  const [linkRequestId, setLinkRequestId] = useState<number | null>(null);
  const [linkStatus, setLinkStatus] = useState("");
  const [botUsername, setBotUsername] = useState<string | null>(null);

  const codeRefs = useRef<(HTMLInputElement | null)[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const tgScriptRef = useRef<HTMLScriptElement | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  // Загружаем bot_username при монтировании
  useEffect(() => {
    authApi.telegramConfig()
      .then((res) => setBotUsername(res.data.bot_username))
      .catch(() => setBotUsername(null));
  }, []);

  const handleTelegramCallback = useCallback(
    async (user: TelegramAuthResult) => {
      setError("");
      setLoading(true);
      try {
        const res = await authApi.telegramLogin(user);
        setToken(res.data.access_token);
        router.push(redirect);
      } catch (e: unknown) {
        const err = e as { response?: { data?: { detail?: string } } };
        setError(err.response?.data?.detail || "Ошибка авторизации через Telegram");
        setLoading(false);
      }
    },
    [redirect, router]
  );

  // Монтируем виджет Telegram когда переходим к нужному шагу и знаем bot_username
  useEffect(() => {
    if (step !== "choose" || !botUsername) return;

    window.onTelegramAuth = handleTelegramCallback;

    // Удаляем старый скрипт если есть
    if (tgScriptRef.current) {
      tgScriptRef.current.remove();
      tgScriptRef.current = null;
    }

    const container = document.getElementById("telegram-login-container");
    if (!container) return;

    // Очищаем контейнер
    container.innerHTML = "";

    const script = document.createElement("script");
    script.src = "https://telegram.org/js/telegram-widget.js?22";
    script.setAttribute("data-telegram-login", botUsername);
    script.setAttribute("data-size", "large");
    script.setAttribute("data-radius", "8");
    script.setAttribute("data-onauth", "onTelegramAuth(user)");
    script.setAttribute("data-request-access", "write");
    script.async = true;

    container.appendChild(script);
    tgScriptRef.current = script;

    return () => {
      delete window.onTelegramAuth;
    };
  }, [step, botUsername, handleTelegramCallback]);

  function startTimer() {
    setTimer(60);
    timerRef.current = setInterval(() => {
      setTimer((t) => {
        if (t <= 1) {
          clearInterval(timerRef.current!);
          return 0;
        }
        return t - 1;
      });
    }, 1000);
  }

  function formatPhone(value: string): string {
    const digits = value.replace(/\D/g, "");
    let result = "+7";
    if (digits.length > 1) result += " (" + digits.slice(1, 4);
    if (digits.length >= 4) result += ") " + digits.slice(4, 7);
    if (digits.length >= 7) result += "-" + digits.slice(7, 9);
    if (digits.length >= 9) result += "-" + digits.slice(9, 11);
    return result;
  }

  function handlePhoneChange(e: React.ChangeEvent<HTMLInputElement>) {
    const formatted = formatPhone(e.target.value);
    setPhone(formatted);
  }

  function getRawPhone(): string {
    return "+" + phone.replace(/\D/g, "");
  }

  async function handleSendCode() {
    setError("");
    const raw = getRawPhone();
    if (raw.length < 12) {
      setError("Введите полный номер телефона");
      return;
    }
    setLoading(true);
    try {
      await authApi.sendCode(raw);
      setStep("code");
      startTimer();
      setTimeout(() => codeRefs.current[0]?.focus(), 100);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setError(err.response?.data?.detail || "Ошибка отправки кода");
    } finally {
      setLoading(false);
    }
  }

  function handleCodeChange(index: number, value: string) {
    if (!/^\d?$/.test(value)) return;
    const next = [...code];
    next[index] = value;
    setCode(next);
    if (value && index < 5) {
      codeRefs.current[index + 1]?.focus();
    }
  }

  function handleCodeKeyDown(index: number, e: React.KeyboardEvent) {
    if (e.key === "Backspace" && !code[index] && index > 0) {
      codeRefs.current[index - 1]?.focus();
    }
  }

  function handleCodePaste(e: React.ClipboardEvent) {
    const text = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6);
    if (text.length === 6) {
      setCode(text.split(""));
      codeRefs.current[5]?.focus();
    }
    e.preventDefault();
  }

  async function handleVerify() {
    const fullCode = code.join("");
    if (fullCode.length < 6) {
      setError("Введите все 6 цифр");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const res = await authApi.verifyCode(getRawPhone(), fullCode);
      setToken(res.data.access_token);
      router.push(redirect);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setError(err.response?.data?.detail || "Неверный код");
    } finally {
      setLoading(false);
    }
  }

  async function handleLinkBot() {
    if (!refCode.trim()) {
      setError("Введите реферальный код");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const res = await authApi.linkBot(refCode.trim());
      setLinkRequestId(res.data.request_id);
      setLinkStatus("pending");
      pollLinkStatus(res.data.request_id);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setError(err.response?.data?.detail || "Ошибка привязки");
    } finally {
      setLoading(false);
    }
  }

  function pollLinkStatus(requestId: number) {
    const poll = setInterval(async () => {
      try {
        const res = await authApi.linkStatus(requestId);
        if (res.data.status === "CONFIRMED" && res.data.access_token) {
          clearInterval(poll);
          setToken(res.data.access_token);
          router.push("/dashboard");
        } else if (res.data.status === "REJECTED" || res.data.status === "EXPIRED") {
          clearInterval(poll);
          setLinkStatus(res.data.status);
          setError("Запрос отклонён или истёк. Попробуйте снова.");
        }
      } catch {
        clearInterval(poll);
      }
    }, 3000);
  }

  const subtitle = {
    choose: "Выберите способ входа",
    phone: "Вход по номеру телефона",
    code: "Введите код из SMS",
    link: "Привязка Telegram-аккаунта",
  }[step];

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="text-2xl font-bold text-blue-400 mb-2">FootageHub</div>
          <p className="text-gray-400 text-sm">{subtitle}</p>
        </div>

        <div className="bg-gray-900 rounded-2xl border border-gray-800 p-8">
          {/* Step 0: Choose method */}
          {step === "choose" && (
            <div className="space-y-4">
              {error && <p className="text-red-400 text-sm text-center">{error}</p>}

              {/* Telegram Login Widget */}
              {botUsername ? (
                <div>
                  <p className="text-gray-400 text-sm text-center mb-3">
                    Войдите через Telegram одним нажатием
                  </p>
                  {loading ? (
                    <div className="flex justify-center py-3">
                      <span className="text-gray-400 text-sm">Вход...</span>
                    </div>
                  ) : (
                    <div id="telegram-login-container" className="flex justify-center" />
                  )}
                </div>
              ) : (
                <div className="flex justify-center py-2">
                  <div className="w-48 h-10 bg-gray-800 rounded-lg animate-pulse" />
                </div>
              )}

              <div className="relative flex items-center gap-3 py-1">
                <div className="flex-1 h-px bg-gray-700" />
                <span className="text-gray-600 text-xs">или</span>
                <div className="flex-1 h-px bg-gray-700" />
              </div>

              <button
                onClick={() => { setStep("phone"); setError(""); }}
                className="w-full py-3 bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded-lg text-sm text-gray-300 hover:text-white transition"
              >
                Войти по номеру телефона (SMS)
              </button>

              <button
                onClick={() => { setStep("link"); setError(""); }}
                className="w-full py-2 text-sm text-gray-500 hover:text-gray-300 transition"
              >
                Привязать аккаунт из бота
              </button>
            </div>
          )}

          {/* Step 1: Phone */}
          {step === "phone" && (
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-gray-400 mb-2">Номер телефона</label>
                <input
                  type="tel"
                  value={phone}
                  onChange={handlePhoneChange}
                  placeholder="+7 (___) ___-__-__"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white text-lg placeholder-gray-600 focus:outline-none focus:border-blue-500"
                  onKeyDown={(e) => e.key === "Enter" && handleSendCode()}
                />
              </div>

              {error && <p className="text-red-400 text-sm">{error}</p>}

              <button
                onClick={handleSendCode}
                disabled={loading}
                className="w-full py-3 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg font-semibold transition"
              >
                {loading ? "Отправка..." : "Получить код"}
              </button>

              <button
                onClick={() => { setStep("choose"); setError(""); }}
                className="w-full py-2 text-sm text-gray-500 hover:text-gray-300 transition"
              >
                ← Назад
              </button>
            </div>
          )}

          {/* Step 2: Code */}
          {step === "code" && (
            <div className="space-y-6">
              <p className="text-gray-400 text-sm text-center">
                Код отправлен на <span className="text-white">{phone}</span>
              </p>

              <div className="flex gap-2 justify-center" onPaste={handleCodePaste}>
                {code.map((digit, i) => (
                  <input
                    key={i}
                    ref={(el) => { codeRefs.current[i] = el; }}
                    type="text"
                    inputMode="numeric"
                    maxLength={1}
                    value={digit}
                    onChange={(e) => handleCodeChange(i, e.target.value)}
                    onKeyDown={(e) => handleCodeKeyDown(i, e)}
                    className="w-12 h-14 text-center text-xl font-bold bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:border-blue-500"
                  />
                ))}
              </div>

              {error && <p className="text-red-400 text-sm text-center">{error}</p>}

              <button
                onClick={handleVerify}
                disabled={loading}
                className="w-full py-3 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg font-semibold transition"
              >
                {loading ? "Проверка..." : "Войти"}
              </button>

              <div className="text-center">
                {timer > 0 ? (
                  <span className="text-gray-500 text-sm">Повторно через {timer} сек</span>
                ) : (
                  <button
                    onClick={() => { setStep("phone"); setCode(["", "", "", "", "", ""]); }}
                    className="text-blue-400 hover:text-blue-300 text-sm transition"
                  >
                    Изменить номер или запросить снова
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Step 3: Link bot */}
          {step === "link" && (
            <div className="space-y-4">
              <p className="text-gray-400 text-sm">
                Введите ваш реферальный код из Telegram-бота. Мы отправим запрос на подтверждение.
              </p>

              <input
                type="text"
                value={refCode}
                onChange={(e) => setRefCode(e.target.value)}
                placeholder="Реферальный код"
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-600 focus:outline-none focus:border-blue-500"
              />

              {error && <p className="text-red-400 text-sm">{error}</p>}

              {linkRequestId && linkStatus === "pending" && (
                <div className="bg-blue-950 border border-blue-800 rounded-lg p-4 text-sm text-blue-300">
                  Ожидаем подтверждения в Telegram... Проверьте бота.
                </div>
              )}

              <button
                onClick={handleLinkBot}
                disabled={loading || linkStatus === "pending"}
                className="w-full py-3 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg font-semibold transition"
              >
                {loading ? "Отправка..." : "Привязать аккаунт"}
              </button>

              <button
                onClick={() => { setStep("choose"); setError(""); }}
                className="w-full py-2 text-sm text-gray-500 hover:text-gray-300 transition"
              >
                ← Назад
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function AuthPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-gray-950" />}>
      <AuthPageInner />
    </Suspense>
  );
}
