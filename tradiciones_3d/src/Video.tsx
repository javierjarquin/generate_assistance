import { Audio } from "@remotion/media";
import { ThreeCanvas } from "@remotion/three";
import type { ComponentType } from "react";
import { useMemo } from "react";
import { AbsoluteFill, Img, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import * as E from "./Escenas";
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
/** Evidencia real dentro de una escena (piloto 11/11/2026): la captura con su crédito, como sello. */
export type Evidencia = { img: string; credito: string; desde?: number; hasta?: number };
export type Escena = { id: string; texto: string; visual: Visual[]; camara?: string | CamaraLibre; etiquetas?: Etiqueta[]; claves?: string[];
  evidencia?: Evidencia; ambiente?: string };
export type Palabra = { t: number; f: number; w: string };
/** El gato que se asoma y el cuadro crudo del render plus (06/11/2026): los
 *  mismos props, para que un video con escenas traiga las mismas sorpresas. */
export type Gato = { t: number; dur: number; src: string; lado: "izq" | "der"; y: number; giro: number };
export type Crudo = { t: number; dur: number; src: string };
/** Cierre de marca, el mismo del render plus (Grafico en poc_remotion/src/Escenas.tsx). */
export type Cierre = { desde: number; texto: string; logo?: string | null };
export type TradicionProps = {
  escenas: Escena[];
  tiempos: { duracion: number; escenas: { id: string; ini: number; fin: number }[] };
  palabras: Palabra[];
  audio: string | null;
  /** Piloto de escenas: luz por defecto y marca "Recreación" en cada plano reconstruido. */
  ambiente?: string;
  recreacion?: boolean;
  /** Marca del canal (11/11/2026): el emblema en la esquina y el cierre. */
  logo?: string | null;
  cierre?: Cierre | null;
  gato?: Gato | null;
  crudo?: Crudo | null;
  /** Segundos que dura el corte entre escenas (0 lo apaga). */
  transicion?: number;
};

// La luz de cada mundo. "calido" es la de tradiciones (la de siempre).
type Ambiente = { fondo: string; niebla: [number, number]; amb: [number, string]; sol: [number, string]; relleno: [number, string] };
const AMBIENTES: Record<string, Ambiente> = {
  calido: { fondo: "#0B0705", niebla: [7, 16], amb: [0.55, "#FFE6C7"], sol: [2.4, "#FFE2B0"], relleno: [0.6, "#FF8A3D"] },
  noche: { fondo: "#060A14", niebla: [9, 26], amb: [0.75, "#9FB6E8"], sol: [1.5, "#C9D8FF"], relleno: [0.9, "#FFB15C"] },
  anden: { fondo: "#0D1015", niebla: [10, 28], amb: [1.0, "#E8F0FF"], sol: [2.0, "#FFFFFF"], relleno: [0.5, "#9EC5FF"] },
  oficina: { fondo: "#120F0C", niebla: [8, 20], amb: [0.7, "#FFE9CC"], sol: [2.2, "#FFF1D6"], relleno: [0.5, "#7FA8FF"] },
};

// Lo que cada objeto recibe además de sus props: el tiempo de la escena.
const OBJETOS: Record<string, { c: ComponentType<any>; t?: boolean }> = {
  Flor: { c: O.Flor }, Corona: { c: O.Corona, t: true }, Forma: { c: O.Forma }, Particulas: { c: O.Particulas, t: true },
  Aroma: { c: O.Particulas, t: true }, Sol: { c: O.Sol }, Calendario: { c: O.Calendario }, Lluvia: { c: O.Lluvia, t: true },
  Campo: { c: O.Campo }, Huevo: { c: O.Huevo, t: true }, Raices: { c: O.Raices, t: true }, Camino: { c: O.Camino },
  Ofrenda: { c: O.Ofrenda, t: true }, Velas: { c: O.Velas, t: true }, PapelPicado: { c: O.PapelPicado, t: true }, Piso: { c: O.Piso },
  Modelo: { c: O.Modelo },
  // Piloto de escenas (11/11/2026)
  Personaje: { c: E.Personaje, t: true }, Multitud: { c: E.Multitud, t: true }, Vagon: { c: E.Vagon }, Vias: { c: E.Vias },
  Anden: { c: E.Anden }, Suelo: { c: E.Suelo }, Luz: { c: E.Luz, t: true },
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

/** La captura real (nota, documento) como sello con su crédito: la evidencia no se reconstruye. */
function Sello({ ev, p }: { ev?: Evidencia; p: number }) {
  if (!ev) return null;
  const desde = ev.desde ?? 0.35;
  const hasta = ev.hasta ?? 0.95;
  if (p < desde || p >= hasta) return null;
  const op = Math.min(suave((p - desde) / 0.06), suave((hasta - p) / 0.05));
  return (
    <div style={{ position: "absolute", left: 90, right: 90, top: 640, display: "flex", flexDirection: "column", alignItems: "center",
      opacity: op, transform: `translateY(${(1 - op) * 40}px) rotate(${-2 + op * 1}deg)` }}>
      <div style={{ background: "#FFFFFF", padding: 10, borderRadius: 10, boxShadow: "0 18px 50px rgba(0,0,0,.65)", maxWidth: 800 }}>
        <Img src={staticFile(ev.img)} style={{ display: "block", maxWidth: 780, maxHeight: 640, objectFit: "contain" }} />
      </div>
      <div style={{ marginTop: 12, fontFamily: "Arial, sans-serif", fontWeight: 700, fontSize: 30, color: "#FFD60A",
        textShadow: "0 2px 10px rgba(0,0,0,.9)", background: "rgba(5,8,15,.7)", padding: "6px 16px", borderRadius: 10 }}>
        FUENTE: {ev.credito.toUpperCase()}
      </div>
    </div>
  );
}

/** Marca de las escenas reconstruidas, para que nadie las tome por evidencia. */
function Recreacion() {
  return (
    <div style={{ position: "absolute", top: 200, left: 64, fontFamily: "Arial, sans-serif", fontWeight: 800, fontSize: 28,
      letterSpacing: 4, color: "rgba(255,255,255,.85)", background: "rgba(5,8,15,.55)", border: "2px solid rgba(255,255,255,.35)",
      borderRadius: 8, padding: "6px 14px" }}>RECREACIÓN</div>
  );
}

const MARCA = "Arial Black, Arial, sans-serif";

/** El emblema del canal en la esquina, como en el render plus. Arriba de la
 *  marca "RECREACIÓN" (top 200) y lejos de los subtítulos (top 300). */
function Logo({ src }: { src: string }) {
  return <Img src={staticFile(src)} style={{ position: "absolute", top: 54, left: 40, width: 130, height: 130,
    objectFit: "contain", opacity: 0.85 }} />;
}

/** Corte corto entre escenas: un parpadeo al color del fondo centrado en el
 *  corte. Además tapa el primer cuadro de la escena nueva, donde los modelos
 *  que aún cargan se ven aparecer. */
function Transicion({ cortes, t, dur, color }: { cortes: number[]; t: number; dur: number; color: string }) {
  if (dur <= 0) return null;
  const op = clamp01(cortes.reduce((max, c) => Math.max(max, 1 - Math.abs(t - c) / dur), 0));
  if (op <= 0.02) return null;
  return <div style={{ position: "absolute", inset: 0, background: color, opacity: op }} />;
}

/** El gato del canal se asoma por un costado (06/11/2026, "encuentra al gato").
 *  Girado 90° con la barbilla hacia el borde: de lado mide `alto` de ancho. */
function GatoAsomado({ gato, t }: { gato: Gato; t: number }) {
  const { width } = useVideoConfig();
  const p = (t - gato.t) / Math.max(1e-3, gato.dur);
  if (p < 0 || p > 1) return null;
  const ancho = 300;
  const alto = Math.round(ancho * 0.77);
  const fuera = Math.min(clamp01(p / 0.15), clamp01((1 - p) / 0.15));
  const asomo = alto * 0.7 * fuera;  // asomado enseña orejas, lentes y ojos
  const cx = gato.lado === "izq" ? -alto / 2 + asomo : width + alto / 2 - asomo;
  return (
    <div style={{ position: "absolute", left: cx - ancho / 2, top: gato.y - alto / 2, width: ancho, height: alto,
      transform: `rotate(${gato.lado === "izq" ? 90 - gato.giro : -90 + gato.giro}deg)`,
      filter: "drop-shadow(0 6px 10px rgba(0,0,0,.55))" }}>
      <Img src={staticFile(gato.src)} style={{ width: ancho, height: alto, objectFit: "contain" }} />
    </div>
  );
}

/** Medio segundo de una foto real del tema, en seco y encima de todo. */
function CuadroCrudo({ crudo, t }: { crudo: Crudo; t: number }) {
  if (t < crudo.t || t >= crudo.t + crudo.dur) return null;
  return (
    <div style={{ position: "absolute", inset: 0, background: "#000" }}>
      <Img src={staticFile(crudo.src)} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
    </div>
  );
}

/** Cierre de marca, el mismo de los videos de hoy: fondo azul con las líneas
 *  doradas, el emblema grande y la firma del canal. Va encima de la escena, en
 *  la franja que dejan libres los subtítulos (arriba) y el letrero (1330). */
function CierreMarca({ cierre, t }: { cierre: Cierre; t: number }) {
  const { width } = useVideoConfig();
  const p = t - cierre.desde;
  if (p < 0) return null;
  const entra = suave(clamp01(p / 0.5));
  const texto = suave(clamp01((p - 0.35) / 0.5));
  const firma = clamp01((p - 0.8) / 0.4);
  return (
    <AbsoluteFill style={{ background: "radial-gradient(circle at 50% 42%, #16335F 0%, #0B1F3A 62%)",
      opacity: clamp01(p / 0.25) }}>
      {[0, 1, 2, 3, 4, 5].map((i) => (
        <div key={i} style={{ position: "absolute", left: -200, width: width + 400, height: 6, top: 300 + i * 260,
          background: "#D4A537", opacity: 0.12, transform: `rotate(-14deg) translateX(${-120 + i * 30 + p * 36}px)` }} />
      ))}
      {cierre.logo && (
        <Img src={staticFile(cierre.logo)} style={{ position: "absolute", top: 620, left: width / 2 - 180, width: 360,
          height: 360, objectFit: "contain", transform: `scale(${lerp(0.3, 1, entra)})`, opacity: entra }} />
      )}
      {cierre.texto && (
        <div style={{ position: "absolute", top: 1030, left: 80, right: 80, textAlign: "center", fontFamily: MARCA,
          fontWeight: 900, fontSize: cierre.texto.length > 30 ? 72 : 96, lineHeight: 1.04, color: "#D4A537",
          textTransform: "uppercase", opacity: texto, transform: `translateY(${(1 - texto) * 50}px)` }}>
          {cierre.texto}
        </div>
      )}
      <div style={{ position: "absolute", top: 1430, width: "100%", textAlign: "center", fontFamily: MARCA,
        fontSize: 52, color: "#FFFFFF", letterSpacing: 4, opacity: firma * 0.9 }}>
        DATO MATA GATO
      </div>
    </AbsoluteFill>
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
  // El espacio entre palabra y palabra es de verdad (11/11/2026): sin él, los
  // <span> pegados no dan dónde partir el renglón y una frase larga
  // ("fotoperiodista Rubén Espinosa") se salía del cuadro por la derecha.
  const letras = frase.reduce((n, w) => n + w.w.length + 1, 0);
  return (
    <div style={{ position: "absolute", top: 300, left: 80, right: 80, textAlign: "center", fontFamily: "Arial, sans-serif",
      fontWeight: 800, fontSize: letras > 22 ? 50 : 60, lineHeight: 1.25, textShadow: "0 3px 18px rgba(0,0,0,.85)" }}>
      <span style={{ display: "inline-block", maxWidth: "100%", background: "rgba(11,7,5,.62)", borderRadius: 22,
        padding: "10px 14px" }}>
      {frase.map((w, i) => {
        const dicha = t >= w.t - 0.03;
        const clave = claves.has(limpia(w.w));
        return (
          <span key={i}>
            <span style={{ color: dicha ? (clave ? "#1A0E05" : "#FFFFFF") : "rgba(255,255,255,.35)",
              background: dicha && clave ? "#FFB020" : "transparent", padding: "0 10px", borderRadius: 10 }}>
              {w.w}
            </span>
            {i < frase.length - 1 ? " " : ""}
          </span>
        );
      })}
      </span>
    </div>
  );
}

export function Tradicion({ escenas, tiempos, palabras, audio, ambiente, recreacion, logo, cierre, gato, crudo,
  transicion = 0 }: TradicionProps) {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const t = frame / fps;
  const lista = useMemo(() => frases(palabras), [palabras]);
  const claves = useMemo(() => new Set(escenas.flatMap((e) => (e.claves ?? []).map(limpia))), [escenas]);
  const marcas = tiempos.escenas;
  // Los cortes entre escenas; el primero (0) hace la entrada del video.
  const cortes = useMemo(() => marcas.map((m) => m.ini), [marcas]);
  let i = marcas.findIndex((_, k) => t < (marcas[k + 1]?.ini ?? Infinity));
  if (i < 0) i = marcas.length - 1;
  const fin = marcas[i + 1]?.ini ?? tiempos.duracion + 1;
  const p = clamp01((t - marcas[i].ini) / (fin - marcas[i].ini));
  const e = escenas.find((x) => x.id === marcas[i].id) ?? escenas[i];
  const a = AMBIENTES[e.ambiente ?? ambiente ?? "calido"] ?? AMBIENTES.calido;
  const enCierre = !!cierre && t >= cierre.desde;
  return (
    <AbsoluteFill style={{ backgroundColor: a.fondo }}>
      <ThreeCanvas width={width} height={height} camera={{ fov: 40, near: 0.1, far: 80 }}>
        <color attach="background" args={[a.fondo]} />
        <fog attach="fog" args={[a.fondo, a.niebla[0], a.niebla[1]]} />
        <ambientLight intensity={a.amb[0]} color={a.amb[1]} />
        <directionalLight position={[2.5, 5, 4]} intensity={a.sol[0]} color={a.sol[1]} />
        <directionalLight position={[-3, 1, -2]} intensity={a.relleno[0]} color={a.relleno[1]} />
        <Mundo e={e} p={p} t={t - marcas[i].ini} />
      </ThreeCanvas>
      <Sello ev={e.evidencia} p={p} />
      <Letrero etiquetas={e.etiquetas} p={p} />
      <Transicion cortes={cortes} t={t} dur={transicion} color={a.fondo} />
      {/* El cierre tapa la escena: ahí ya no hay nada reconstruido que marcar. */}
      {cierre && <CierreMarca cierre={cierre} t={t} />}
      <Subtitulos t={t} lista={lista} claves={claves} />
      {!enCierre && logo && <Logo src={logo} />}
      {!enCierre && recreacion && <Recreacion />}
      {gato && <GatoAsomado gato={gato} t={t} />}
      {/* Encima de todo (subtítulos y logo incluidos): el cuadro va crudo. */}
      {crudo && <CuadroCrudo crudo={crudo} t={t} />}
      {audio && <Audio src={staticFile(audio)} />}
    </AbsoluteFill>
  );
}
