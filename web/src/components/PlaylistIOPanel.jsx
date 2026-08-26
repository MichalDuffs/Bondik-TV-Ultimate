import {
  useRef,
  useState,
} from "react";

import {
  createPlaylistFile,
  downloadPlaylistFile,
  loadPlaylistUrl,
  readPlaylistFile,
  savePlaylistFile,
  sharePlaylistFile,
  supportsFileShare,
  supportsSaveAs,
} from "../lib/playlistInterop";

export default function PlaylistIOPanel({
  playlistName,
  selectedChannels,
  onImport,
}) {
  const fileInputRef = useRef(null);

  const [format, setFormat] =
    useState("m3u");

  const [sourceUrl, setSourceUrl] =
    useState("");

  const [pendingImport, setPendingImport] =
    useState(null);

  const [busy, setBusy] =
    useState(false);

  const [message, setMessage] =
    useState("");

  const canExport =
    selectedChannels.length > 0;

  async function handleFileChange(event) {
    const file =
      event.target.files?.[0];

    event.target.value = "";

    if (!file) {
      return;
    }

    setBusy(true);
    setMessage("");

    try {
      const result =
        await readPlaylistFile(file);

      setPendingImport(result);

      setMessage(
        `Nalezeno ${result.channels.length} stanic.`,
      );
    } catch (error) {
      setPendingImport(null);

      setMessage(
        String(
          error?.message || error,
        ),
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleUrlLoad() {
    if (!sourceUrl.trim()) {
      return;
    }

    setBusy(true);
    setMessage("");

    try {
      const result =
        await loadPlaylistUrl(
          sourceUrl,
        );

      setPendingImport(result);

      setMessage(
        `Nalezeno ${result.channels.length} stanic.`,
      );
    } catch (error) {
      setPendingImport(null);

      setMessage(
        String(
          error?.message || error,
        ),
      );
    } finally {
      setBusy(false);
    }
  }

  function applyImport(mode) {
    if (!pendingImport) {
      return;
    }

    const result =
      onImport(
        pendingImport,
        mode,
      );

    if (result?.ok === false) {
      setMessage(result.message);
      return;
    }

    setMessage(
      result?.message ||
      "Import hotov.",
    );

    setPendingImport(null);
  }

  function makeFile() {
    return createPlaylistFile({
      format,
      playlistName,
      channels: selectedChannels,
    });
  }

  async function handleSaveAs() {
    if (!canExport) {
      return;
    }

    setMessage("");

    try {
      const result =
        await savePlaylistFile(
          makeFile(),
        );

      setMessage(
        result.method === "picker"
          ? "Playlist ulozen."
          : "Systemovy vyber umisteni neni dostupny. Playlist byl stazen do vychozi slozky.",
      );
    } catch (error) {
      if (
        error?.name === "AbortError"
      ) {
        return;
      }

      setMessage(
        String(
          error?.message || error,
        ),
      );
    }
  }

  async function handleShare() {
    if (!canExport) {
      return;
    }

    setMessage("");

    try {
      const shared =
        await sharePlaylistFile(
          makeFile(),
        );

      setMessage(
        shared
          ? "Systemove sdileni otevreno."
          : "Toto zarizeni nebo browser nepodporuje sdileni souboru.",
      );
    } catch (error) {
      if (
        error?.name === "AbortError"
      ) {
        return;
      }

      setMessage(
        String(
          error?.message || error,
        ),
      );
    }
  }

  function handleDownload() {
    if (!canExport) {
      return;
    }

    downloadPlaylistFile(
      makeFile(),
    );

    setMessage(
      "Playlist byl predan browseru ke stazeni.",
    );
  }

  return (
    <section className="playlist-io-panel">
      <div className="playlist-io-heading">
        <div>
          <span className="eyebrow">
            PLAYLIST INTEROP & SHARING V2.1
          </span>

          <h3>
            {"\u{1F4C2} Otevrit, ulozit a sdilet"}
          </h3>
        </div>

        <span className="playlist-io-formats">
          M3U / M3U8 / CSV / URL
        </span>
      </div>

      <div className="playlist-io-import-grid">
        <div className="playlist-io-card">
          <strong>
            {"\u{1F4C2} Soubor / USB / uloziste"}
          </strong>

          <p>
            {
              "Vyber playlist z interniho uloziste, Downloads nebo USB, pokud ho system zobrazi."
            }
          </p>

          <input
            ref={fileInputRef}
            className="playlist-file-input"
            type="file"
            accept=".m3u,.m3u8,.csv,text/csv,audio/x-mpegurl,application/vnd.apple.mpegurl,text/plain"
            onChange={handleFileChange}
          />

          <button
            type="button"
            disabled={busy}
            onClick={() =>
              fileInputRef.current?.click()
            }
          >
            {"\u{1F4C2} Otevrit playlist"}
          </button>
        </div>

        <div className="playlist-io-card">
          <strong>
            {"\u{1F517} Playlist z URL"}
          </strong>

          <p>
            {
              "M3U, M3U8, CSV nebo primy HLS stream."
            }
          </p>

          <div className="playlist-url-row">
            <input
              type="url"
              placeholder="https://example.com/playlist.m3u"
              value={sourceUrl}
              onChange={(event) =>
                setSourceUrl(
                  event.target.value,
                )
              }
              onKeyDown={(event) => {
                if (
                  event.key === "Enter"
                ) {
                  handleUrlLoad();
                }
              }}
            />

            <button
              type="button"
              disabled={
                busy ||
                !sourceUrl.trim()
              }
              onClick={handleUrlLoad}
            >
              {"Nacist"}
            </button>
          </div>
        </div>
      </div>

      {pendingImport && (
        <div className="playlist-import-preview">
          <div>
            <strong>
              {"\u{1F4E6} "}
              {pendingImport.name}
            </strong>

            <span>
              {pendingImport.channels.length}
              {" stanic \u2022 "}
              {pendingImport.format.toUpperCase()}
            </span>
          </div>

          {pendingImport.warnings?.map(
            (warning) => (
              <p
                key={warning}
                className="playlist-io-warning"
              >
                {"\u26A0\uFE0F "}
                {warning}
              </p>
            ),
          )}

          <div className="playlist-import-actions">
            <button
              type="button"
              onClick={() =>
                applyImport("new")
              }
            >
              {"\u2795 Jako novy playlist"}
            </button>

            <button
              type="button"
              onClick={() =>
                applyImport("merge")
              }
            >
              {"\u{1F4E5} Do aktivniho"}
            </button>

            <button
              type="button"
              className="secondary"
              onClick={() =>
                setPendingImport(null)
              }
            >
              {"Zrusit"}
            </button>
          </div>
        </div>
      )}

      <div className="playlist-export-toolbar">
        <label>
          {"Format"}

          <select
            value={format}
            onChange={(event) =>
              setFormat(
                event.target.value,
              )
            }
          >
            <option value="m3u">
              M3U
            </option>

            <option value="m3u8">
              M3U8
            </option>

            <option value="csv">
              CSV
            </option>
          </select>
        </label>

        <div className="playlist-export-actions">
          <button
            type="button"
            disabled={!canExport}
            onClick={handleSaveAs}
            title={
              supportsSaveAs()
                ? "Vybrat umisteni"
                : "Fallback na Downloads"
            }
          >
            {"\u{1F4BE} Ulozit jako..."}
          </button>

          <button
            type="button"
            disabled={
              !canExport ||
              !supportsFileShare()
            }
            onClick={handleShare}
          >
            {"\u{1F4E4} Sdilet"}
          </button>

          <button
            type="button"
            disabled={!canExport}
            onClick={handleDownload}
          >
            {"\u2B07\uFE0F Stahnout"}
          </button>
        </div>
      </div>

      {message && (
        <div
          className="playlist-io-message"
          role="status"
        >
          {busy
            ? "\u{1F415} Pracuji..."
            : message}
        </div>
      )}
    </section>
  );
}
