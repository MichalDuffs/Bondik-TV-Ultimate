import {
  useEffect,
  useRef,
  useState,
} from "react";

const PREVIEW_TIMEOUT_MS = 15000;

function isHlsStream(format, url) {
  const normalizedFormat =
    String(format ?? "").toLowerCase();

  const normalizedUrl =
    String(url ?? "").toLowerCase();

  return (
    normalizedFormat === "hls" ||
    normalizedUrl.includes(".m3u8")
  );
}

function formatBitrate(value) {
  if (!value) {
    return "";
  }

  if (value >= 1000000) {
    return `${(value / 1000000).toFixed(1)} Mb/s`;
  }

  return `${Math.round(value / 1000)} kb/s`;
}

export default function LivePreview({
  channel,
  active,
  onToggle,
  onNavigate,
  buttonRef,
}) {
  const shellRef = useRef(null);
  const videoRef = useRef(null);
  const hlsRef = useRef(null);

  const [previewState, setPreviewState] =
    useState("idle");

  const [levels, setLevels] = useState([]);
  const [selectedLevel, setSelectedLevel] =
    useState(-1);

  const [isFullscreen, setIsFullscreen] =
    useState(false);

  const [infoVisible, setInfoVisible] =
    useState(false);

  const streamUrl =
    channel.stream?.url ?? "";

  const streamFormat =
    channel.stream?.format ?? "";

  const logo =
    channel.logo?.url ?? "";

  useEffect(() => {
    if (!active) {
      return undefined;
    }

    const video = videoRef.current;

    if (!video || !streamUrl) {
      return undefined;
    }

    let disposed = false;
    let startupTimer = null;
    let recoveryAttempts = 0;

    function clearStartupTimer() {
      if (startupTimer !== null) {
        window.clearTimeout(startupTimer);
        startupTimer = null;
      }
    }

    function markPlaying() {
      if (!disposed) {
        clearStartupTimer();
        setPreviewState("playing");
      }
    }

    function markBuffering() {
      if (!disposed) {
        setPreviewState("buffering");
      }
    }

    function markError() {
      if (!disposed) {
        clearStartupTimer();
        setPreviewState("error");
      }
    }

    function playVideo() {
      video.play().catch(markError);
    }

    async function startPlayback() {
      video.muted = true;
      video.playsInline = true;

      startupTimer = window.setTimeout(
        markError,
        PREVIEW_TIMEOUT_MS,
      );

      video.addEventListener(
        "playing",
        markPlaying,
      );

      video.addEventListener(
        "waiting",
        markBuffering,
      );

      video.addEventListener(
        "stalled",
        markBuffering,
      );

      video.addEventListener(
        "error",
        markError,
      );

      if (!isHlsStream(streamFormat, streamUrl)) {
        video.src = streamUrl;
        playVideo();
        return;
      }

      const nativeHls =
        video.canPlayType(
          "application/vnd.apple.mpegurl",
        );

      if (nativeHls) {
        video.src = streamUrl;
        playVideo();
        return;
      }

      try {
        const module =
          await import("hls.js/light");

        if (disposed) {
          return;
        }

        const Hls = module.default;

        if (!Hls.isSupported()) {
          markError();
          return;
        }

        const hls = new Hls({
          enableWorker: true,
          backBufferLength: 12,
          maxBufferLength: 15,
        });

        hlsRef.current = hls;

        hls.attachMedia(video);

        hls.on(
          Hls.Events.MEDIA_ATTACHED,
          () => {
            hls.loadSource(streamUrl);
          },
        );

        hls.on(
          Hls.Events.MANIFEST_PARSED,
          () => {
            const availableLevels =
              hls.levels.map((level, index) => ({
                index,
                height: level.height ?? 0,
                width: level.width ?? 0,
                bitrate: level.bitrate ?? 0,
              }));

            setLevels(availableLevels);
            setSelectedLevel(-1);
            playVideo();
          },
        );

        hls.on(
          Hls.Events.LEVEL_SWITCHED,
          (_event, data) => {
            if (hls.autoLevelEnabled) {
              setSelectedLevel(-1);
              return;
            }

            setSelectedLevel(data.level);
          },
        );

        hls.on(
          Hls.Events.ERROR,
          (_event, data) => {
            if (!data.fatal) {
              return;
            }

            if (recoveryAttempts < 1) {
              recoveryAttempts += 1;

              if (
                data.type ===
                Hls.ErrorTypes.NETWORK_ERROR
              ) {
                hls.startLoad();
                return;
              }

              if (
                data.type ===
                Hls.ErrorTypes.MEDIA_ERROR
              ) {
                hls.recoverMediaError();
                return;
              }
            }

            markError();
          },
        );
      } catch {
        markError();
      }
    }

    startPlayback();

    return () => {
      disposed = true;
      clearStartupTimer();

      video.removeEventListener(
        "playing",
        markPlaying,
      );

      video.removeEventListener(
        "waiting",
        markBuffering,
      );

      video.removeEventListener(
        "stalled",
        markBuffering,
      );

      video.removeEventListener(
        "error",
        markError,
      );

      video.pause();
      video.removeAttribute("src");
      video.load();

      if (hlsRef.current) {
        hlsRef.current.destroy();
        hlsRef.current = null;
      }
    };
  }, [
    active,
    streamFormat,
    streamUrl,
  ]);

  useEffect(() => {
    function handleFullscreenChange() {
      setIsFullscreen(
        document.fullscreenElement ===
          shellRef.current,
      );
    }

    document.addEventListener(
      "fullscreenchange",
      handleFullscreenChange,
    );

    return () => {
      document.removeEventListener(
        "fullscreenchange",
        handleFullscreenChange,
      );
    };
  }, []);

  function handleToggle() {
    if (!active) {
      setPreviewState("loading");
      setLevels([]);
      setSelectedLevel(-1);
      setInfoVisible(false);
    }

    onToggle();
  }

  function handleKeyDown(event) {
    const directions = {
      ArrowLeft: "left",
      ArrowRight: "right",
      ArrowUp: "up",
      ArrowDown: "down",
      Home: "first",
      End: "last",
    };

    const direction =
      directions[event.key];

    if (!direction || !onNavigate) {
      return;
    }

    event.preventDefault();
    onNavigate(direction);
  }

  async function handleFullscreen() {
    const shell = shellRef.current;
    const video = videoRef.current;

    if (!shell) {
      return;
    }

    try {
      if (document.fullscreenElement) {
        await document.exitFullscreen();
        return;
      }

      if (shell.requestFullscreen) {
        await shell.requestFullscreen();
        return;
      }

      if (shell.webkitRequestFullscreen) {
        shell.webkitRequestFullscreen();
        return;
      }

      if (video?.webkitEnterFullscreen) {
        video.webkitEnterFullscreen();
      }
    } catch {
      // Fullscreen is optional on older TV browsers.
    }
  }

  function handleQualityChange(event) {
    const value =
      Number(event.target.value);

    const hls =
      hlsRef.current;

    setSelectedLevel(value);

    if (!hls) {
      return;
    }

    hls.currentLevel = value;
  }

  const qualityLabel =
    selectedLevel === -1
      ? "AUTO"
      : levels.find(
          (level) =>
            level.index === selectedLevel,
        )?.height
        ? `${levels.find(
            (level) =>
              level.index === selectedLevel,
          ).height}p`
        : "MANUAL";

  return (
    <div
      ref={shellRef}
      className={
        `live-preview-shell state-${previewState}`
      }
    >
      <button
        ref={buttonRef}
        type="button"
        className={
          `live-preview ${
            active ? "active" : ""
          }`
        }
        aria-pressed={active}
        onClick={handleToggle}
        onKeyDown={handleKeyDown}
      >
        {active ? (
          <>
            <video
              ref={videoRef}
              className="live-preview-video"
              autoPlay
              muted
              playsInline
            />

            {previewState === "loading" && (
              <span className="live-preview-status">
                <span className="live-preview-spinner" />
                {
                  "Na\u010d\u00edt\u00e1m \u017eiv\u00fd obraz..."
                }
              </span>
            )}

            {previewState === "buffering" && (
              <span className="live-preview-status buffering">
                <span className="live-preview-spinner" />
                {
                  "Stream se znovu na\u010d\u00edt\u00e1..."
                }
              </span>
            )}

            {previewState === "error" && (
              <span className="live-preview-status error">
                {
                  "\u26A0\uFE0F N\u00e1hled se nepoda\u0159ilo spustit"
                }
              </span>
            )}

            {previewState === "playing" && (
              <span className="live-preview-live-badge">
                {"\u25CF LIVE"}
              </span>
            )}

            <span className="live-preview-name">
              {channel.name}
            </span>
          </>
        ) : (
          <>
            {logo ? (
              <img
                className="live-preview-logo"
                src={logo}
                alt=""
              />
            ) : (
              <span className="live-preview-placeholder">
                {"\u{1F4FA}"}
              </span>
            )}

            <span className="live-preview-name">
              {channel.name}
            </span>

            <span className="live-preview-hint">
              {
                "\u{1F441}\uFE0F OK / Enter \u2022 spustit"
              }
            </span>
          </>
        )}
      </button>

      {active && (
        <>
          <div className="live-preview-toolbar">
            <div className="live-preview-toolbar-group">
              <button
                type="button"
                onClick={() =>
                  setInfoVisible((current) => !current)
                }
              >
                {
                  infoVisible
                    ? "\u2715 Info"
                    : "\u2139\uFE0F Info"
                }
              </button>

              <button
                type="button"
                onClick={handleFullscreen}
              >
                {isFullscreen
                  ? "\u229F Zp\u011bt"
                  : "\u26F6 Fullscreen"}
              </button>
            </div>

            <div className="live-preview-quality">
              <span>
                {"Kvalita "}
                <strong>{qualityLabel}</strong>
              </span>

              {levels.length > 1 && (
                <select
                  value={selectedLevel}
                  onChange={handleQualityChange}
                  aria-label="Kvalita obrazu"
                >
                  <option value={-1}>
                    AUTO
                  </option>

                  {levels.map((level) => (
                    <option
                      key={level.index}
                      value={level.index}
                    >
                      {level.height
                        ? `${level.height}p`
                        : `Level ${level.index + 1}`}
                      {level.bitrate
                        ? ` \u2022 ${formatBitrate(level.bitrate)}`
                        : ""}
                    </option>
                  ))}
                </select>
              )}
            </div>
          </div>

          {infoVisible && (
            <div className="live-preview-info">
              <div>
                <span>Stanice</span>
                <strong>{channel.name}</strong>
              </div>

              <div>
                <span>Zem\u011b</span>
                <strong>{channel.country}</strong>
              </div>

              <div>
                <span>Kategorie</span>
                <strong>{channel.category}</strong>
              </div>

              <div>
                <span>Provider</span>
                <strong>{channel.provider}</strong>
              </div>

              <div>
                <span>Form\u00e1t</span>
                <strong>
                  {channel.stream?.format ?? "-"}
                </strong>
              </div>

              <div>
                <span>Katalogov\u00e1 kvalita</span>
                <strong>
                  {channel.stream?.quality ?? "-"}
                </strong>
              </div>

              <div>
                <span>EPG</span>
                <strong>
                  {channel.epg?.enabled
                    ? "\u2705 ano"
                    : "\u2796 ne"}
                </strong>
              </div>

              <div>
                <span>Stav</span>
                <strong>{channel.status}</strong>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
