// POC CapituloPlus (13/10/2026): "aquí es". Acercamiento desde la ciudad hasta
// la supermanzana del guion, con un pin. Mapa real de OpenStreetMap servido
// por OpenFreeMap (sin clave). Se dibujan cuatro placas FIJAS a distinto zoom
// y el movimiento es solo CSS (skill remotion-maps: mover la cámara de
// MapLibre cuadro por cuadro hace temblar el mapa en el render).
import { loadFont } from "@remotion/google-fonts/Anton";
import { useEffect, useRef, useState } from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useDelayRender, useVideoConfig } from "remotion";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

const { fontFamily } = loadFont("normal", { weights: ["400"], subsets: ["latin", "latin-ext"] });

const ESTILO = "https://tiles.openfreemap.org/styles/liberty";
const K = 1.5; // la placa mide 1.5 veces el cuadro: se ve entera a escala 1/K
const ZOOMS = [11, 12.5, 14, 15.5];
const fijo = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

// MapLibre 5 trae su worker dentro del paquete: no hace falta setWorkerUrl()
// (el maplibre-gl-worker.mjs que cita el skill es de una versión más nueva).

const Placa: React.FC<{ readonly centro: [number, number]; readonly zoom: number }> = ({ centro, zoom }) => {
  const ref = useRef<HTMLDivElement>(null);
  const { width, height } = useVideoConfig();
  const { delayRender, continueRender, cancelRender } = useDelayRender();
  const [espera] = useState(() => delayRender(`mapa z${zoom}`, { timeoutInMilliseconds: 120000 }));
  useEffect(() => {
    if (!ref.current) return;
    const mapa = new maplibregl.Map({
      container: ref.current,
      style: ESTILO,
      center: centro,
      zoom,
      interactive: false,
      attributionControl: false,
      fadeDuration: 0,
      canvasContextAttributes: { preserveDrawingBuffer: true },
    });
    mapa.on("error", (e) => cancelRender(e.error ?? new Error("MapLibre falló")));
    mapa.on("load", () => {
      mapa.jumpTo({ center: centro, zoom });
      mapa.once("idle", () => continueRender(espera));
    });
  }, [cancelRender, centro, continueRender, espera, zoom]);
  return <div ref={ref} style={{ width: width * K, height: height * K, position: "absolute", left: 0, top: 0 }} />;
};

export const Mapa: React.FC<{
  readonly centro: [number, number];
  readonly etiqueta: string;
  readonly navy: string;
  readonly gold: string;
}> = ({ centro, etiqueta, navy, gold }) => {
  const frame = useCurrentFrame();
  const { fps, width, height, durationInFrames } = useVideoConfig();
  const n = ZOOMS.length;
  const tramo = durationInFrames * 0.78 / n; // el último 22% el mapa queda quieto con el pin
  const cruce = 7;
  const pin = spring({ frame: frame - tramo * (n - 1) - 4, fps, config: { damping: 10, stiffness: 180 } });
  const pulso = (frame % 30) / 30;
  return (
    <AbsoluteFill style={{ backgroundColor: navy, overflow: "hidden" }}>
      {ZOOMS.map((z, i) => {
        const ini = i * tramo;
        const fin = i === n - 1 ? durationInFrames : (i + 1) * tramo + cruce;
        // Cada placa crece de 1/K (se ve entera) a 1 (nítida), y al cruzarse
        // con la siguiente sigue un poco más: se lee como un solo acercamiento.
        const s = interpolate(frame, [ini, fin - cruce, fin], [1 / K, 1, i === n - 1 ? 1 : 1.18], fijo);
        const opacidad = i === 0 ? 1 : interpolate(frame, [ini, ini + cruce], [0, 1], fijo);
        const oculta = frame < ini - 1 || (i < n - 1 && frame > fin + 1);
        return (
          <div
            key={z}
            style={{
              position: "absolute",
              left: (width - width * K * s) / 2,
              top: (height - height * K * s) / 2,
              transform: `scale(${s})`,
              transformOrigin: "0 0",
              // Oculta pero montada: así carga antes de que le toque.
              opacity: oculta ? 0 : opacidad,
            }}
          >
            <Placa centro={centro} zoom={z} />
          </div>
        );
      })}
      <AbsoluteFill style={{ background: `radial-gradient(circle at 50% 50%, transparent 35%, ${navy}aa 100%)` }} />
      {/* Pin en el centro exacto (cada placa está centrada en las coordenadas). */}
      <div style={{ position: "absolute", left: width / 2, top: height / 2, opacity: pin }}>
        <div
          style={{
            position: "absolute",
            width: 60 + pulso * 140,
            height: 60 + pulso * 140,
            left: -(30 + pulso * 70),
            top: -(30 + pulso * 70),
            borderRadius: "50%",
            border: `6px solid ${gold}`,
            opacity: 1 - pulso,
          }}
        />
        <div
          style={{
            position: "absolute",
            width: 54,
            height: 54,
            left: -27,
            top: -27 - interpolate(pin, [0, 1], [120, 0]),
            borderRadius: "50%",
            background: "#FF4D3D",
            border: "8px solid white",
            boxShadow: "0 10px 24px rgba(0,0,0,0.5)",
          }}
        />
      </div>
      <div
        style={{
          position: "absolute",
          top: height / 2 - 230,
          width: "100%",
          display: "flex",
          justifyContent: "center",
          opacity: pin,
          scale: interpolate(pin, [0, 1], [0.7, 1]),
        }}
      >
        <div
          style={{
            fontFamily,
            fontSize: 72,
            color: navy,
            background: gold,
            padding: "10px 30px",
            borderRadius: 16,
            boxShadow: `0 10px 0 ${navy}, 0 16px 34px rgba(0,0,0,0.45)`,
          }}
        >
          {etiqueta}
        </div>
      </div>
      <div style={{ position: "absolute", left: 30, bottom: 26, fontSize: 24, color: "white", opacity: 0.8, fontFamily: "sans-serif" }}>
        © OpenStreetMap · OpenFreeMap
      </div>
    </AbsoluteFill>
  );
};
