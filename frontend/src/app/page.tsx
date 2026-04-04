import Link from "next/link";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Header */}
      <header className="border-b border-gray-800 px-6 py-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="text-xl font-bold text-blue-400">FootageHub</div>
          <div className="flex gap-4">
            <Link
              href="/auth"
              className="px-4 py-2 text-sm text-gray-300 hover:text-white transition"
            >
              Войти
            </Link>
            <Link
              href="/auth"
              className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 rounded-lg transition"
            >
              Начать бесплатно
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="px-6 py-24 text-center">
        <div className="max-w-3xl mx-auto">
          <h1 className="text-5xl font-bold mb-6 leading-tight">
            Скачивай медиа с{" "}
            <span className="text-blue-400">Envato, Freepik</span> и{" "}
            <span className="text-purple-400">Motion Array</span>
          </h1>
          <p className="text-xl text-gray-400 mb-10">
            Профессиональные шаблоны, стоковое видео и AI-генерация контента — всё в одном месте.
            Регистрация за 30 секунд по номеру телефона.
          </p>
          <Link
            href="/auth"
            className="inline-block px-8 py-4 bg-blue-600 hover:bg-blue-700 rounded-xl text-lg font-semibold transition"
          >
            Попробовать бесплатно
          </Link>
        </div>
      </section>

      {/* Features */}
      <section className="px-6 py-16 bg-gray-900">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-12">Что умеет FootageHub</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {[
              {
                title: "Envato Elements",
                desc: "Шаблоны After Effects, Premiere Pro, 3D, стоковое видео и музыка",
                icon: "🎬",
              },
              {
                title: "Freepik",
                desc: "Векторы, фотомокапы, иллюстрации, PSD-файлы и иконки",
                icon: "🎨",
              },
              {
                title: "Motion Array",
                desc: "Моушн-графика, плагины, LUT-пресеты и шаблоны монтажа",
                icon: "🎥",
              },
              {
                title: "AI Генерация",
                desc: "Изображения и видео от Google, Kling 2.6 и VEO 3.1 по текстовому запросу",
                icon: "🤖",
              },
            ].map((f) => (
              <div key={f.title} className="bg-gray-800 rounded-xl p-6">
                <div className="text-4xl mb-4">{f.icon}</div>
                <h3 className="text-lg font-semibold mb-2">{f.title}</h3>
                <p className="text-gray-400 text-sm">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section className="px-6 py-16">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-3xl font-bold mb-4">Простые тарифы</h2>
          <p className="text-gray-400 mb-10">Начни бесплатно, масштабируй по мере роста</p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[
              { name: "Lite", price: "от $9.99", desc: "50 скачиваний в месяц", popular: false },
              { name: "Standard", price: "от $24.99", desc: "150 скачиваний в месяц", popular: true },
              { name: "Pro", price: "от $49.99", desc: "400 скачиваний в месяц", popular: false },
            ].map((plan) => (
              <div
                key={plan.name}
                className={`rounded-xl p-6 border ${
                  plan.popular ? "border-blue-500 bg-blue-950" : "border-gray-700 bg-gray-900"
                }`}
              >
                {plan.popular && (
                  <div className="text-xs text-blue-400 font-semibold mb-2">ПОПУЛЯРНЫЙ</div>
                )}
                <div className="text-2xl font-bold mb-1">{plan.name}</div>
                <div className="text-xl text-blue-400 font-semibold mb-3">{plan.price}</div>
                <div className="text-gray-400 text-sm mb-4">{plan.desc}</div>
                <Link
                  href="/auth"
                  className="block w-full py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm font-medium text-center transition"
                >
                  Выбрать
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="px-6 py-16 bg-blue-900/30 text-center">
        <h2 className="text-3xl font-bold mb-4">Готов начать?</h2>
        <p className="text-gray-400 mb-8">
          Регистрация занимает 30 секунд. Никакого email, только номер телефона.
        </p>
        <Link
          href="/auth"
          className="inline-block px-8 py-4 bg-blue-600 hover:bg-blue-700 rounded-xl text-lg font-semibold transition"
        >
          Зарегистрироваться
        </Link>
      </section>

      <footer className="px-6 py-8 border-t border-gray-800 text-center text-gray-500 text-sm">
        © 2026 FootageHub · envato-freepik-download.store
      </footer>
    </div>
  );
}
