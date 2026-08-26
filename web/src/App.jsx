import { useEffect, useMemo, useState } from "react";
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
  const [catalog, setCatalog] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [country, setCountry] = useState("all");
  const [category, setCategory] = useState("all");
  const [status, setStatus] = useState("stable");

  const ui = {
    title: "Najdi p\u0159esn\u011b to, co chce\u0161",
    search: "Hledat stanici",
    placeholder: "Nap\u0159. \u00d3\u010dko, sport, POLAR...",
    country: "Zem\u011b",
    allCountries: "\u{1F30D} V\u0161echny zem\u011b",
    czechia: "\u{1F1E8}\u{1F1FF} \u010cesko",
    slovakia: "\u{1F1F8}\u{1F1F0} Slovensko",
    czsk: "\u{1F1E8}\u{1F1FF} + \u{1F1F8}\u{1F1F0} CZ / SK",
    category: "Kategorie",
    allCategories: "\u{1F4FA} V\u0161echny kategorie",
    state: "Stav",
    stable: "\u2705 Stable",
    testing: "\u{1F9EA} Testing",
    all: "\u{1F4FA} V\u0161e",
    combination: "Aktivn\u00ed kombinace",
    loading: "Bond\u00edk na\u010d\u00edt\u00e1 katalog...",
    loadError: "Katalog se nepoda\u0159ilo na\u010d\u00edst",
    results: "v\u00fdsledk\u016f z",
    channels: "kan\u00e1l\u016f",
    noResults:
      "\u017d\u00e1dn\u00e1 stanice t\u00e9to kombinaci neodpov\u00edd\u00e1",
    tryAgain: "Zkus zm\u011bnit zemi, kategorii nebo stav.",
    epg: "\u{1F4C5} EPG",
    noEpg: "\u2796 bez EPG",
    stream: "\u25B6 Stream",
    web: "\u{1F310} Web",
  };

  const categoryLabels = {
    general: "Obecn\u00e9",
    documentary: "Dokumenty",
    music: "Hudba",
    sport: "Sport",
    sports: "Sport",
    news: "Zpr\u00e1vy",
    kids: "D\u011bti",
    movies: "Filmy",
    entertainment: "Z\u00e1bava",
    education: "Vzd\u011bl\u00e1v\u00e1n\u00ed",
    science: "V\u011bda",
    nature: "P\u0159\u00edroda",
    series: "Seri\u00e1ly",
  };

  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}data/channels.json`)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        return response.json();
      })
      .then((data) => {
        setCatalog(data);
        setLoading(false);
      })
      .catch((reason) => {
        setError(String(reason));
        setLoading(false);
      });
  }, []);

  const results = useMemo(() => {
    if (!catalog?.channels) {
      return [];
    }

    const needle = query.trim().toLocaleLowerCase("cs");

    return catalog.channels.filter((channel) => {
      const countryMatch =
        country === "all" ||
        channel.country === country ||
        (country === "CZ+SK" &&
          ["CZ", "SK"].includes(channel.country));

      const categoryMatch =
        category === "all" ||
        channel.category === category;

      const statusMatch =
        status === "all" ||
        channel.status === status;

      const haystack = [
        channel.name,
        channel.id,
        channel.provider,
        channel.category,
        channel.country,
      ]
        .filter(Boolean)
        .join(" ")
        .toLocaleLowerCase("cs");

      const textMatch =
        needle === "" ||
        haystack.includes(needle);

      return (
        countryMatch &&
        categoryMatch &&
        statusMatch &&
        textMatch
      );
    });
  }, [catalog, query, country, category, status]);

  return (
    <section className="page">
      <div className="page-heading">
        <div className="character">
          {"\u{1F415}\u{1F50E}"}
        </div>

        <div>
          <span className="eyebrow">ULTIMATE SEARCH</span>
          <h2>{ui.title}</h2>
        </div>
      </div>

      <label className="text-search">
        {ui.search}

        <input
          type="search"
          placeholder={ui.placeholder}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </label>

      <div className="filter-grid">
        <label>
          {ui.country}

          <select
            value={country}
            onChange={(event) => setCountry(event.target.value)}
          >
            <option value="all">{ui.allCountries}</option>
            <option value="CZ">{ui.czechia}</option>
            <option value="SK">{ui.slovakia}</option>
            <option value="CZ+SK">{ui.czsk}</option>

            {catalog?.countries
              ?.filter((code) => !["CZ", "SK"].includes(code))
              .map((code) => (
                <option key={code} value={code}>
                  {code}
                </option>
              ))}
          </select>
        </label>

        <label>
          {ui.category}

          <select
            value={category}
            onChange={(event) => setCategory(event.target.value)}
          >
            <option value="all">
              {ui.allCategories}
            </option>

            {catalog?.categories?.map((item) => (
              <option key={item} value={item}>
                {categoryLabels[item] ?? item}
              </option>
            ))}
          </select>
        </label>

        <label>
          {ui.state}

          <select
            value={status}
            onChange={(event) => setStatus(event.target.value)}
          >
            <option value="stable">{ui.stable}</option>
            <option value="testing">{ui.testing}</option>
            <option value="all">{ui.all}</option>
          </select>
        </label>
      </div>

      <div className="query-preview">
        <span>{ui.combination}</span>

        <strong>
          {country} + {category} + {status}
          {query ? ` + "${query}"` : ""}
        </strong>
      </div>

      {loading && (
        <div className="empty-results">
          <div>{"\u{1F415}"}</div>
          <h3>{ui.loading}</h3>
        </div>
      )}

      {error && (
        <div className="empty-results">
          <div>{"\u26A0\uFE0F"}</div>
          <h3>{ui.loadError}</h3>
          <p>{error}</p>
        </div>
      )}

      {!loading && !error && (
        <>
          <div className="results-summary">
            <strong>{results.length}</strong>

            <span>
              {ui.results} {catalog.channel_count} {ui.channels}
            </span>
          </div>

          {results.length === 0 ? (
            <div className="empty-results">
              <div>{"\u{1F50E}"}</div>
              <h3>{ui.noResults}</h3>
              <p>{ui.tryAgain}</p>
            </div>
          ) : (
            <div className="results-grid">
              {results.map((channel) => (
                <article
                  className="channel-card"
                  key={channel.id}
                >
                  <div className="channel-card-head">
                    <div>
                      <span className="channel-country">
                        {channel.country}
                      </span>

                      <h3>{channel.name}</h3>
                    </div>

                    <span
                      className={
                        `status-badge status-${channel.status}`
                      }
                    >
                      {channel.status}
                    </span>
                  </div>

                  <div className="channel-meta">
                    <span>
                      {"\u{1F4C2} "}
                      {categoryLabels[channel.category] ??
                        channel.category}
                    </span>

                    <span>
                      {"\u{1F4E1} "}
                      {channel.provider}
                    </span>

                    <span>
                      {"\u{1F39E}\uFE0F "}
                      {channel.stream.quality}
                    </span>

                    <span>
                      {channel.epg.enabled
                        ? ui.epg
                        : ui.noEpg}
                    </span>
                  </div>

                  <div className="channel-actions">
                    <a
                      href={channel.stream.url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {ui.stream}
                    </a>

                    {channel.metadata.website && (
                      <a
                        href={channel.metadata.website}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {ui.web}
                      </a>
                    )}
                  </div>
                </article>
              ))}
            </div>
          )}
        </>
      )}
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