import {
  useEffect,
  useRef,
  useState,
} from "react";

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

export default function LivePreview({
  channel,
  active,
  onToggle,
}) {
  const videoRef = useRef(null);
  const [previewState, setPreviewState] =
    useState("loading");

  const streamUrl = channel.stream?.url ?? "";
  const streamFormat =
    channel.stream?.format ?? "";

  const logo = channel.logo?.url;

  useEffect(() => {
    if (!active) {
      return undefined;
    }

    const video = videoRef.current;

    if (!video || !streamUrl) {
      return undefined;
    }

    let hls = null;
    let disposed = false;

    function markPlaying() {
      if (!disposed) {
        setPreviewState("playing");
      }
    }

    function markError() {
      if (!disposed) {
        setPreviewState("error");
      }
    }

    function playVideo() {
      video
        .play()
        .catch(markError);
    }

    async function startPlayback() {
      video.muted = true;
      video.playsInline = true;

      video.addEventListener(
        "playing",
        markPlaying,
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

        hls = new Hls({
          enableWorker: true,
        });

        hls.attachMedia(video);

        hls.on(
          Hls.Events.MEDIA_ATTACHED,
          () => {
            hls.loadSource(streamUrl);
          },
        );

        hls.on(
          Hls.Events.MANIFEST_PARSED,
          playVideo,
        );

        hls.on(
          Hls.Events.ERROR,
          (_event, data) => {
            if (data.fatal) {
              markError();
            }
          },
        );
      } catch {
        markError();
      }
    }

    startPlayback();

    return () => {
      disposed = true;

      video.removeEventListener(
        "playing",
        markPlaying,
      );

      video.removeEventListener(
        "error",
        markError,
      );

      video.pause();
      video.removeAttribute("src");
      video.load();

      if (hls) {
        hls.destroy();
      }
    };
  }, [
    active,
    streamFormat,
    streamUrl,
  ]);

  function handleToggle() {
    if (!active) {
      setPreviewState("loading");
    }

    onToggle();
  }

  const visibleState =
    !streamUrl
      ? "error"
      : previewState;

  return (
    <button
      type="button"
      className={
        `live-preview ${
          active ? "active" : ""
        }`
      }
      aria-pressed={active}
      aria-label={
        active
          ? `Zavrit nahled ${channel.name}`
          : `Spustit nahled ${channel.name}`
      }
      onClick={handleToggle}
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

          {visibleState === "loading" && (
            <span className="live-preview-status">
              {
                "\u{1F415} Na\u010d\u00edt\u00e1m \u017eiv\u00fd obraz..."
              }
            </span>
          )}

          {visibleState === "error" && (
            <span className="live-preview-status error">
              {
                "\u26A0\uFE0F N\u00e1hled nen\u00ed v prohl\u00ed\u017ee\u010di dostupn\u00fd"
              }
            </span>
          )}

          <span className="live-preview-close">
            {
              "OK / Enter \u2022 zav\u0159\u00edt"
            }
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
              "\u{1F441}\uFE0F N\u00e1hled \u2022 OK / Enter"
            }
          </span>
        </>
      )}
    </button>
  );
}
