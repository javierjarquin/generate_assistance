// POC CapituloPlus (13/10/2026): fichas animadas, contador del gancho y
// tarjeta de contradicción. Todo sale de datos ya verificados en el guion.
import { loadFont as cargarAnton } from "@remotion/google-fonts/Anton";
import { loadFont as cargarRoboto } from "@remotion/google-fonts/RobotoCondensed";
import { Circle, Highlight } from "@remotion/rough-notation";
import { AbsoluteFill, Easing, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import type { Bloque, FichaDatos } from "../types";

const { fontFamily: anton } = cargarAnton("normal", { weights: ["400"], subsets: ["latin", "latin-ext"] });
const { fontFamily: roboto } = cargarRoboto("normal", { weights: ["700"], subsets: ["latin", "latin-ext"] });

const ROJO = "#FF4D3D";
const fijo = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

const Fondo: React.FC<{ readonly navy: string; readonly gold: string }> = ({ navy, gold }) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: `radial-gradient(circle at 30% 20%, #1b3c6e 0%, ${navy} 58%, #050b16 100%)` }}>
      {/* Retícula tenue que se desliza: el fondo no se ve "congelado". */}
      <AbsoluteFill
        style={{
          backgroundImage: `linear-gradient(${gold}14 2px, transparent 2px), linear-gradient(90deg, ${gold}14 2px, transparent 2px)`,
          backgroundSize: "120px 120px",
          backgroundPosition: `${frame * 0.6}px ${frame * 0.9}px`,
        }}
      />
    </AbsoluteFill>
  );
};

const Renglon: React.FC<{ readonly texto: string; readonly i: number; readonly desde: number }> = ({
  texto,
  i,
  desde,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const e = spring({ frame: frame - desde - i * 5, fps, config: { damping: 18, stiffness: 140 } });
  return (
    <div style={{ opacity: e, translate: `${interpolate(e, [0, 1], [-60, 0])}px 0px` }}>{texto}</div>
  );
};

// La ficha (tipo "ficha" de la evidencia) dibujada en vez de su imagen fija:
// renglones que entran uno por uno y el dato clave marcado con resaltador.
export const FichaAnimada: React.FC<{
  readonly ficha: FichaDatos;
  readonly navy: string;
  readonly gold: string;
}> = ({ ficha, navy, gold }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const titulo = spring({ frame, fps, config: { damping: 16 } });
  // El resaltador entra cuando la voz llega a ese renglón (lo calcula render_plus.py).
  const desde = Math.max(ficha.resaltarDesde * fps, 8 + ficha.renglones.length * 5);
  const marca = interpolate(frame, [desde, desde + 0.55 * fps], [0, 1], fijo);
  return (
    <AbsoluteFill style={{ scale: interpolate(frame, [0, 6 * fps], [1, 1.05], fijo) }}>
      <Fondo navy={navy} gold={gold} />
      <div style={{ position: "absolute", left: 110, right: 110, top: 380 }}>
        <div
          style={{
            fontFamily: anton,
            fontSize: 92,
            lineHeight: 1.05,
            color: gold,
            textTransform: "uppercase",
            opacity: titulo,
            translate: `0px ${interpolate(titulo, [0, 1], [40, 0])}px`,
          }}
        >
          {ficha.titulo}
        </div>
        <div style={{ height: 8, background: gold, marginTop: 26, width: `${interpolate(titulo, [0, 1], [0, 100])}%` }} />
        <div style={{ fontFamily: roboto, fontSize: 58, lineHeight: 1.25, color: "white", marginTop: 44, display: "grid", gap: 26 }}>
          {ficha.renglones.map((r, i) =>
            i === ficha.resaltar ? (
              <div key={r}>
                <Highlight color={`${gold}99`} progress={marca} padding={{ left: 10, right: 10, top: 2, bottom: 2 }} style={{ display: "inline-block", maxWidth: 840 }}>
                  <Renglon texto={r} i={i} desde={8} />
                </Highlight>
              </div>
            ) : (
              <Renglon key={r} texto={r} i={i} desde={8} />
            ),
          )}
        </div>
      </div>
      <div style={{ position: "absolute", left: 110, right: 110, bottom: 150, fontFamily: roboto, fontSize: 34, color: "#9fb0c8", textTransform: "uppercase", letterSpacing: 1 }}>
        Fuente: {ficha.fuente}
      </div>
    </AbsoluteFill>
  );
};

// El gancho con su cifra: el número sube de 0 a N mientras la voz lo dice.
export const Contador: React.FC<{
  readonly numero: number;
  readonly antes: string;
  readonly despues: string;
  readonly navy: string;
  readonly gold: string;
}> = ({ numero, antes, despues, navy, gold }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const valor = Math.round(
    interpolate(frame, [3, 0.95 * fps], [0, numero], { ...fijo, easing: Easing.bezier(0.16, 1, 0.3, 1) }),
  );
  const golpe = spring({ frame: frame - 0.95 * fps, fps, config: { damping: 9, stiffness: 220 } });
  const sub = spring({ frame: frame - 0.5 * fps, fps, config: { damping: 16 } });
  const { durationInFrames } = useVideoConfig();
  const salida = interpolate(frame, [durationInFrames - 8, durationInFrames], [1, 0], fijo);
  return (
    <AbsoluteFill style={{ opacity: salida }}>
    <Fondo navy={navy} gold={gold} />
    <div style={{ position: "absolute", top: 420, left: 60, right: 60, display: "flex", flexDirection: "column", alignItems: "center" }}>
      {antes ? (
        <div style={{ fontFamily: anton, fontSize: 70, color: "white", WebkitTextStroke: "10px #050b16", paintOrder: "stroke fill" }}>
          {antes}
        </div>
      ) : null}
      <div
        style={{
          fontFamily: anton,
          fontSize: 300,
          lineHeight: 0.95,
          color: gold,
          WebkitTextStroke: "18px #050b16",
          paintOrder: "stroke fill",
          textShadow: "0 18px 40px rgba(0,0,0,0.6)",
          scale: interpolate(golpe, [0, 1], [1, 1.08]) - interpolate(golpe, [0.8, 1], [0, 0.08], fijo),
        }}
      >
        {valor}
      </div>
      <div
        style={{
          fontFamily: anton,
          fontSize: 78,
          color: navy,
          background: gold,
          padding: "8px 30px",
          borderRadius: 16,
          textTransform: "uppercase",
          opacity: sub,
          translate: `0px ${interpolate(sub, [0, 1], [30, 0])}px`,
          boxShadow: `0 10px 0 ${navy}`,
        }}
      >
        {despues}
      </div>
    </div>
    </AbsoluteFill>
  );
};

const Mitad: React.FC<{
  readonly bloque: Bloque;
  readonly color: string;
  readonly tinta: string;
  readonly resaltar: string;
  readonly marca: number;
}> = ({ bloque, color, tinta, resaltar, marca }) => (
  <div>
    <div
      style={{
        display: "inline-block",
        fontFamily: anton,
        fontSize: 64,
        color: tinta,
        background: color,
        padding: "6px 26px",
        borderRadius: 14,
        textTransform: "uppercase",
      }}
    >
      {bloque.titulo}
    </div>
    <div style={{ fontFamily: roboto, fontSize: 60, lineHeight: 1.2, color: "white", marginTop: 30, display: "grid", gap: 20 }}>
      {bloque.renglones.map((r, i) =>
        r === resaltar ? (
          <div key={r}>
            <Circle color={ROJO} strokeWidth={6} progress={marca} padding={{ left: 14, right: 14, top: 12, bottom: 12 }} style={{ display: "inline-block", maxWidth: 820 }}>
              <Renglon texto={r} i={i} desde={0} />
            </Circle>
          </div>
        ) : (
          <Renglon key={r} texto={r} i={i} desde={0} />
        ),
      )}
    </div>
  </div>
);

// "Algo no cuadra" en pantalla: lo prometido arriba, lo que hay abajo (entra
// cuando la voz llega a esa parte) y lo que no cuadra encerrado en rojo.
export const Contradiccion: React.FC<{
  readonly arriba: Bloque;
  readonly abajo: Bloque;
  readonly abajoDesde: number;
  readonly resaltar: string;
  readonly fuente: string;
  readonly navy: string;
  readonly gold: string;
}> = ({ arriba, abajo, abajoDesde, resaltar, fuente, navy, gold }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const desde = Math.round(abajoDesde * fps);
  const entra = spring({ frame: frame - desde, fps, config: { damping: 16 } });
  const marca = interpolate(frame, [desde + 0.5 * fps, desde + 1.1 * fps], [0, 1], fijo);
  return (
    <AbsoluteFill>
      <Fondo navy={navy} gold={gold} />
      <div style={{ position: "absolute", left: 100, right: 100, top: 250 }}>
        <Mitad bloque={arriba} color={gold} tinta={navy} resaltar={resaltar} marca={marca} />
      </div>
      <div
        style={{
          position: "absolute",
          left: 100,
          right: 100,
          top: 850,
          height: 8,
          background: ROJO,
          width: `${interpolate(entra, [0, 1], [0, 880])}px`,
        }}
      />
      <div style={{ position: "absolute", left: 100, right: 100, top: 900, opacity: entra, translate: `0px ${interpolate(entra, [0, 1], [50, 0])}px` }}>
        {frame >= desde ? <Mitad bloque={abajo} color={ROJO} tinta="white" resaltar={resaltar} marca={marca} /> : null}
      </div>
      <div style={{ position: "absolute", left: 100, right: 100, bottom: 150, fontFamily: roboto, fontSize: 32, color: "#9fb0c8", textTransform: "uppercase" }}>
        Fuente: {fuente}
      </div>
    </AbsoluteFill>
  );
};
