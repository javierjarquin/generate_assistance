import { loadFont } from "@remotion/google-fonts/Anton";
import { Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import type { Palabra } from "./types";

const { fontFamily } = loadFont("normal", { weights: ["400"], subsets: ["latin", "latin-ext"] });

// Una "página" = las palabras que se ven juntas. Se corta por cantidad, por
// largo, o por una pausa de la voz (así no se mezclan dos frases).
const MAX_PALABRAS = 4;
const MAX_LETRAS = 22;
const PAUSA = 0.45;
const ENFASIS = "#FF4D3D";

export const paginar = (words: Palabra[]): Palabra[][] => {
  const paginas: Palabra[][] = [];
  let actual: Palabra[] = [];
  for (const w of words) {
    const letras = actual.reduce((n, x) => n + x.text.length + 1, 0) + w.text.length;
    const anterior = actual[actual.length - 1];
    const pausa = anterior ? w.start - anterior.end > PAUSA : false;
    const fin = anterior ? /[.?!]$/.test(anterior.text) : false;
    if (actual.length && (actual.length >= MAX_PALABRAS || letras > MAX_LETRAS || pausa || fin)) {
      paginas.push(actual);
      actual = [];
    }
    actual.push(w);
  }
  if (actual.length) paginas.push(actual);
  return paginas;
};

export const Karaoke: React.FC<{
  readonly words: Palabra[];
  readonly gold: string;
}> = ({ words, gold }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const t = frame / fps;
  const paginas = paginar(words);
  // La página visible: la última que ya empezó, mientras no haya pasado
  // mucho de su última palabra (en silencios largos no queda texto colgado).
  const pagina = [...paginas].reverse().find((p) => p[0].start <= t + 0.05);
  if (!pagina || t > pagina[pagina.length - 1].end + 0.6) return null;
  const inicio = pagina[0].start * fps;

  return (
    <div
      style={{
        position: "absolute",
        left: "50%",
        translate: "-50% 0px",
        maxWidth: width - 160,
        width: "max-content",
        top: height * 0.7,
        display: "flex",
        flexWrap: "wrap",
        justifyContent: "center",
        gap: "6px 26px",
        padding: "22px 30px 26px",
        borderRadius: 26,
        background: "rgba(11,31,58,0.78)",
        boxShadow: "0 18px 40px rgba(0,0,0,0.35)",
        fontFamily,
        fontSize: 90,
        lineHeight: 1.08,
        textTransform: "uppercase",
        textAlign: "center",
        scale: interpolate(frame, [inicio, inicio + 6], [0.92, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: Easing.bezier(0.16, 1, 0.3, 1),
        }),
      }}
    >
      {pagina.map((w, i) => {
        const activa = t >= w.start && t < w.end + 0.05;
        const dicha = t >= w.end;
        // CapituloPlus: la cifra o el nombre que duele va en rojo (sale del
        // texto_en_pantalla de su plano). Sin `enfasis`, igual que siempre.
        return (
          <span
            key={`${w.start}-${i}`}
            style={{
              color: w.enfasis ? ENFASIS : activa ? gold : "white",
              opacity: activa || dicha ? 1 : 0.85,
              WebkitTextStroke: "14px #050b16",
              paintOrder: "stroke fill",
              textShadow: "0 8px 18px rgba(0,0,0,0.55)",
              scale: activa ? 1.06 : 1,
              transformOrigin: "center bottom",
              display: "inline-block",
            }}
          >
            {w.text}
          </span>
        );
      })}
    </div>
  );
};
