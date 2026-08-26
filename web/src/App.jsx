import { useEffect, useMemo, useState } from "react";
import { BrowserRouter, NavLink, Route, Routes } from "react-router-dom";
import LivePreview from "./components/LivePreview";
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


const PLAYLIST_STORAGE_KEY = "bondik-tv-playlist-v2";
const LEGACY_PLAYLIST_STORAGE_KEY = "bondik-tv-playlist-v1";

const EMPTY_PLAYLIST_STATE = {
  ids: [],
  notes: {},
  name: "Bondik TV Custom",
  note: "",
};

function normalizePlaylistState(value) {
  if (Array.isArray(value)) {
    return {
      ...EMPTY_PLAYLIST_STATE,
      ids: [
        ...new Set(
          value.filter((id) => typeof id === "string"),
        ),
      ],
    };
  }

  if (!value || typeof value !== "object") {
    return { ...EMPTY_PLAYLIST_STATE };
  }

  const ids = [
    ...new Set(
      Array.isArray(value.ids)
        ? value.ids.filter((id) => typeof id === "string")
        : [],
    ),
  ];

  const notes =
    value.notes && typeof value.notes === "object"
      ? Object.fromEntries(
          Object.entries(value.notes).filter(
            ([id, note]) =>
              ids.includes(id) &&
              typeof note === "string",
          ),
        )
      : {};

  return {
    ids,
    notes,
    name:
      typeof value.name === "string"
        ? value.name
        : EMPTY_PLAYLIST_STATE.name,
    note:
      typeof value.note === "string"
        ? value.note
        : "",
  };
}

function loadStoredPlaylistState() {
  try {
    const current =
      window.localStorage.getItem(PLAYLIST_STORAGE_KEY);

    if (current) {
      return normalizePlaylistState(JSON.parse(current));
    }

    const legacy =
      window.localStorage.getItem(
        LEGACY_PLAYLIST_STORAGE_KEY,
      );

    if (legacy) {
      return normalizePlaylistState(JSON.parse(legacy));
    }
  } catch {
    // Ignore invalid or unavailable browser storage.
  }

  return { ...EMPTY_PLAYLIST_STATE };
}

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

function SearchPage({ playlistIds, setPlaylistIds }) {
  const [catalog, setCatalog] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [activePreviewId, setActivePreviewId] =
    useState(null);

  const [countries, setCountries] = useState([]);
  const [categories, setCategories] = useState([]);
  const [statuses, setStatuses] = useState(["stable"]);

  const ui = {
    title: "Najdi p\u0159esn\u011b to, co chce\u0161",
    search: "Hledat stanici",
    placeholder: "Nap\u0159. \u00d3\u010dko, sport, POLAR...",
    countries: "Zem\u011b",
    categories: "Kategorie",
    statuses: "Stav",
    combination: "Aktivn\u00ed kombinace",
    loading: "Bond\u00edk na\u010d\u00edt\u00e1 katalog...",
    loadError: "Katalog se nepoda\u0159ilo na\u010d\u00edst",
    results: "v\u00fdsledk\u016f z",
    channels: "kan\u00e1l\u016f",
    clear: "Vy\u010distit filtry",
    noResults:
      "\u017d\u00e1dn\u00e1 stanice t\u00e9to kombinaci neodpov\u00edd\u00e1",
    tryAgain: "Zkus zm\u011bnit kombinaci filtr\u016f.",
    epg: "\u{1F4C5} EPG",
    noEpg: "\u2796 bez EPG",
    stream: "\u25B6 Stream",
    web: "\u{1F310} Web",
    addResults: "P\u0159idat v\u00fdsledky",
    openPlaylist: "Otev\u0159\u00edt playlist",
    add: "Do playlistu",
    added: "V playlistu",
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

  const countryLabels = {
    CZ: "\u{1F1E8}\u{1F1FF} CZ",
    SK: "\u{1F1F8}\u{1F1F0} SK",
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

  useEffect(() => {
    function handlePreviewBack(event) {
      if (!activePreviewId) {
        return;
      }

      const target = event.target;
      const tagName = target?.tagName;

      if (
        tagName === "INPUT" ||
        tagName === "TEXTAREA"
      ) {
        return;
      }

      const backKeys = new Set([
        "Escape",
        "BrowserBack",
        "GoBack",
        "Back",
        "Backspace",
      ]);

      if (
        backKeys.has(event.key) ||
        event.keyCode === 4 ||
        event.keyCode === 461
      ) {
        event.preventDefault();
        setActivePreviewId(null);
      }
    }

    window.addEventListener(
      "keydown",
      handlePreviewBack,
    );

    return () => {
      window.removeEventListener(
        "keydown",
        handlePreviewBack,
      );
    };
  }, [activePreviewId]);

  function togglePreview(channelId) {
    setActivePreviewId((current) =>
      current === channelId
        ? null
        : channelId,
    );
  }

  function toggleSelection(value, setter) {
    setter((current) =>
      current.includes(value)
        ? current.filter((item) => item !== value)
        : [...current, value],
    );
  }

  function clearFilters() {
    setQuery("");
    setCountries([]);
    setCategories([]);
    setStatuses(["stable"]);
  }

  const results = useMemo(() => {
    if (!catalog?.channels) {
      return [];
    }

    const needle = query.trim().toLocaleLowerCase("cs");

    return catalog.channels.filter((channel) => {
      const countryMatch =
        countries.length === 0 ||
        countries.includes(channel.country);

      const categoryMatch =
        categories.length === 0 ||
        categories.includes(channel.category);

      const statusMatch =
        statuses.length === 0 ||
        statuses.includes(channel.status);

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
  }, [catalog, query, countries, categories, statuses]);

  function togglePlaylistChannel(channelId) {
    setPlaylistIds((current) =>
      current.includes(channelId)
        ? current.filter((id) => id !== channelId)
        : [...current, channelId],
    );
  }

  function addVisibleResults() {
    setPlaylistIds((current) => [
      ...new Set([
        ...current,
        ...results.map((channel) => channel.id),
      ]),
    ]);
  }

  const countryQuery =
    countries.length > 0
      ? `(${countries.join(" OR ")})`
      : "ALL";

  const categoryQuery =
    categories.length > 0
      ? `(${categories.join(" OR ")})`
      : "ALL";

  const statusQuery =
    statuses.length > 0
      ? `(${statuses.join(" OR ")})`
      : "ALL";

  return (
    <section className="page">
      <div className="page-heading">
        <div className="character">
          {"\u{1F415}\u{1F50E}"}
        </div>

        <div>
          <span className="eyebrow">ULTIMATE SEARCH V2</span>
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

      <div className="multi-filter-grid">
        <section className="filter-section">
          <strong>{ui.countries}</strong>

          <div className="filter-chips">
            {catalog?.countries?.map((country) => {
              const selected = countries.includes(country);

              return (
                <button
                  key={country}
                  type="button"
                  className={`filter-chip ${selected ? "selected" : ""}`}
                  aria-pressed={selected}
                  onClick={() =>
                    toggleSelection(country, setCountries)
                  }
                >
                  {countryLabels[country] ?? country}
                </button>
              );
            })}
          </div>
        </section>

        <section className="filter-section">
          <strong>{ui.categories}</strong>

          <div className="filter-chips">
            {catalog?.categories?.map((category) => {
              const selected = categories.includes(category);

              return (
                <button
                  key={category}
                  type="button"
                  className={`filter-chip ${selected ? "selected" : ""}`}
                  aria-pressed={selected}
                  onClick={() =>
                    toggleSelection(category, setCategories)
                  }
                >
                  {categoryLabels[category] ?? category}
                </button>
              );
            })}
          </div>
        </section>

        <section className="filter-section">
          <strong>{ui.statuses}</strong>

          <div className="filter-chips">
            {catalog?.statuses?.map((status) => {
              const selected = statuses.includes(status);

              return (
                <button
                  key={status}
                  type="button"
                  className={`filter-chip ${selected ? "selected" : ""}`}
                  aria-pressed={selected}
                  onClick={() =>
                    toggleSelection(status, setStatuses)
                  }
                >
                  {status === "stable"
                    ? "\u2705 Stable"
                    : status === "testing"
                      ? "\u{1F9EA} Testing"
                      : status}
                </button>
              );
            })}
          </div>
        </section>
      </div>

      <div className="filter-toolbar">
        <div className="query-preview multi-query">
          <span>{ui.combination}</span>

          <strong>
            {countryQuery}
            {" AND "}
            {categoryQuery}
            {" AND "}
            {statusQuery}
            {query ? ` AND "${query}"` : ""}
          </strong>
        </div>

        <button
          type="button"
          className="clear-filters"
          onClick={clearFilters}
        >
          {"\u{1F9F9} "}
          {ui.clear}
        </button>
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

          <div className="playlist-selection-bar">
            <div>
              <strong>{playlistIds.length}</strong>
              <span> {"\u{1F4FA}"} playlist</span>
            </div>

            <div className="playlist-selection-actions">
              <button
                type="button"
                onClick={addVisibleResults}
                disabled={results.length === 0}
              >
                {"\u2795 "}
                {ui.addResults}
              </button>

              <NavLink to="/playlists">
                {ui.openPlaylist} {"\u2192"}
              </NavLink>
            </div>
          </div>

          {results.length === 0 ? (
            <div className="empty-results">
              <div>{"\u{1F50E}"}</div>
              <h3>{ui.noResults}</h3>
              <p>{ui.tryAgain}</p>
            </div>
          ) : (
            <div className="results-grid">
              {results.map((channel) => {
                const inPlaylist = playlistIds.includes(channel.id);

                return (
                  <article
                    className={`channel-card ${inPlaylist ? "in-playlist" : ""}`}
                    key={channel.id}
                  >
                    <LivePreview
                      channel={channel}
                      active={
                        activePreviewId === channel.id
                      }
                      onToggle={() =>
                        togglePreview(channel.id)
                      }
                    />

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
                      <button
                        type="button"
                        className={`playlist-toggle ${inPlaylist ? "selected" : ""}`}
                        onClick={() =>
                          togglePlaylistChannel(channel.id)
                        }
                      >
                        {inPlaylist
                          ? `\u2713 ${ui.added}`
                          : `\u2795 ${ui.add}`}
                      </button>

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
                );
              })}
            </div>
          )}
        </>
      )}
    </section>
  );
}

function PlaylistPage({
  playlistState,
  setPlaylistState,
}) {
  const [catalog, setCatalog] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const {
    ids: playlistIds,
    notes: channelNotes,
    name: playlistName,
    note: playlistNote,
  } = playlistState;

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

  const selectedChannels = useMemo(() => {
    if (!catalog?.channels) {
      return [];
    }

    const channelsById = new Map(
      catalog.channels.map((channel) => [
        channel.id,
        channel,
      ]),
    );

    return playlistIds
      .map((id) => channelsById.get(id))
      .filter(Boolean);
  }, [catalog, playlistIds]);

  function updatePlaylistField(field, value) {
    setPlaylistState((current) => ({
      ...current,
      [field]: value,
    }));
  }

  function updateChannelNote(channelId, value) {
    setPlaylistState((current) => {
      const notes = { ...current.notes };

      if (value === "") {
        delete notes[channelId];
      } else {
        notes[channelId] = value;
      }

      return {
        ...current,
        notes,
      };
    });
  }

  function moveChannel(channelId, offset) {
    setPlaylistState((current) => {
      const ids = [...current.ids];
      const index = ids.indexOf(channelId);

      if (index === -1) {
        return current;
      }

      const target = index + offset;

      if (target < 0 || target >= ids.length) {
        return current;
      }

      [ids[index], ids[target]] = [
        ids[target],
        ids[index],
      ];

      return {
        ...current,
        ids,
      };
    });
  }

  function removeChannel(channelId) {
    setPlaylistState((current) => {
      const notes = { ...current.notes };
      delete notes[channelId];

      return {
        ...current,
        ids: current.ids.filter(
          (id) => id !== channelId,
        ),
        notes,
      };
    });
  }

  function clearPlaylist() {
    setPlaylistState((current) => ({
      ...current,
      ids: [],
      notes: {},
    }));
  }

  function escapeAttribute(value) {
    return String(value ?? "").replaceAll('"', "'");
  }

  function downloadPlaylist() {
    if (selectedChannels.length === 0) {
      return;
    }

    const lines = ["#EXTM3U"];

    selectedChannels.forEach((channel) => {
      const name = String(channel.name ?? "")
        .replace(/[\r\n]+/g, " ")
        .trim();

      const tvgId = escapeAttribute(channel.epg?.id);
      const logo = escapeAttribute(
        channel.logo?.url ?? "",
      );
      const group = escapeAttribute(
        channel.category,
      );

      lines.push(
        `#EXTINF:-1 tvg-id="${tvgId}" tvg-name="${escapeAttribute(name)}" tvg-logo="${logo}" group-title="${group}",${name}`,
      );
      lines.push(channel.stream.url);
    });

    const safeFileName = (
      playlistName.trim() ||
      "Bondik-TV-Custom"
    )
      .replace(/[<>:"/\\|?*]/g, "-")
      .split("")
      .map((character) =>
        character.charCodeAt(0) < 32
          ? "-"
          : character,
      )
      .join("")
      .replace(/\s+/g, "-")
      .replace(/-+/g, "-");

    const blob = new Blob(
      ["\uFEFF", `${lines.join("\n")}\n`],
      {
        type: "audio/x-mpegurl;charset=utf-8",
      },
    );

    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");

    link.href = url;
    link.download = `${safeFileName}.m3u`;

    document.body.appendChild(link);
    link.click();
    link.remove();

    URL.revokeObjectURL(url);
  }

  return (
    <section className="page">
      <div className="page-heading">
        <div className="character">
          {"\u{1F4FA}\u{1F4DD}"}
        </div>

        <div>
          <span className="eyebrow">
            PLAYLIST BUILDER V1.1
          </span>
          <h2>
            {"Vlastn\u00ed playlist"}
          </h2>
        </div>
      </div>

      <div className="playlist-builder-head">
        <label>
          {"N\u00e1zev playlistu"}

          <input
            type="text"
            value={playlistName}
            onChange={(event) =>
              updatePlaylistField(
                "name",
                event.target.value,
              )
            }
          />
        </label>

        <div className="playlist-builder-summary">
          <strong>{selectedChannels.length}</strong>
          <span>
            {" vybran\u00fdch stanic"}
          </span>
        </div>
      </div>

      <label className="playlist-builder-note">
        {"\u{1F4DD} Pozn\u00e1mka k playlistu"}

        <textarea
          rows="3"
          placeholder={
            "Nap\u0159. TV u babi\u010dky, CZ/SK hudba..."
          }
          value={playlistNote}
          onChange={(event) =>
            updatePlaylistField(
              "note",
              event.target.value,
            )
          }
        />
      </label>

      <p className="playlist-note-hint">
        {
          "Pozn\u00e1mky se ukl\u00e1daj\u00ed v prohl\u00ed\u017ee\u010di. Do .m3u se zat\u00edm nevkl\u00e1daj\u00ed."
        }
      </p>

      <div className="playlist-builder-actions">
        <NavLink to="/search">
          {"\u2190 Zp\u011bt do Search"}
        </NavLink>

        <button
          type="button"
          className="playlist-download"
          disabled={selectedChannels.length === 0}
          onClick={downloadPlaylist}
        >
          {"\u2B07\uFE0F St\u00e1hnout .m3u"}
        </button>

        <button
          type="button"
          className="playlist-clear"
          disabled={selectedChannels.length === 0}
          onClick={clearPlaylist}
        >
          {
            "\u{1F9F9} Vy\u010distit stanice"
          }
        </button>
      </div>

      {loading && (
        <div className="empty-results">
          <div>{"\u{1F415}"}</div>
          <h3>
            {"Na\u010d\u00edt\u00e1m playlist..."}
          </h3>
        </div>
      )}

      {error && (
        <div className="empty-results">
          <div>{"\u26A0\uFE0F"}</div>
          <h3>
            {
              "Katalog se nepoda\u0159ilo na\u010d\u00edst"
            }
          </h3>
          <p>{error}</p>
        </div>
      )}

      {!loading &&
        !error &&
        selectedChannels.length === 0 && (
          <div className="empty-results">
            <div>{"\u{1F4FA}"}</div>
            <h3>
              {
                "Playlist je zat\u00edm pr\u00e1zdn\u00fd"
              }
            </h3>
            <p>
              {
                "Vyber stanice v Ultimate Search a p\u0159idej je sem."
              }
            </p>
          </div>
        )}

      {!loading &&
        !error &&
        selectedChannels.length > 0 && (
          <div className="playlist-channel-list">
            {selectedChannels.map(
              (channel, index) => (
                <article
                  className="playlist-channel-row"
                  key={channel.id}
                >
                  <span className="playlist-position">
                    {index + 1}
                  </span>

                  <div className="playlist-channel-info">
                    <strong>{channel.name}</strong>

                    <span>
                      {channel.country}
                      {" \u2022 "}
                      {channel.category}
                      {" \u2022 "}
                      {channel.status}
                    </span>

                    <label className="playlist-channel-note-field">
                      <span>
                        {"\u{1F4DD} Pozn\u00e1mka"}
                      </span>

                      <input
                        type="text"
                        placeholder={
                          "Voliteln\u00e1 pozn\u00e1mka..."
                        }
                        value={
                          channelNotes[channel.id] ?? ""
                        }
                        onChange={(event) =>
                          updateChannelNote(
                            channel.id,
                            event.target.value,
                          )
                        }
                      />
                    </label>
                  </div>

                  <div className="playlist-channel-controls">
                    <button
                      type="button"
                      disabled={index === 0}
                      title="Posunout nahoru"
                      onClick={() =>
                        moveChannel(channel.id, -1)
                      }
                    >
                      {"\u2191"}
                    </button>

                    <button
                      type="button"
                      disabled={
                        index ===
                        selectedChannels.length - 1
                      }
                      title="Posunout dolu"
                      onClick={() =>
                        moveChannel(channel.id, 1)
                      }
                    >
                      {"\u2193"}
                    </button>

                    <button
                      type="button"
                      className="playlist-remove"
                      title="Odebrat"
                      onClick={() =>
                        removeChannel(channel.id)
                      }
                    >
                      {"\u2715"}
                    </button>
                  </div>
                </article>
              ),
            )}
          </div>
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
  const [playlistState, setPlaylistState] =
    useState(loadStoredPlaylistState);

  const playlistIds = playlistState.ids;

  function setPlaylistIds(update) {
    setPlaylistState((current) => {
      const nextValue =
        typeof update === "function"
          ? update(current.ids)
          : update;

      if (!Array.isArray(nextValue)) {
        return current;
      }

      const ids = [
        ...new Set(
          nextValue.filter(
            (id) => typeof id === "string",
          ),
        ),
      ];

      const notes = Object.fromEntries(
        Object.entries(current.notes).filter(
          ([id]) => ids.includes(id),
        ),
      );

      return {
        ...current,
        ids,
        notes,
      };
    });
  }

  useEffect(() => {
    try {
      window.localStorage.setItem(
        PLAYLIST_STORAGE_KEY,
        JSON.stringify(playlistState),
      );
    } catch {
      // Storage can be unavailable in restricted browser contexts.
    }
  }, [playlistState]);

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
          <Route
            path="/search"
            element={
              <SearchPage
                playlistIds={playlistIds}
                setPlaylistIds={setPlaylistIds}
              />
            }
          />
          <Route
            path="/playlists"
            element={
              <PlaylistPage
                playlistState={playlistState}
                setPlaylistState={setPlaylistState}
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