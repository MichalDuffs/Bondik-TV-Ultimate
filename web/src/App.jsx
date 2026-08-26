import { useState } from "react";
import { BrowserRouter, NavLink, Route, Routes } from "react-router-dom";
import "./App.css";

const navigation = [
  { path: "/", label: "Domů", icon: "🦮" },
  { path: "/search", label: "Search", icon: "🦮🔎" },
  { path: "/playlists", label: "Playlisty", icon: "📺" },
  { path: "/epg", label: "EPG", icon: "🦮📅" },
  { path: "/favorites", label: "Oblíbené", icon: "⭐" },
  { path: "/tools", label: "Nástroje", icon: "🚜" },
  { path: "/statistics", label: "Statistiky", icon: "🤖📊" },
  { path: "/settings", label: "Nastavení", icon: "🤖⚙️" },
];

const themes = {
  ultimate: { name: "Ultimate", mascot: "🦮🚜🤖", className: "theme-ultimate" },
  bondik: { name: "Bondík", mascot: "🦮", className: "theme-bondik" },
  mole: { name: "Krtek", mascot: "🚜", className: "theme-mole" },
  boris: { name: "Boris", mascot: "🤖", className: "theme-boris" },
  minimal: { name: "Minimal", mascot: "📺", className: "theme-minimal" },
};

function HomePage() {
  return (
    <section className="hero">
      <div className="hero-overlay">
        <span className="eyebrow">BONDÍK TV</span>
        <h1>ULTIMATE SEARCH</h1>

        <p>
          Hunter hledá. Gate ověřuje. BAGTOP vybírá.
          <br />
          Ultimate Search ukazuje výsledek lidem.
        </p>

        <NavLink className="primary-button" to="/search">
          🦮🔎 Otevřít Search
        </NavLink>
      </div>
    </section>
  );
}

function SearchPage() {
  const [country, setCountry] = useState("CZ");
  const [category, setCategory] = useState("documentary");
  const [status, setStatus] = useState("stable");

  return (
    <section className="page">
      <div className="page-heading">
        <div className="character">🦮🔎</div>
        <div>
          <span className="eyebrow">ULTIMATE SEARCH</span>
          <h2>Najdi přesně to, co chceš</h2>
        </div>
      </div>

      <div className="filter-grid">
        <label>
          Země
          <select value={country} onChange={(e) => setCountry(e.target.value)}>
            <option value="CZ">🇨🇿 Česko</option>
            <option value="SK">🇸🇰 Slovensko</option>
            <option value="CZ+SK">🇨🇿 + 🇸🇰 CZ / SK</option>
          </select>
        </label>

        <label>
          Kategorie
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          >
            <option value="documentary">🌍 Dokumenty</option>
            <option value="music">🎵 Hudba</option>
            <option value="sport">⚽ Sport</option>
            <option value="news">📰 Zprávy</option>
            <option value="kids">🧸 Děti</option>
          </select>
        </label>

        <label>
          Stav
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="stable">✅ Stable</option>
            <option value="testing">🧪 Testing</option>
            <option value="all">📺 Vše</option>
          </select>
        </label>
      </div>

      <div className="query-preview">
        <span>Aktivní kombinace</span>
        <strong>
          {country} + {category} + {status}
        </strong>
      </div>

      <div className="empty-results">
        <div>🚧</div>
        <h3>Datový motor připojíme jako další krok</h3>
        <p>
          Filtry už jsou připravené pro skutečná data z channels.yaml.
        </p>
      </div>
    </section>
  );
}

function PlaceholderPage({ title, character, text }) {
  return (
    <section className="page placeholder">
      <div className="character big">{character}</div>
      <span className="eyebrow">BONDÍK TV ULTIMATE</span>
      <h2>{title}</h2>
      <p>{text}</p>
    </section>
  );
}

function SettingsPage({ theme, setTheme }) {
  return (
    <section className="page">
      <div className="page-heading">
        <div className="character">🤖⚙️</div>
        <div>
          <span className="eyebrow">NASTAVENÍ</span>
          <h2>Vyber svého průvodce</h2>
        </div>
      </div>

      <div className="theme-grid">
        {Object.entries(themes).map(([key, item]) => (
          <button
            key={key}
            className={`theme-card ${theme === key ? "selected" : ""}`}
            onClick={() => setTheme(key)}
          >
            <span>{item.mascot}</span>
            <strong>{item.name}</strong>
          </button>
        ))}
      </div>

      <p className="support-note">
        💡 Po telefonu stačí říct třeba: „Najdi list s krtkem.“ 🚜
      </p>
    </section>
  );
}

function AppShell() {
  const [theme, setTheme] = useState("ultimate");

  return (
    <div className={`app ${themes[theme].className}`}>
      <aside className="sidebar">
        <div className="brand">
          <span>🦮📺</span>
          <div>
            <strong>BONDÍK TV</strong>
            <small>ULTIMATE</small>
          </div>
        </div>

        <nav>
          {navigation.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === "/"}
              className={({ isActive }) => (isActive ? "active" : "")}
            >
              <span className="nav-icon">{item.icon}</span>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          {themes[theme].mascot}
          <small>{themes[theme].name} theme</small>
        </div>
      </aside>

      <main className="content">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/search" element={<SearchPage />} />

          <Route
            path="/playlists"
            element={
              <PlaceholderPage
                character="📺"
                title="Playlisty"
                text="Vlastní Playlist Builder přijde sem."
              />
            }
          />

          <Route
            path="/epg"
            element={
              <PlaceholderPage
                character="🦮📅"
                title="EPG"
                text="Program stanic a časová osa."
              />
            }
          />

          <Route
            path="/favorites"
            element={
              <PlaceholderPage
                character="⭐"
                title="Oblíbené"
                text="Tvoje uložené stanice."
              />
            }
          />

          <Route
            path="/tools"
            element={
              <PlaceholderPage
                character="🚜"
                title="Nástroje"
                text="Tady bude mít Krtek BAGTOP, testy a diagnostiku."
              />
            }
          />

          <Route
            path="/statistics"
            element={
              <PlaceholderPage
                character="🤖📊"
                title="Statistiky"
                text="Boris bude počítat kvalitu, dostupnost a odezvu."
              />
            }
          />

          <Route
            path="/settings"
            element={<SettingsPage theme={theme} setTheme={setTheme} />}
          />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppShell />
    </BrowserRouter>
  );
}