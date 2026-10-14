import { Audio } from "@remotion/media";
import {
  AbsoluteFill,
  CanvasImage,
  interpolate,
  Sequence,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { FUNDIDO, Grafico, PlanoImagenes, Titulo } from "./Escenas";
import { Karaoke } from "./Karaoke";
import type { CapituloProps, Plano } from "./types";

// Cada plano arranca en su segundo REAL del audio (planos_alineados.json) y
// dura hasta que empieza el siguiente: así voz, imagen y título no se
// desfasan. El siguiente entra encima con un fundido de FUNDIDO frames.
const tramo = (planos: Plano[], i: number, fps: number, total: number) => {
  const desde = Math.round(planos[i].start * fps);
  const hasta = i + 1 < planos.length ? Math.round(planos[i + 1].start * fps) : total;
  return { desde, duracion: Math.max(1, hasta - desde) };
};

const Entrada: React.FC<{ readonly primero: boolean; readonly children: React.ReactNode }> = ({
  primero,
  children,
}) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill
      style={{
        opacity: primero
          ? 1
          : interpolate(frame, [0, FUNDIDO], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
      }}
    >
      {children}
    </AbsoluteFill>
  );
};

export const Capitulo: React.FC<CapituloProps> = (props) => {
  const { fps, durationInFrames } = useVideoConfig();
  const frame = useCurrentFrame();
  const { navy, gold } = props.palette;
  // El logo de esquina se esconde en el gráfico de cierre: ahí ya está en grande.
  const enGrafico = props.planos.some(
    (p, i) =>
      p.tipo === "grafico_movimiento" &&
      frame >= Math.round(p.start * fps) &&
      (i + 1 >= props.planos.length || frame < Math.round(props.planos[i + 1].start * fps)),
  );
  return (
    <AbsoluteFill style={{ backgroundColor: navy }}>
      {props.planos.map((plano, i) => {
        const { desde, duracion } = tramo(props.planos, i, fps, durationInFrames);
        const grafico = plano.tipo === "grafico_movimiento" || plano.shots.length === 0;
        return (
          <Sequence
            key={plano.id}
            name={`${plano.id} · ${plano.seccion}`}
            from={desde}
            durationInFrames={duracion + FUNDIDO}
            premountFor={fps}
            layout="absolute-fill"
          >
            <Entrada primero={i === 0}>
              {grafico ? (
                <Grafico plano={plano} logo={props.logo} navy={navy} gold={gold} />
              ) : (
                <>
                  <PlanoImagenes plano={plano} duracion={duracion} />
                  {/* Degradado abajo para que los subtítulos se lean sobre cualquier foto */}
                  <AbsoluteFill
                    style={{ background: `linear-gradient(to bottom, transparent 52%, ${navy}cc 100%)` }}
                  />
                  <Titulo texto={plano.texto} navy={navy} gold={gold} />
                </>
              )}
            </Entrada>
          </Sequence>
        );
      })}

      <Karaoke words={props.words} gold={gold} />

      {props.logo && !enGrafico ? (
        <CanvasImage
          src={staticFile(props.logo)}
          width={150}
          height={150}
          fit="contain"
          style={{ position: "absolute", top: 70, left: 40, opacity: 0.85 }}
        />
      ) : null}

      <Audio src={staticFile(props.audio)} />
      {props.musica ? <Audio src={staticFile(props.musica)} volume={props.musicaVolumen} loop /> : null}
    </AbsoluteFill>
  );
};
