import Artplayer from 'artplayer';
import Hls from 'hls.js';
import mpegts from 'mpegts.js';
import React, { useEffect, useRef } from 'react';

interface LivePlayerProps {
  url: string;
  format: string;
  style?: React.CSSProperties;
}

const LivePlayer: React.FC<LivePlayerProps> = ({ url, format, style }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const artRef = useRef<Artplayer | null>(null);
  const mpegtsRef = useRef<ReturnType<typeof mpegts.createPlayer> | null>(null);
  const hlsRef = useRef<Hls | null>(null);

  useEffect(() => {
    if (!containerRef.current || !url) return;

    // Destroy previous instance
    mpegtsRef.current?.destroy();
    mpegtsRef.current = null;
    hlsRef.current?.destroy();
    hlsRef.current = null;
    if (artRef.current) {
      artRef.current.destroy();
      artRef.current = null;
    }

    const options: ConstructorParameters<typeof Artplayer>[0] = {
      container: containerRef.current,
      url,
      isLive: true,
      autoplay: true,
      autoSize: false,
      autoMini: false,
      loop: false,
      flip: true,
      playbackRate: false,
      aspectRatio: true,
      setting: true,
      pip: true,
      fullscreen: true,
      fullscreenWeb: true,
      mutex: true,
      backdrop: true,
      theme: '#1677ff',
      lang: 'zh-cn',
      moreVideoAttr: {
        crossOrigin: 'anonymous',
      },
    };

    if (format === 'flv' && mpegts.isSupported()) {
      options.customType = {
        flv: (video: HTMLVideoElement, streamUrl: string) => {
          const player = mpegts.createPlayer({
            type: 'flv',
            url: streamUrl,
            isLive: true,
          } as mpegts.MediaDataSource);
          player.attachMediaElement(video);
          player.load();
          player.play();
          mpegtsRef.current = player;
        },
      };
      options.type = 'flv';
    } else if (format === 'hls') {
      if (Hls.isSupported()) {
        options.customType = {
          m3u8: (video: HTMLVideoElement, streamUrl: string) => {
            const hls = new Hls({
              enableWorker: true,
              lowLatencyMode: true,
            });
            hls.loadSource(streamUrl);
            hls.attachMedia(video);
            hlsRef.current = hls;
          },
        };
        options.type = 'm3u8';
      }
      // Safari supports HLS natively
    }

    const art = new Artplayer(options);
    artRef.current = art;

    return () => {
      mpegtsRef.current?.destroy();
      mpegtsRef.current = null;
      hlsRef.current?.destroy();
      hlsRef.current = null;
      if (artRef.current) {
        artRef.current.destroy();
        artRef.current = null;
      }
    };
  }, [url, format]);

  return (
    <div
      ref={containerRef}
      style={{
        width: '100%',
        aspectRatio: '16 / 9',
        borderRadius: 8,
        overflow: 'hidden',
        background: '#000',
        ...style,
      }}
    />
  );
};

export default LivePlayer;
