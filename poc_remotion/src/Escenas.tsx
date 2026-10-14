import { loadFont } from "@remotion/google-fonts/Anton";
import {
  AbsoluteFill,
  CanvasImage,
  Easing,
  interpolate,
  Sequence,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type { Plano } from "./types";

const { fontFamily } = loadFont("normal", { weights: ["400"], subsets: ["latin", "latin-ext"] });

export const FUNDIDO = 8; // frames de transición entre planos y entre tomas

// Una toma con Ken Burns suave: zoom lento y paneo alternado por toma.
export const Toma: React.FC<{
  readonly src: string;
  readonly indice: number;
  readonly duracion: number; // frames
}> = ({ src, indice, duracion }) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const sentido = indice % 2 === 0 ? 1 : -1;
  return (
    <AbsoluteFill
      style={{
        opacity: interpolate(frame, [0, FUNDIDO], [indice === 0 ? 1 : 0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        }),
        scale: interpolate(frame, [0, duracion], [1.06, 1.16], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          output: "perceptual-scale",
        }),
        translate: interpolate(frame, [0, duracion], [`${-18 * sentido}px 0px`, `${18 * sentido}px -14px`], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        }),
      }}
    >
      <CanvasImage src={staticFile(src)} width={width} height={height} fit="cover" />
    </AbsoluteFill>
  );
};

// Las tomas de un plano se reparten su duración; cada una entra con fundido.
export const PlanoImagenes: React.FC<{
  readonly plano: Plano;
  readonly duracion: number;
}> = ({ plano, duracion }) => {
  const { fps } = useVideoConfig();
  const porToma = duracion / Math.max(1, plano.shots.length);
  return (
    <AbsoluteFill>
      {plano.shots.map((src, i) => (
        <Sequence key={src} name={src} from={Math.round(i * porToma)} premountFor={fps} layout="absolute-fill">
          <Toma src={src} indice={i} duracion={Math.round(porToma) + FUNDIDO} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};

// texto_en_pantalla: entra con spring al inicio del plano y sale a los ~2.6 s.
export const Titulo: React.FC<{
  readonly texto: string;
  readonly navy: string;
  readonly gold: string;
}> = ({ texto, navy, gold }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  if (!texto) return null;
  const entrada = spring({ frame, fps, config: { damping: 14, stiffness: 160 } });
  const salida = interpolate(frame, [2.4 * fps, 2.8 * fps], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <div
      style={{
        position: "absolute",
        top: 230,
        left: 80,
        right: 80,
        display: "flex",
        justifyContent: "center",
        opacity: salida,
        translate: `0px ${interpolate(entrada, [0, 1], [-60, 0])}px`,
        scale: interpolate(entrada, [0, 1], [0.6, 1]),
      }}
    >
      <div
        style={{
          fontFamily,
          fontSize: 84,
          lineHeight: 1.05,
          color: navy,
          background: gold,
          padding: "14px 34px",
          borderRadius: 18,
          textAlign: "center",
          textTransform: "uppercase",
          boxShadow: `0 14px 0 ${navy}, 0 18px 40px rgba(0,0,0,0.45)`,
        }}
      >
        {texto}
      </div>
    </div>
  );
};

// visual.tipo = grafico_movimiento: gráfico animado en vez de imagen (el cierre).
export const Grafico: React.FC<{
  readonly plano: Plano;
  readonly logo: string | null;
  readonly navy: string;
  readonly gold: string;
}> = ({ plano, logo, navy, gold }) => {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  const logoIn = spring({ frame, fps, config: { damping: 12 } });
  const textoIn = spring({ frame: frame - 0.35 * fps, fps, config: { damping: 16 } });
  const lineas = [0, 1, 2, 3, 4, 5];
  return (
    <AbsoluteFill style={{ background: `radial-gradient(circle at 50% 40%, #16335f 0%, ${navy} 62%)` }}>
      {lineas.map((i) => (
        <div
          key={i}
          style={{
            position: "absolute",
            left: -200,
            width: width + 400,
            height: 6,
            top: 260 + i * 260,
            background: gold,
            opacity: 0.12,
            rotate: "-14deg",
            translate: `${interpolate(frame, [0, 6 * fps], [-120 + i * 30, 120 + i * 30])}px 0px`,
          }}
        />
      ))}
      {logo ? (
        <div style={{ position: "absolute", top: 300, width: "100%", display: "flex", justifyContent: "center" }}>
          <CanvasImage
            src={staticFile(logo)}
            width={420}
            height={420}
            fit="contain"
            style={{ scale: interpolate(logoIn, [0, 1], [0.3, 1]), opacity: logoIn }}
          />
        </div>
      ) : null}
      <div
        style={{
          position: "absolute",
          top: 780,
          left: 80,
          right: 80,
          textAlign: "center",
          fontFamily,
          fontSize: 110,
          lineHeight: 1.02,
          color: gold,
          textTransform: "uppercase",
          opacity: textoIn,
          translate: `0px ${interpolate(textoIn, [0, 1], [50, 0])}px`,
        }}
      >
        {plano.texto}
      </div>
      <div
        style={{
          position: "absolute",
          top: 1040,
          width: "100%",
          textAlign: "center",
          fontFamily,
          fontSize: 56,
          color: "white",
          letterSpacing: 4,
          opacity: interpolate(frame, [0.8 * fps, 1.2 * fps], [0, 0.9], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.16, 1, 0.3, 1),
          }),
        }}
      >
        DATO MATA GATO
      </div>
    </AbsoluteFill>
  );
};
