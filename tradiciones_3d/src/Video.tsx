import { Audio } from "@remotion/media";
import { ThreeCanvas } from "@remotion/three";
import type { ComponentType } from "react";
import { useMemo } from "react";
import { AbsoluteFill, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import * as O from "./Objetos";
import { clamp01, lerp, suave } from "./Objetos";

// El guion trae, por escena, qué se ve (escenas declarativas, 30/10/2026). El
// POC del cempasúchil tenía un switch escrito a mano por tema; esto lo lee.

/** Un número que cambia dentro de la escena: de `de` a `a` entre `desde` y
 *  `hasta` (0 = empieza la escena, 1 = termina). Con `regresa`, vuelve a `de`. */
export type Anim = { de: number | number[]; a: number | number[]; desde?: number; hasta?: number; regresa?: [number, number] };
export type Visual = { objeto: string; posicion?: unknown; escala?: unknown; rotacion?: unknown; gira?: number; [prop: string]: unknown };
type Toma = { pos: number[]; mira: number[] };
export type CamaraLibre = Toma | { desde: Toma; hasta: Toma; entre?: [number, number] };
export type Etiqueta = { titulo: string; subtitulo?: string; desde: number; hasta: number };
export type Escena = { id: string; texto: string; visual: Visual[]; camara?: string | CamaraLibre; etiquetas?: Etiqueta[]; claves?: string[] };
export type Palabra = { t: number; f: number; w: string };
export type TradicionProps = {
  escenas: Escena[];
  tiempos: { duracion: number; escenas: { id: string; ini: number; fin: number }[] };
  palabras: Palabra[];
  audio: string | null;
};

// Lo que cada objeto recibe además de sus props: el tiempo de la escena.
const OBJETOS: Record<string, { c: ComponentType<any>; t?: boolean }> = {
  Flor: { c: O.Flor }, Corona: { c: O.Corona, t: true }, Forma: { c: O.Forma }, Particulas: { c: O.Particulas, t: true },
  Aroma: { c: O.Particulas, t: true }, Sol: { c: O.Sol }, Calendario: { c: O.Calendario }, Lluvia: { c: O.Lluvia, t: true },
  Campo: { c: O.Campo }, Huevo: { c: O.Huevo, t: true }, Raices: { c: O.Raices, t: true }, Camino: { c: O.Camino },
  Ofrenda: { c: O.Ofrenda, t: true }, Velas: { c: O.Velas, t: true }, PapelPicado: { c: O.PapelPicado, t: true }, Piso: { c: O.Piso },
  Modelo: { c: O.Modelo },
};
const DEL_GRUPO = new Set(["objeto", "posicion", "escala", "rotacion", "gira"]);

const esAnim = (v: unknown): v is Anim => !!v && typeof v === "object" && !Array.isArray(v) && "de" in v && "a" in v;

export function valor(v: unknown, p: number): unknown {
  if (!esAnim(v)) return v;
  const desde = v.desde ?? 0;
  const hasta = v.hasta ?? 1;
  let k = suave((p - desde) / Math.max(1e-3, hasta - desde));
  if (v.regresa) k *= 1 - suave((p - v.regresa[0]) / Math.max(1e-3, v.regresa[1] - v.regresa[0]));
  if (Array.isArray(v.de) && Array.isArray(v.a)) return v.de.map((d, i) => lerp(d, (v.a as number[])[i] ?? d, k));
  return lerp(Number(v.de), Number(v.a), k);
}

// Las tomas de cámara del POC, con nombre. La Ofrenda y el fondo del Camino
// están en z = -7; el objeto protagonista en el centro.
const CAMARAS: Record<string, (p: number) => Toma> = {
  frente: () => ({ pos: [0, 0.35, 6.3], mira: [0, 0.1, 0] }),
  acerca: (p) => ({ pos: [0, 0.35, lerp(7.6, 6.3, suave(p))], mira: [0, 0, 0] }),
  aleja: (p) => ({ pos: [0, 0.3, lerp(6.3, 7.6, suave((p - 0.4) / 0.4))], mira: [0, 0, 0] }),
  cerca: () => ({ pos: [0, 0.15, 4.2], mira: [0, -0.1, 0] }),
  plano: () => ({ pos: [0, 0, 5.6], mira: [0, 0, 0] }),
  arriba: () => ({ pos: [0, 1.9, 3.9], mira: [0, 0.35, 0] }),
  campo: () => ({ pos: [0, 1.4, 5.6], mira: [0, -0.9, -0.5] }),
  suelo: () => ({ pos: [0, 0.9, 6.8], mira: [0, -0.5, 1] }),
  recorre: (p) => ({ pos: [0, lerp(0.9, 0.5, suave(p)), lerp(6.8, -1.2, suave(p))], mira: [0, -0.4, -7] }),
  eleva: (p) => ({ pos: [0, lerp(0.5, 2.6, suave(p)), lerp(-1.2, 4.5, suave(p))], mira: [0, -0.6, -6] }),
  orbita: (p) => {
    const a = lerp(-0.5, 0.5, suave(p));
    return { pos: [Math.sin(a) * 6.3, 0.6, Math.cos(a) * 6.3], mira: [0, 0, 0] };
  },
};

function toma(camara: Escena["camara"], p: number): Toma {
  if (!camara) return CAMARAS.frente(p);
  if (typeof camara === "string") return (CAMARAS[camara] ?? CAMARAS.frente)(p);
  if ("desde" in camara) {
    const [a, b] = camara.entre ?? [0, 1];
    const k = suave((p - a) / Math.max(1e-3, b - a));
    return { pos: camara.desde.pos.map((x, i) => lerp(x, camara.hasta.pos[i], k)),
      mira: camara.desde.mira.map((x, i) => lerp(x, camara.hasta.mira[i], k)) };
  }
  return camara;
}

function Objeto({ v, p, t }: { v: Visual; p: number; t: number }) {
  const def = OBJETOS[v.objeto];
  if (!def) return null;
  const props: Record<string, unknown> = {};
  for (const [k, x] of Object.entries(v)) if (!DEL_GRUPO.has(k)) props[k] = valor(x, p);
  if (v.gira) props.giro = Number(props.giro ?? 0) + t * v.gira;
  if (def.t) props.t = t;
  const escala = valor(v.escala ?? 1, p);
  const C = def.c;
  return (
    <group position={(valor(v.posicion ?? [0, 0, 0], p) as [number, number, number])}
      rotation={(valor(v.rotacion ?? [0, 0, 0], p) as [number, number, number])}
      scale={escala as number | [number, number, number]}>
      <C {...props} />
    </group>
  );
}

function Mundo({ e, p, t }: { e: Escena; p: number; t: number }) {
  const c = toma(e.camara, p);
  return <>
    <O.Camara pos={c.pos} mira={c.mira} />
    {e.visual.map((v, i) => <Objeto key={`${e.id}-${i}`} v={v} p={p} t={t} />)}
  </>;
}

function Letrero({ etiquetas, p }: { etiquetas?: Etiqueta[]; p: number }) {
  const e = (etiquetas ?? []).find((x) => p >= x.desde && p < x.hasta);
  if (!e) return null;
  const op = Math.min(suave((p - e.desde) / 0.05), suave((e.hasta - p) / 0.05));
  return (
    <div style={{ position: "absolute", top: 1330, left: 90, right: 90, textAlign: "center", opacity: op, background: "rgba(11,7,5,.62)", borderRadius: 24, padding: "22px 20px",
      transform: `translateY(${(1 - op) * 20}px)` }}>
      <div style={{ display: "inline-block", fontFamily: "Arial Black, Arial, sans-serif", fontWeight: 900,
        fontSize: e.titulo.length > 18 ? 54 : 72, color: "#FFB020", letterSpacing: 2, textShadow: "0 4px 24px rgba(0,0,0,.8)",
        borderBottom: "6px solid #FFB020", paddingBottom: 8 }}>{e.titulo.toUpperCase()}</div>
      {e.subtitulo && <div style={{ marginTop: 18, fontFamily: "Arial, sans-serif", fontSize: 40, color: "#F3E6D3",
        textShadow: "0 3px 16px rgba(0,0,0,.9)" }}>{e.subtitulo}</div>}
    </div>
  );
}

const limpia = (w: string) => w.toLowerCase().replace(/[¿?¡!.,:;«»"]/g, "");

/** Frases de hasta 3 palabras, cortando en la puntuación y en las pausas. */
function frases(palabras: Palabra[]): Palabra[][] {
  const out: Palabra[][] = [];
  for (const w of palabras) {
    const ultima = out[out.length - 1];
    const prev = ultima?.[ultima.length - 1];
    if (!ultima || ultima.length >= 3 || /[.,?:;]$/.test(prev.w) || w.t - prev.f > 0.45) out.push([w]);
    else ultima.push(w);
  }
  return out;
}

function Subtitulos({ t, lista, claves }: { t: number; lista: Palabra[][]; claves: Set<string> }) {
  const frase = lista.find((f, i) => t >= f[0].t - 0.05 && t < (lista[i + 1]?.[0].t ?? f[f.length - 1].f + 0.6) - 0.05);
  if (!frase) return null;
  // Con fondo propio: un objeto armado con Forma puede subir hasta esta franja
  // (el papelito de la calaverita, 30/10/2026) y sin fondo no se leía.
  return (
    <div style={{ position: "absolute", top: 300, left: 80, right: 80, textAlign: "center", fontFamily: "Arial, sans-serif",
      fontWeight: 800, fontSize: 60, lineHeight: 1.25, textShadow: "0 3px 18px rgba(0,0,0,.85)" }}>
      <span style={{ display: "inline-block", background: "rgba(11,7,5,.62)", borderRadius: 22, padding: "10px 14px" }}>
      {frase.map((w, i) => {
        const dicha = t >= w.t - 0.03;
        const clave = claves.has(limpia(w.w));
        return (
          <span key={i} style={{ color: dicha ? (clave ? "#1A0E05" : "#FFFFFF") : "rgba(255,255,255,.35)",
            background: dicha && clave ? "#FFB020" : "transparent", padding: "0 10px", borderRadius: 10, marginRight: 4 }}>
            {w.w}
          </span>
        );
      })}
      </span>
    </div>
  );
}

export function Tradicion({ escenas, tiempos, palabras, audio }: TradicionProps) {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const t = frame / fps;
  const lista = useMemo(() => frases(palabras), [palabras]);
  const claves = useMemo(() => new Set(escenas.flatMap((e) => (e.claves ?? []).map(limpia))), [escenas]);
  const marcas = tiempos.escenas;
  let i = marcas.findIndex((_, k) => t < (marcas[k + 1]?.ini ?? Infinity));
  if (i < 0) i = marcas.length - 1;
  const fin = marcas[i + 1]?.ini ?? tiempos.duracion + 1;
  const p = clamp01((t - marcas[i].ini) / (fin - marcas[i].ini));
  const e = escenas.find((x) => x.id === marcas[i].id) ?? escenas[i];
  return (
    <AbsoluteFill style={{ backgroundColor: "#0B0705" }}>
      <ThreeCanvas width={width} height={height} camera={{ fov: 40, near: 0.1, far: 60 }}>
        <color attach="background" args={["#0B0705"]} />
        <fog attach="fog" args={["#0B0705", 7, 16]} />
        <ambientLight intensity={0.55} color="#FFE6C7" />
        <directionalLight position={[2.5, 5, 4]} intensity={2.4} color="#FFE2B0" />
        <directionalLight position={[-3, 1, -2]} intensity={0.6} color="#FF8A3D" />
        <Mundo e={e} p={p} t={t - marcas[i].ini} />
      </ThreeCanvas>
      <Letrero etiquetas={e.etiquetas} p={p} />
      <Subtitulos t={t} lista={lista} claves={claves} />
      {audio && <Audio src={staticFile(audio)} />}
    </AbsoluteFill>
  );
}
