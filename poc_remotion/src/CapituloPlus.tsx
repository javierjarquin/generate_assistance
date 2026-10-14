// POC CapituloPlus (13/10/2026): Capitulo + valor visual para retención, sin
// sonido (Javier pone la música en TikTok) y sin IA generativa:
//   1. mapa del lugar exacto (te afecta / se puede grabar)
//   2. tarjeta de contradicción (algo no cuadra / coraje)
//   3. fichas dibujadas y animadas, con el dato clave resaltado
//   4. contador en el gancho
//   5. palabras clave en rojo en los subtítulos (las del texto_en_pantalla)
//   6. destellos de luz en los cortes de sección
// Capitulo (el del pipeline) no cambia.
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
import { FUNDIDO, Grafico, Titulo, Toma } from "./Escenas";
import { Karaoke } from "./Karaoke";
import { Contador, Contradiccion, FichaAnimada } from "./plus/Tarjetas";
import { Destello } from "./plus/Destello";
import { Mapa } from "./plus/Mapa";
import type { Plano, PlusProps } from "./types";

const tramo = (planos: Plano[], i: number, fps: number, total: number) => {
  const desde = Math.round(planos[i].start * fps);
  const hasta = i + 1 < planos.length ? Math.round(planos[i + 1].start * fps) : total;
  return { desde, duracion: Math.max(1, hasta - desde) };
};

const Entrada: React.FC<{ readonly primero: boolean; readonly children: React.ReactNode }> = ({ primero, children }) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill
      style={{
        opacity: primero ? 1 : interpolate(frame, [0, FUNDIDO], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
      }}
    >
      {children}
    </AbsoluteFill>
  );
};

const Tomas: React.FC<{
  readonly plano: Plano;
  readonly duracion: number;
  readonly fichas: PlusProps["fichas"][string] | undefined;
  readonly navy: string;
  readonly gold: string;
}> = ({ plano, duracion, fichas, navy, gold }) => {
  const { fps } = useVideoConfig();
  const porToma = duracion / Math.max(1, plano.shots.length);
  return (
    <AbsoluteFill>
      {plano.shots.map((src, i) => {
        const ficha = fichas?.[String(i)];
        return (
          <Sequence key={src} name={ficha ? `ficha ${src}` : src} from={Math.round(i * porToma)} premountFor={fps} layout="absolute-fill">
            {ficha ? (
              <Entrada primero={i === 0}>
                <FichaAnimada ficha={ficha} navy={navy} gold={gold} />
              </Entrada>
            ) : (
              <Toma src={src} indice={i} duracion={Math.round(porToma) + FUNDIDO} />
            )}
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};

export const CapituloPlus: React.FC<PlusProps> = (props) => {
  const { fps, durationInFrames } = useVideoConfig();
  const frame = useCurrentFrame();
  const { navy, gold } = props.palette;
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
        const contra = props.contradiccion?.plano === plano.id ? props.contradiccion : null;
        const contador = props.contador?.plano === plano.id ? props.contador : null;
        const mapa = props.mapa?.plano === plano.id ? props.mapa : null;
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
              ) : contra ? (
                <Contradiccion
                  arriba={contra.arriba}
                  abajo={contra.abajo}
                  abajoDesde={contra.abajoDesde}
                  resaltar={contra.resaltar}
                  fuente={contra.fuente}
                  navy={navy}
                  gold={gold}
                />
              ) : (
                <>
                  <Tomas plano={plano} duracion={duracion} fichas={props.fichas[plano.id]} navy={navy} gold={gold} />
                  <AbsoluteFill style={{ background: `linear-gradient(to bottom, transparent 52%, ${navy}cc 100%)` }} />
                  {contador || mapa ? null : <Titulo texto={plano.texto} navy={navy} gold={gold} />}
                  {contador ? (
                    // El gancho abre con la cifra a pantalla completa (2.4 s) y luego entran las tomas.
                    <Sequence durationInFrames={Math.min(duracion, Math.round(2.4 * fps))} layout="absolute-fill" name="contador">
                      <Contador numero={contador.numero} antes={contador.antes} despues={contador.despues} navy={navy} gold={gold} />
                    </Sequence>
                  ) : null}
                  {mapa ? (
                    <Sequence
                      from={Math.round(mapa.desde * fps)}
                      durationInFrames={Math.round(mapa.dur * fps)}
                      premountFor={2 * fps}
                      layout="absolute-fill"
                      name="mapa"
                    >
                      <Mapa centro={mapa.centro} etiqueta={mapa.etiqueta} navy={navy} gold={gold} />
                    </Sequence>
                  ) : null}
                </>
              )}
            </Entrada>
          </Sequence>
        );
      })}

      {props.destellos.map((t, i) => (
        <Sequence key={t} from={Math.max(0, Math.round(t * fps) - 12)} durationInFrames={30} layout="absolute-fill" name="destello">
          <Destello seed={i * 7 + 3} />
        </Sequence>
      ))}

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
    </AbsoluteFill>
  );
};
