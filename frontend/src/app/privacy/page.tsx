"use client";

import { PageShell } from "@/components/page-shell";
import { useLanguage } from "@/lib/language";

export default function PrivacyPage() {
  const { language } = useLanguage();
  const en = language === "en";
  const sections = en ? [
    ["Essential storage", "FootageHub stores a sign-in cookie for up to 7 days and your language preference in your browser. If you paste a link on the home page, it is temporarily stored in this tab for up to 30 minutes to carry it into the dashboard after sign-in."],
    ["Optional analytics", "PostHog and optional Google Analytics measure visits and selected actions only after you accept visit statistics. PostHog records interactions on the public home page only after you accept recordings. Text is masked in PostHog. The site does not enable advertising consent."],
    ["Your choice", "You can accept or reject optional analytics separately. Your choice is stored in your browser for 180 days. Use the cookie button to reopen preferences and change or withdraw your choice. Sign-in, downloads and payment do not require optional analytics."],
    ["Information sent to analytics", "The site's custom analytics events use page names, plan identifiers, provider names and timing information. They do not include pasted asset links, Telegram usernames, sign-in tokens or payment details. Analytics providers also process technical connection information when their scripts are enabled."],
    ["Questions", "Contact FootageHub support for questions about your account or data. The service terms are available in the public offer linked below."],
  ] : [
    ["Необходимое хранение", "FootageHub сохраняет cookie входа на срок до 7 дней и выбор языка в браузере. Ссылка, вставленная на главной, временно хранится в текущей вкладке до 30 минут, чтобы перенести её в кабинет после входа."],
    ["Необязательная аналитика", "PostHog и необязательный Google Analytics собирают статистику посещений и отдельных действий только после согласия на статистику. PostHog записывает взаимодействия только на публичной главной странице после согласия на записи. Текст в PostHog скрывается. Сайт не включает согласие на рекламное отслеживание."],
    ["Ваш выбор", "Можно отдельно принять или отклонить необязательную аналитику. Выбор сохраняется в браузере на 180 дней. Кнопка cookie позволяет снова открыть настройки, изменить или отозвать согласие. Вход, скачивание и оплата не требуют необязательной аналитики."],
    ["Данные аналитики", "События, настроенные на сайте, содержат названия страниц, идентификаторы тарифов, названия провайдеров и время выполнения. Они не содержат вставленные ссылки на файлы, имена Telegram, токены входа или платёжные реквизиты. При включённых скриптах провайдеры аналитики также обрабатывают технические сведения о соединении."],
    ["Вопросы", "По вопросам об аккаунте и данных обратитесь в поддержку FootageHub. Условия использования сервиса доступны в публичной оферте по ссылке ниже."],
  ];

  return <PageShell><main data-no-translate className="container-page" style={{ maxWidth: 820, paddingTop: 40, paddingBottom: 80 }}>
    <h1 style={{ fontSize: 30, marginBottom: 32 }}>{en ? "Cookies and analytics" : "Cookie и аналитика"}</h1>
    {sections.map(([title, body]) => <section key={title} style={{ marginBottom: 28 }}>
      <h2 style={{ fontSize: 20, marginBottom: 10 }}>{title}</h2>
      <p style={{ color: "var(--text-dim)", lineHeight: 1.7 }}>{body}</p>
    </section>)}
    <div style={{ display: "flex", flexWrap: "wrap", gap: 20, textDecoration: "underline" }}>
      <a href="https://t.me/FootageHub_support" target="_blank" rel="noopener noreferrer">{en ? "Support" : "Поддержка"}</a>
      <a href="/assets/public_offer_footagehub.pdf" target="_blank" rel="noopener noreferrer">{en ? "Public offer" : "Публичная оферта"}</a>
      <a href="https://policies.google.com/privacy" target="_blank" rel="noopener noreferrer">Google</a>
      <a href="https://posthog.com/privacy" target="_blank" rel="noopener noreferrer">PostHog</a>
    </div>
  </main></PageShell>;
}
