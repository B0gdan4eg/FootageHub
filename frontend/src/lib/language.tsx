"use client";

import { createContext, useContext, useEffect, useMemo, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { nextTranslation, type TranslationState } from "./translation-state";

type Language = "ru" | "en";

type LanguageContextValue = {
  language: Language;
  setLanguage: (language: Language) => void;
};

const LanguageContext = createContext<LanguageContextValue | null>(null);

const STORAGE_KEY = "fh_lang";
const RU_LANGUAGE_PREFIXES = ["ru", "be", "uk", "kk"];

const exactTranslations: Record<string, string> = {
  "Как работает": "How it works",
  "Стоки": "Sources",
  "Тарифы": "Pricing",
  "Сравнение": "Comparison",
  "Войти": "Sign in",
  "Попробовать": "Try it",
  "Кабинет": "Dashboard",
  "Оплата": "Payment",
  "На главную": "Home",
  "← На главную": "← Home",
  "Главная": "Home",
  "AI-генерации": "AI generation",
  "Продукт": "Product",
  "Аккаунт": "Account",
  "Контакты": "Contacts",
  "Оферта": "Offer",
  "Политика": "Policy",
  "Правила": "Rules",
  "Telegram-бот": "Telegram bot",
  "Канал новостей": "News channel",
  "Поддержка": "Support",
  "Бот в строю · 14 521 файлов выдано": "Bot online · 14,521 files delivered",
  "Устал искать,": "Tired of hunting",
  "где взять шаблоны?": "for templates?",
  "Вставь ссылку с Envato, Freepik или Motion Array — забери файл за 5–10 секунд. Без подписок, без танцев.": "Paste an Envato, Freepik, or Motion Array link and get the file in 5–10 seconds. No subscriptions, no hassle.",
  "Получить": "Get file",
  "Ищу…": "Searching...",
  "Готово": "Ready",
  "Скачать": "Download",
  "Без VPN": "No VPN",
  "Авторизация в 2 клика": "2-click login",
  "опять Envato $33/мес?": "Envato again at $33/mo?",
  "→ Получить": "→ Get file",
  "«опять Envato $33/мес?»": "«Envato again at $33/mo?»",
  "$33/мес": "$33/mo",
  "$20/мес": "$20/mo",
  "$11/мес": "$11/mo",
  "$39.99/мес": "$39.99/mo",
  "Как это работает": "How it works",
  "Три шага. Никакой магии.": "Three steps. No magic.",
  "Три шага. Никакой": "Three steps. No",
  "магии.": "magic.",
  "~ 8 сек": "~ 8 sec",
  "~8 сек": "~8 sec",
  "Вставь ссылку": "Paste a link",
  "Копируй URL шаблона с Envato, Freepik или Motion Array — в боте или прямо на сайте.": "Copy an Envato, Freepik, or Motion Array asset URL into the bot or the website.",
  "Бот достаёт файл": "The bot gets the file",
  "Качаем оригинал с премиум-аккаунта за 5–10 секунд. Без водяных знаков, без обрезок.": "We fetch the original from a premium account in 5–10 seconds. No watermarks, no crops.",
  "Скачивай и работай": "Download and work",
  "Прямая ссылка прилетает в Telegram. Работает на всех устройствах.": "A direct link arrives in Telegram. Works on any device.",
  "Поддерживаемые стоки": "Supported sources",
  "Один бот — все стоки в одном кармане.": "One bot, all sources in your pocket.",
  "Один бот — все стоки": "One bot — all sources",
  "в одном кармане.": "in one place.",
  "Видео, аудио, шаблоны AE/Premiere": "Video, audio, AE/Premiere templates",
  "Векторы, фото, PSD, иконки": "Vectors, photos, PSDs, icons",
  "AE, Premiere, DaVinci, плагины": "AE, Premiere, DaVinci, plugins",
  "работает": "online",
  "тех. работы": "maintenance",
  "Реальные отзывы из Telegram": "Real Telegram reviews",
  "Скриншоты от тех, кто уже пользуется.": "Screenshots from people already using it.",
  "Без редактуры, без актёров — реальные сообщения в поддержку и боту.": "No editing, no actors: real messages to support and the bot.",
  "Подписки vs FootageHub": "Subscriptions vs FootageHub",
  "Подписки vs": "Subscriptions vs",
  "Купить отдельно": "Buy separately",
  "Доступ к Envato Elements": "Envato Elements access",
  "Доступ к Freepik Premium+": "Freepik Premium+ access",
  "Доступ к Motion Array": "Motion Array access",
  "Привязка к одному устройству": "Locked to one device",
  "VPN для оплаты из РФ": "VPN for payment",
  "Старт за 2 минуты": "Start in 2 minutes",
  "Итого в месяц": "Monthly total",
  "включено": "included",
  "Да": "Yes",
  "Нет": "No",
  "Нужен": "Required",
  "Не нужен": "Not required",
  "Карта + регистрация": "Card + registration",
  "Telegram + СБП": "Telegram + fast payment",
  "Дешевле любой подписки.": "Cheaper than any subscription.",
  "Дешевле любой": "Cheaper than any",
  "подписки.": "subscription.",
  "Для теста": "For testing",
  "Самый популярный": "Most popular",
  "Для агентств": "For agencies",
  "50 файлов в месяц": "50 files per month",
  "150 файлов в месяц": "150 files per month",
  "400 файлов в месяц": "400 files per month",
  "Все стоки кроме Motion Array": "All sources except Motion Array",
  "Все стоки": "All sources",
  "Хранение 7 дней": "Storage for 7 days",
  "Хранение 30 дней": "Storage for 30 days",
  "Хранение 90 дней": "Storage for 90 days",
  "Поддержка в Telegram": "Telegram support",
  "Приоритет в очереди": "Priority queue",
  "Все стоки + ранний доступ к новым": "All sources + early access to new ones",
  "Личный менеджер": "Personal manager",
  "Скидка на AI-генерации": "AI generation discount",
  "Начать с Lite": "Start with Lite",
  "Взять Standard": "Get Standard",
  "Хочу Pro": "I want Pro",
  "в месяц": "per month",
  "за файл": "per file",
  "Популярный": "Popular",
  "★ ПОПУЛЯРНЫЙ": "★ POPULAR",
  "в месяц ·": "per month ·",
  "API + bulk-режим": "API + bulk mode",
  "Частые вопросы": "FAQ",
  "Ответим до того, как спросишь.": "Answers before you ask.",
  "Ответим до того,": "Answers before",
  "как": "you",
  "спросишь.": "ask.",
  "Скачивание и файлы": "Downloads and files",
  "Файл скачивается не сразу?": "Does the file not download immediately?",
  "Если файл не скачался с первого раза — попробуй ещё раз, это решает 90% проблем.": "If the file did not download the first time, try again. That solves most issues.",
  "Можно ли скачать файл повторно?": "Can I download the file again?",
  "Да, просто отправь ссылку снова. Повторные скачивания одного и того же файла не списываются с лимита в течение 24 часов.": "Yes, just send the link again. Repeat downloads of the same file do not count against your limit for 24 hours.",
  "Подписка и лимиты": "Subscription and limits",
  "Что считается за «скачивание»?": "What counts as a download?",
  "Только успешно завершённые загрузки. Если что-то пошло не так — лимит не списывается.": "Only successful downloads count. If something goes wrong, your limit is not used.",
  "Когда начисляются бесплатные загрузки?": "When are free downloads added?",
  "Бесплатные загрузки начисляются каждую среду в 3:00 ночи в размере 5 шт.": "Free downloads are added every Wednesday at 3:00 AM: 5 files.",
  "Почему цена отличается от указаннной?": "Why can the final price differ?",
  "Почему цена отличается от указанной?": "Why can the final price differ?",
  "На сайте цены указаны в долларах. Провайдер может списать эквивалент в валюте вашей карты по своему курсу.": "Prices on the website are shown in US dollars. The provider may charge the equivalent in your card's currency using its exchange rate.",
  "Поддерживаемые платформы": "Supported platforms",
  "Почему не работает ссылка?": "Why does a link not work?",
  "Убедись, что ссылка ведёт на конкретный файл, а не на категорию или поисковую выдачу. Нужна прямая ссылка на элемент. Это касается всех платформ: Freepik, Envato Elements и Motion Array.": "Make sure the URL points to a specific asset, not a category or search page. Use a direct asset link from Freepik, Envato Elements, or Motion Array.",
  "Можно добавить поддержку других платформ?": "Can you add more platforms?",
  "Мы планируем расширение! Напиши, какие платформы тебе нужны — учтём в следующем опросе, подписывайся на": "We plan to support more platforms. Tell us which ones you need and follow the",
  "канал": "channel",
  "Хватит платить стокам по $90.": "Stop paying stock sites $90.",
  "Хватит платить": "Stop paying",
  "стокам по $90.": "$90 to stock sites.",
  "Первые 5 файлов — бесплатно. Без карты, без подписки. Только Telegram и пара секунд.": "The first 5 files are free. No card, no subscription. Just Telegram and a few seconds.",
  "Попробовать бесплатно →": "Try for free →",
  "Премиум-стоки одной ссылкой. Без VPN, регистраций и подписок по $90/мес.": "Premium stock files from one link. No VPN, registrations, or $90/month subscriptions.",
  "Сделано на одной зелёной лапке.": "Built with one green paw.",
  "© 2026 FootageHub. Сделано на одной зелёной лапке.": "© 2026 FootageHub. Built with one green paw.",
  "лягушка с кофе": "frog with coffee",
  "Войти через Telegram": "Sign in with Telegram",
  "Войти через": "Sign in with",
  "Никаких паролей и регистраций. Отсканируй QR или открой бота — и ты внутри.": "No passwords or registrations. Scan the QR or open the bot and you are in.",
  "Готовим QR-код…": "Preparing QR code...",
  "Открыть в Telegram": "Open in Telegram",
  "Ждём подтверждения в Telegram:": "Waiting for Telegram confirmation:",
  "⏳ Ждём подтверждения в Telegram:": "⏳ Waiting for Telegram confirmation:",
  "Отсканируй камерой телефона или нажми кнопку выше, затем нажми «Подтвердить вход» в боте.": "Scan it with your phone camera or press the button above, then confirm login in the bot.",
  "Вход подтверждён!": "Login confirmed!",
  "Открываем личный кабинет…": "Opening your dashboard...",
  "Срок действия QR истёк.": "The QR code has expired.",
  "⌛ Срок действия QR истёк.": "⌛ The QR code has expired.",
  "Не удалось создать сессию входа": "Could not start a sign-in session",
  "Что-то пошло не так.": "Something went wrong.",
  "Обновить QR": "Refresh QR",
  "Авторизуясь, ты соглашаешься с": "By signing in, you agree to the",
  "офертой": "offer",
  "и политикой": "and policy",
  "Личный кабинет": "Dashboard",
  "Привет": "Hello",
  "Сменить тариф": "Change plan",
  "Получить файл": "Get file",
  "1 ссылка = 1 файл": "1 link = 1 file",
  "Качаем…": "Downloading...",
  "Поддерживаем:": "Supported:",
  "Остаток": "Remaining",
  "кредитов": "credits",
  "Пополнить баланс на странице оплаты": "Top up on the payment page",
  "Пополни баланс на странице оплаты": "Top up on the payment page",
  "Загрузка…": "Loading...",
  "Не удалось получить файл": "Could not get the file",
  "Введите ссылку на файл Envato, Freepik или Motion Array": "Enter an Envato, Freepik or Motion Array asset link",
  "Не удалось сохранить ссылку. Откройте кабинет и вставьте её там.": "Could not save the link. Open the dashboard and paste it there.",
  "✓ Готово": "Ready",
  "Новости о запуске в Telegram": "Launch news on Telegram",
  "Анонс появится в канале новостей.": "The launch announcement will be posted in our news channel.",
  "Cookie и аналитика": "Cookies and analytics",
  "и информацией о cookie": "and cookie information",
  "Всего скачано": "Total downloads",
  "по подписке": "by subscription",
  "В этом месяце": "This month",
  "Скорость": "Speed",
  "среднее время выдачи": "average delivery time",
  "Бесплатно": "Free",
  "кредитов на счету": "credits on account",
  "История скачиваний": "Download history",
  "Скачиваний пока нет — вставь ссылку выше.": "No downloads yet. Paste a link above.",
  "готов": "ready",
  "Открыть": "Open",
  "Оплата тарифа": "Plan payment",
  "назад в кабинет": "back to dashboard",
  "← назад в кабинет": "← back to dashboard",
  "Списание разовое. Без автопродления. Включается мгновенно после оплаты.": "One-time charge. No auto-renewal. Activated immediately after payment.",
  "Тариф": "Plan",
  "1 · Тариф": "1 · Plan",
  "Способ оплаты": "Payment method",
  "2 · Способ оплаты": "2 · Payment method",
  "Карта": "Card",
  "Крипта": "Crypto",
  "Итого": "Total",
  "Объём": "Volume",
  "К оплате": "To pay",
  "Оплатить": "Pay",
  "Перенаправление…": "Redirecting...",
  "Выберите тариф": "Choose a plan",
  "30 файлов / день": "30 files / day",
  "Безлимит": "Unlimited",
  "Все стоки: Envato, Freepik, Motion Array": "All sources: Envato, Freepik, Motion Array",
  "Доставка в Telegram за ~8 секунд": "Delivery in Telegram in ~8 seconds",
  "Нажимая «Оплатить», ты соглашаешься с офертой. Оплата проходит через защищённый шлюз провайдера.": "By clicking Pay, you agree to the offer. Payment is processed through the provider's secure gateway.",
  "Загрузка тарифов…": "Loading plans...",
  "Не удалось загрузить тарифы": "Could not load plans",
  "Ошибка создания платежа": "Could not create payment",
  "Скачивание медиа": "Media download",
  "Вставьте ссылку с Envato Elements, Freepik или Motion Array": "Paste an Envato Elements, Freepik, or Motion Array link",
  "Ссылка на файл": "File link",
  "Введите ссылку": "Enter a link",
  "Обрабатываем запрос...": "Processing request...",
  "Файл готов к скачиванию": "File is ready to download",
  "Скачать файл": "Download file",
  "Осталось кредитов:": "Credits left:",
  "Назад": "Back",
  "Скоро · в разработке": "Coming soon · in development",
  "AI, который": "AI that",
  "генерит шаблоны.": "generates templates.",
  "Опишешь идею текстом — получишь готовый": "Describe an idea and get a ready",
  "или вектор. Бесплатные правки. Прямо в Telegram.": "or vector. Free revisions. Right in Telegram.",
  "@username в Telegram": "@username on Telegram",
  "Сообщить о запуске": "Notify me at launch",
  "Подписан! Напишем в Telegram, как только включим.": "Subscribed! We'll message you on Telegram as soon as it is live.",
  "Подписалось 4 217 человек · запуск ориентировочно": "4,217 people subscribed · estimated launch",
  "→ \"Минималистичная заставка для тревел-блога,": "→ \"Minimalist intro for a travel blog,",
  "6 секунд, в стиле Wes Anderson\"": "6 seconds, in the style of Wes Anderson\"",
  "генерация · 47%": "generation · 47%",
  "~ 12 сек": "~ 12 sec",
  "✦ работает на свежей лягушке": "✦ powered by a fresh frog",
  "Что будет уметь": "What it will do",
  "Motion-шаблоны": "Motion templates",
  "Генерация .aep / .mogrt из текстового брифа. Импортируешь в After Effects и работаешь дальше.": "Generate .aep / .mogrt files from a text brief. Import them into After Effects and keep working.",
  "Векторы и постеры": "Vectors and posters",
  "AI рисует векторные иллюстрации в нужном стиле. Сразу .ai / .svg, без растровых артефактов.": "AI creates vector illustrations in your chosen style. Ready as .ai / .svg, without raster artifacts.",
  "Бесконечные правки": "Unlimited revisions",
  "«Сделай ярче», «убери логотип», «другой ритм». Чат с AI прямо в Telegram, итераций сколько надо.": "Make it brighter, remove the logo, change the rhythm. Chat with AI in Telegram and iterate as much as needed.",
  "← Вернуться на главную": "← Back to home",
};

const phraseTranslations: [string, string][] = [
  ["Оплатить ", "Pay "],
  ["в месяц ·", "per month ·"],
  ["файлов / месяц", "files / month"],
  ["файлов в каталоге", "files in catalog"],
  ["файлов выдано", "files delivered"],
  ["довольных дизайнеров", "happy designers"],
  ["средняя выдача", "average delivery"],
  ["аптайм бота", "bot uptime"],
  ["только что", "just now"],
  ["мин назад", "min ago"],
  ["ч назад", "h ago"],
  ["дн назад", "d ago"],
  ["Free · бесплатные кредиты", "Free · free credits"],
  ["месяц", "month"],
  ["файлов", "files"],
  ["файл", "file"],
  ["кредитов", "credits"],
  ["кредиты", "credits"],
  ["тех.работы", "maintenance"],
  ["тех. работы", "maintenance"],
];

const originals = new WeakMap<Text, TranslationState>();
const originalAttrs = new WeakMap<Element, Record<string, TranslationState>>();

export function translateText(value: string): string {
  const leading = value.match(/^\s*/)?.[0] ?? "";
  const trailing = value.match(/\s*$/)?.[0] ?? "";
  let core = value.trim();

  if (!core) return value;
  if (exactTranslations[core]) return `${leading}${exactTranslations[core]}${trailing}`;

  for (const [ru, en] of phraseTranslations) {
    core = core.replaceAll(ru, en);
  }

  return `${leading}${core}${trailing}`;
}

function shouldSkip(element: Element | null): boolean {
  if (!element) return false;
  return Boolean(element.closest("script,style,noscript,code,pre,[data-no-translate]"));
}

function detectPreferredLanguage(): Language {
  const browserLanguages = navigator.languages?.length
    ? navigator.languages
    : [navigator.language];
  const primaryLanguage = browserLanguages[0]?.toLowerCase() ?? "";

  return RU_LANGUAGE_PREFIXES.some((prefix) => primaryLanguage.startsWith(prefix))
    ? "ru"
    : "en";
}

function translateNode(root: ParentNode, language: Language) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const textNodes: Text[] = [];
  while (walker.nextNode()) textNodes.push(walker.currentNode as Text);

  for (const node of textNodes) {
    if (shouldSkip(node.parentElement)) continue;
    const current = node.nodeValue ?? "";
    const next = nextTranslation(current, originals.get(node), language === "en" ? translateText : value => value);
    originals.set(node, next);
    if (current !== next.rendered) node.nodeValue = next.rendered;
  }

  const elements = root instanceof Element ? [root, ...Array.from(root.querySelectorAll("*"))] : Array.from(root.querySelectorAll("*"));
  for (const element of elements) {
    if (shouldSkip(element)) continue;
    const attrs = ["placeholder", "title", "aria-label", "alt"];
    const saved = originalAttrs.get(element) ?? {};
    originalAttrs.set(element, saved);
    for (const attr of attrs) {
      const current = element.getAttribute(attr);
      if (current === null) { delete saved[attr]; continue; }
      const next = nextTranslation(current, saved[attr], language === "en" ? translateText : value => value);
      saved[attr] = next;
      if (current !== next.rendered) element.setAttribute(attr, next.rendered);
    }
  }
}

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [language, setLanguageState] = useState<Language>("ru");
  const pathname = usePathname();

  useEffect(() => {
    let saved: string | null = null;
    try { saved = window.localStorage.getItem(STORAGE_KEY); } catch { /* Storage may be unavailable. */ }
    const nextLanguage = pathname === "/en" ? "en" : pathname === "/" ? "ru" : saved === "ru" || saved === "en"
      ? saved
      : detectPreferredLanguage();
    if (pathname === "/" || pathname === "/en") {
      try { window.localStorage.setItem(STORAGE_KEY, nextLanguage); } catch { /* Keep language in memory. */ }
    }
    const frame = window.requestAnimationFrame(() => setLanguageState(nextLanguage));
    return () => window.cancelAnimationFrame(frame);
  }, [pathname]);

  const setLanguage = (next: Language) => {
    try { window.localStorage.setItem(STORAGE_KEY, next); } catch { /* Keep language in memory. */ }
    document.cookie = `${STORAGE_KEY}=${next}; path=/; max-age=31536000; SameSite=Lax`;
    setLanguageState(next);
  };

  const value = useMemo(() => ({ language, setLanguage }), [language]);

  return (
    <LanguageContext.Provider value={value}>
      {children}
      <GlobalTranslator language={language} />
    </LanguageContext.Provider>
  );
}

function GlobalTranslator({ language }: { language: Language }) {
  const translating = useRef(false);

  useEffect(() => {
    const run = () => {
      if (translating.current) return;
      translating.current = true;
      const pageLanguage = document.querySelector<HTMLElement>("[data-page-language]")?.dataset.pageLanguage;
      document.documentElement.lang = pageLanguage === "ru" || pageLanguage === "en"
        ? pageLanguage
        : language;
      translateNode(document.body, language);
      translating.current = false;
    };

    run();
    let frame = 0;
    const observer = new MutationObserver(() => {
      window.cancelAnimationFrame(frame);
      frame = window.requestAnimationFrame(run);
    });
    observer.observe(document.body, { childList: true, subtree: true, characterData: true,
      attributes: true, attributeFilter: ["placeholder", "title", "aria-label", "alt"] });
    return () => { observer.disconnect(); window.cancelAnimationFrame(frame); };
  }, [language]);

  return null;
}

export function useLanguage() {
  const value = useContext(LanguageContext);
  if (!value) throw new Error("useLanguage must be used inside LanguageProvider");
  return value;
}

export function useHomeHref() {
  const { language } = useLanguage();
  const pathname = usePathname();
  return pathname === "/en" || (pathname !== "/" && language === "en") ? "/en" : "/";
}

export function LanguageSwitcher() {
  const { language, setLanguage } = useLanguage();

  return (
    <div
      aria-label="Language"
      data-no-translate
      style={{
        display: "inline-flex",
        padding: 3,
        borderRadius: 999,
        background: "var(--border)",
        border: "1px solid var(--border)",
      }}
    >
      {(["ru", "en"] as const).map((item) => (
        <button
          key={item}
          type="button"
          onClick={() => setLanguage(item)}
          style={{
            minWidth: 34,
            padding: "6px 9px",
            borderRadius: 999,
            fontSize: 12,
            fontWeight: 700,
            background: language === item ? "var(--accent)" : "transparent",
            color: language === item ? "white" : "var(--text-dim)",
            transition: "all 0.15s ease",
          }}
        >
          {item.toUpperCase()}
        </button>
      ))}
    </div>
  );
}
