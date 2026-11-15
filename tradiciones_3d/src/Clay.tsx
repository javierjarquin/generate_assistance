// Estilo "plastilina kawaii pastel" del canal papasia (15/11/2026). La
// referencia de Javier: un malvavisco con carita sentado en una nube rosa.
// Las reglas (están también en .claude/skills/clay-kawaii):
//   1. formas gorditas, sin esquinas: esferas, cápsulas, tornos y cajas redondeadas;
//   2. material mate (roughness ~0.8), un poco de luz propia que hace de
//      "subsurface", y un relieve de ruido muy sutil (bumpMap) de plastilina;
//   3. solo pasteles: cualquier color que traiga el guion se pasteliza;
//   4. luz de estudio difusa con sombras suaves y el fondo desenfocado (miniatura);
//   5. cada parte es su propio grupo con el origen en la articulación, para
//      animar rebotes (squash & stretch).
// Bebe, Cuna y Biberon solo existen aquí. Calendario, Sol, Particulas y Forma
// tienen su versión de plastilina, que Video.tsx usa cuando el ambiente es claro.
import { useMemo } from "react";
import { random } from "remotion";
import * as THREE from "three";
import { RoundedBoxGeometry } from "three/examples/jsm/geometries/RoundedBoxGeometry.js";
import { clamp01, lerp, suave } from "./Objetos";

// --- Paleta ---------------------------------------------------------------------
export const PASTEL = {
  crema: "#FFF4E6", piel: "#FFEBDD", rosa: "#FFC2D4", rosaFuerte: "#FF9DB5", azul: "#BFE0F7",
  mantequilla: "#FFE9A8", menta: "#CFF0DC", lila: "#DCCBF5", durazno: "#FFD3BA", blanco: "#FFFDFA",
  tinta: "#5B4250",
};
/** El fondo del cuadro: va en CSS, detrás de los dos lienzos. */
export const FONDO_CSS = "radial-gradient(circle at 50% 40%, #FFFBF4 0%, #FFF0EC 42%, #FBDCE6 100%)";
export const FONDO = "#FFE6EC";

const _c = new THREE.Color();
const _hsl = { h: 0, s: 0, l: 0 };
/** Cualquier color, en pastel: mismo tono, menos saturación y mucha luz. */
export function pastel(color: string, luz = 0.82): string {
  _c.set(color).getHSL(_hsl);
  _c.setHSL(_hsl.h, Math.min(_hsl.s, 0.7) * 0.85, lerp(luz, 0.9, clamp01((_hsl.l - 0.5) * 2) * 0.5));
  return `#${_c.getHexString()}`;
}

// --- El relieve de plastilina -----------------------------------------------------
const hash = (x: number, y: number, s: number) => {
  const v = Math.sin(x * 127.1 + y * 311.7 + s * 74.7) * 43758.5453;
  return v - Math.floor(v);
};
function ruido(u: number, v: number, periodo: number, s: number) {
  const x = u * periodo, y = v * periodo;
  const xi = Math.floor(x), yi = Math.floor(y);
  const fx = suave(x - xi), fy = suave(y - yi);
  const h = (a: number, b: number) => hash(((a % periodo) + periodo) % periodo, ((b % periodo) + periodo) % periodo, s);
  return lerp(lerp(h(xi, yi), h(xi + 1, yi), fx), lerp(h(xi, yi + 1), h(xi + 1, yi + 1), fx), fy);
}
let _relieve: THREE.DataTexture | null = null;
/** Ruido que se repite sin costura: huellitas grandes y grano fino. */
function relieve(): THREE.DataTexture {
  if (_relieve) return _relieve;
  const n = 256;
  const data = new Uint8Array(n * n * 4);
  for (let j = 0; j < n; j++) for (let i = 0; i < n; i++) {
    const u = i / n, v = j / n;
    const x = 0.55 * ruido(u, v, 5, 1) + 0.3 * ruido(u, v, 13, 2) + 0.15 * ruido(u, v, 37, 3);
    const g = Math.round(255 * x);
    data.set([g, g, g, 255], (j * n + i) * 4);
  }
  const t = new THREE.DataTexture(data, n, n, THREE.RGBAFormat);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(3, 3);
  t.magFilter = THREE.LinearFilter;
  t.minFilter = THREE.LinearMipmapLinearFilter;
  t.generateMipmaps = true;
  t.needsUpdate = true;
  _relieve = t;
  return t;
}

/** El material de todo: mate, con un poco de luz propia y relieve de plastilina. */
export function Arcilla({ color, brillo = 0, opacidad = 1, relieveFuerza = 1 }: {
  color: string; brillo?: number; opacidad?: number; relieveFuerza?: number;
}) {
  return (
    <meshPhysicalMaterial color={color} roughness={0.82} metalness={0} bumpMap={relieve()} bumpScale={2.4 * relieveFuerza}
      sheen={0.55} sheenRoughness={0.75} sheenColor="#FFFFFF" emissive={color} emissiveIntensity={0.1 + brillo * 0.07}
      transparent={opacidad < 1} opacity={opacidad} />
  );
}

/** Tinta de la carita: lisa y sin sombra, como pintada encima. */
const Tinta = ({ color = PASTEL.tinta, opacidad = 1 }: { color?: string; opacidad?: number }) => (
  <meshBasicMaterial color={color} transparent={opacidad < 1} opacity={opacidad} />
);

type V3 = [number, number, number];
const ESFERA = new THREE.SphereGeometry(1, 40, 28);
/** Una bola de plastilina (o un huevo, con `s` de tres números). */
function Bola({ p = [0, 0, 0], s = 1, r, color, brillo, opacidad, sombra = true }: {
  p?: V3; s?: number | V3; r?: V3; color: string; brillo?: number; opacidad?: number; sombra?: boolean;
}) {
  return (
    <mesh geometry={ESFERA} position={p} scale={s} rotation={r} castShadow={sombra} receiveShadow>
      <Arcilla color={color} brillo={brillo} opacidad={opacidad} />
    </mesh>
  );
}

const _cajas = new Map<string, THREE.BufferGeometry>();
function geoCaja(t: V3, radio: number) {
  const k = `${t.join()}|${radio}`;
  if (!_cajas.has(k)) _cajas.set(k, new RoundedBoxGeometry(t[0], t[1], t[2], 6, radio));
  return _cajas.get(k)!;
}
/** Una caja de malvavisco: todas las esquinas redondas. */
function Caja({ p = [0, 0, 0], t, radio = 0.08, color, brillo }: { p?: V3; t: V3; radio?: number; color: string; brillo?: number }) {
  return (
    <mesh geometry={geoCaja(t, Math.min(radio, Math.min(...t) / 2 - 0.001))} position={p} castShadow receiveShadow>
      <Arcilla color={color} brillo={brillo} />
    </mesh>
  );
}

/** Un rollito: cápsula de `a` a `b`. */
function Rollo({ a, b, radio, color, brillo }: { a: V3; b: V3; radio: number; color: string; brillo?: number }) {
  const { pos, q, largo } = useMemo(() => {
    const va = new THREE.Vector3(...a), vb = new THREE.Vector3(...b);
    const d = vb.clone().sub(va);
    return { pos: va.clone().add(vb).multiplyScalar(0.5), largo: d.length(),
      q: new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), d.clone().normalize()) };
  }, [a.join(), b.join()]);
  return (
    <mesh position={pos} quaternion={q} castShadow receiveShadow>
      <capsuleGeometry args={[radio, largo, 6, 16]} />
      <Arcilla color={color} brillo={brillo} />
    </mesh>
  );
}

/** Un sólido de torno a partir de su perfil (radio, altura), suavizado. */
function torno(perfil: [number, number][], vueltas = 40) {
  const curva = new THREE.SplineCurve(perfil.map(([x, y]) => new THREE.Vector2(x, y)));
  return new THREE.LatheGeometry(curva.getPoints(48), vueltas);
}

function estrella(puntas = 5, r1 = 1, r0 = 0.52) {
  const s = new THREE.Shape();
  for (let i = 0; i < puntas * 2; i++) {
    const a = (i / (puntas * 2)) * Math.PI * 2 + Math.PI / 2;
    const r = i % 2 ? r0 : r1;
    if (i) s.lineTo(Math.cos(a) * r, Math.sin(a) * r); else s.moveTo(Math.cos(a) * r, Math.sin(a) * r);
  }
  s.closePath();
  const g = new THREE.ExtrudeGeometry(s, { depth: 0.16, bevelEnabled: true, bevelSize: 0.22, bevelThickness: 0.2, bevelSegments: 6, curveSegments: 4 });
  g.center();
  return g;
}
const ESTRELLA = estrella();

function corazon() {
  const s = new THREE.Shape();
  s.moveTo(0, -0.7);
  s.bezierCurveTo(-1.3, 0.1, -0.75, 1.05, 0, 0.42);
  s.bezierCurveTo(0.75, 1.05, 1.3, 0.1, 0, -0.7);
  const g = new THREE.ExtrudeGeometry(s, { depth: 0.14, bevelEnabled: true, bevelSize: 0.16, bevelThickness: 0.16, bevelSegments: 6, curveSegments: 18 });
  g.center();
  return g;
}
const CORAZON = corazon();

/** Estrellita gordita. */
export function Estrella({ p, s = 0.2, color = PASTEL.mantequilla, giro = 0, sombra = false }: { p: V3; s?: number; color?: string; giro?: number; sombra?: boolean }) {
  return (
    <mesh geometry={ESTRELLA} position={p} scale={s} rotation={[0, 0, giro]} castShadow={sombra}>
      <Arcilla color={color} />
    </mesh>
  );
}

// Una nube: bolas pegadas. Cada bola: [x, y, z, radio].
const NUBE: [number, number, number, number][] = [
  [0, 0, 0, 0.5], [-0.48, -0.08, 0.02, 0.38], [0.5, -0.1, 0, 0.36], [-0.2, 0.2, -0.05, 0.36], [0.24, 0.16, 0.05, 0.34],
  [-0.82, -0.16, 0, 0.24], [0.84, -0.18, 0, 0.22],
];
export function Nube({ p = [0, 0, 0], s = 1, color = PASTEL.blanco, sombra = false }: { p?: V3; s?: number | V3; color?: string; sombra?: boolean }) {
  return (
    <group position={p} scale={s}>
      {NUBE.map(([x, y, z, r], i) => <Bola key={i} p={[x, y * 0.8, z]} s={[r, r * 0.82, r * 0.8]} color={color} sombra={sombra} />)}
    </group>
  );
}

// --- Luz y decorado ----------------------------------------------------------------
/** Estudio difuso: cielo y suelo claros, una luz principal suave con sombra
 *  blanda y un contraluz rosa que despega la figura del fondo. */
export function Luces({ sombras = true, relleno = 0 }: { sombras?: boolean; relleno?: number }) {
  return <>
    {relleno > 0 && <ambientLight intensity={relleno} color="#FFFFFF" />}
    <hemisphereLight args={["#FFFFFF", "#F3B9CD", 1.55]} />
    {/* casi cenital: la sombra cae debajo de la figura, no a un lado */}
    <directionalLight position={[-0.9, 9, 2.4]} intensity={1.15} color="#FFF6EC" castShadow={sombras}
      shadow-mapSize={[1024, 1024]} shadow-radius={9} shadow-bias={-0.0006} shadow-normalBias={0.05}>
      <orthographicCamera attach="shadow-camera" args={[-4.5, 4.5, 4.5, -4.5, 0.5, 24]} />
    </directionalLight>
    <directionalLight position={[3.5, 2.5, -4]} intensity={0.8} color="#FFC2D8" />
    <directionalLight position={[2.5, 1, 5]} intensity={0.3} color="#D6ECFF" />
  </>;
}

// El cojín: una nube rosa grande donde se sienta lo que salga en la escena. Lo
// que es más grande que el encuadre se hunde un poco en ella, como en algodón.
const COJIN: [number, number, number, number][] = [
  [0, -1.92, 0.1, 1.0], [-0.95, -1.98, 0.25, 0.86], [0.98, -1.97, 0.2, 0.84], [-1.85, -2.05, 0, 0.8], [1.9, -2.04, 0.05, 0.78],
  [-0.5, -2.0, 0.95, 0.72], [0.55, -2.02, 0.9, 0.7], [-1.45, -2.1, 0.8, 0.66], [1.5, -2.1, 0.78, 0.64], [0, -2.0, -0.85, 0.95],
  [-1.2, -2.02, -0.8, 0.9], [1.25, -2.03, -0.82, 0.88], [-2.7, -2.15, 0.2, 0.7], [2.75, -2.15, 0.2, 0.7], [-2.4, -2.1, -0.9, 0.85],
  [2.45, -2.1, -0.9, 0.85], [0, -2.15, 1.6, 0.6], [-1.1, -2.2, 1.55, 0.55], [1.1, -2.2, 1.55, 0.55],
];
export function Cojin() {
  return (
    <group>
      {COJIN.map(([x, y, z, r], i) => <Bola key={i} p={[x, y, z]} s={[r, r * 0.9, r]} color={i % 5 === 3 ? "#FFCBDA" : "#FFB9CE"} sombra={false} />)}
    </group>
  );
}

// Lo que flota atrás, fuera de foco: nubes, estrellas y un arcoíris. `t` es el
// tiempo del video (no el de la escena), para que no brinque en cada corte.
const ARCO = [PASTEL.rosaFuerte, PASTEL.mantequilla, PASTEL.menta, PASTEL.azul];
export function Decorado({ t }: { t: number }) {
  const sube = (i: number, a = 0.08) => Math.sin(t * 0.7 + i * 1.7) * a;
  return (
    <group>
      <group position={[2.0, 1.15 + sube(1), -4.6]} rotation={[0, -0.25, 0.08]}>
        {ARCO.map((c, i) => (
          <mesh key={c} rotation={[0, 0, 0]}>
            <torusGeometry args={[0.95 - i * 0.17, 0.085, 12, 40, Math.PI]} />
            <Arcilla color={c} />
          </mesh>
        ))}
        <Nube p={[-0.72, -0.02, 0.1]} s={0.42} />
        <Nube p={[0.72, -0.02, 0.1]} s={0.42} />
      </group>
      <Nube p={[-2.3, 2.0 + sube(2), -5]} s={1.0} />
      <Nube p={[-2.5, -0.5 + sube(3), -4.2]} s={0.75} />
      <Nube p={[2.6, -0.9 + sube(4), -5.2]} s={0.9} />
      <Nube p={[4.6, 1.9 + sube(5), -6]} s={1.2} />
      <Nube p={[-4.8, 0.9 + sube(6), -6]} s={1.2} />
      <Nube p={[0.4, 3.3 + sube(7), -6.5]} s={1.1} />
      {[[-1.75, 1.05, -3.6, 0.2, PASTEL.mantequilla], [1.5, 2.55, -4.4, 0.15, PASTEL.mantequilla], [-0.9, 2.75, -5, 0.13, PASTEL.rosaFuerte],
        [2.35, 0.15, -3.8, 0.12, PASTEL.lila], [-2.3, -1.45, -3.4, 0.14, PASTEL.mantequilla], [3.6, 0.8, -5, 0.2, PASTEL.mantequilla],
        [-3.7, 2.2, -5.2, 0.18, PASTEL.lila], [-3.6, -0.6, -5, 0.16, PASTEL.rosaFuerte]].map(([x, y, z, s, c], i) => (
        <Estrella key={i} p={[x as number, (y as number) + sube(i + 9, 0.12), z as number]} giro={Math.sin(t * 0.9 + i) * 0.3}
          s={(s as number) * (1 + Math.sin(t * 2.2 + i * 2.1) * 0.08)} color={c as string} />
      ))}
      {[[-1.2, 0.2, -4.2, PASTEL.azul], [1.25, -0.35, -4, PASTEL.rosaFuerte], [0.9, 1.9, -5.2, PASTEL.menta], [-0.3, -1.1, -4.6, PASTEL.lila]].map(([x, y, z, c], i) => (
        <Bola key={i} p={[x as number, (y as number) + sube(i + 20, 0.15), z as number]} s={0.09} color={c as string} sombra={false} />
      ))}
    </group>
  );
}

// --- La carita ---------------------------------------------------------------------
const ARCO_CARA = new THREE.TorusGeometry(1, 0.2, 10, 24, Math.PI);

/** Dónde queda un punto (x, y) sobre un huevo de radios `r`, y hacia dónde mira. */
function enHuevo(r: V3, x: number, y: number, sale = 0): { position: V3; rotation: V3 } {
  const z = r[2] * Math.sqrt(Math.max(0, 1 - (x / r[0]) ** 2 - (y / r[1]) ** 2));
  const n = new THREE.Vector3(x / r[0] ** 2, y / r[1] ** 2, z / r[2] ** 2).normalize();
  return { position: [x + n.x * sale, y + n.y * sale, z + n.z * sale], rotation: [-Math.asin(n.y), Math.atan2(n.x, n.z), 0] };
}

/** Carita kawaii sobre un huevo de radios `r`: ojos de punto muy separados,
 *  chapitas y una boca chiquita. duerme: ojos de media luna. llora: ojos
 *  apretados (> <), lágrimas y boca abierta. `t` hace parpadear. */
function Carita({ r, t = 0, duerme = 0, llora = 0, y0 = 0, tam = 1 }: { r: V3; t?: number; duerme?: number; llora?: number; y0?: number; tam?: number }) {
  const d = clamp01(duerme), l = clamp01(llora);
  const aprieta = suave((l - 0.35) / 0.2);          // de inquieto a llanto abierto
  const abiertos = (1 - suave(d / 0.6)) * (1 - aprieta);
  const fase = (t % 3.4) / 3.4;
  const parpadeo = fase > 0.955 ? 0.12 : 1;
  const ex = 0.4 * r[0], ey = y0 - 0.02 * r[1];
  return (
    <group>
      {[-1, 1].map((lado) => {
        const ojo = enHuevo(r, lado * ex, ey, 0.004);
        return (
          <group key={lado} position={ojo.position} rotation={ojo.rotation}>
            {abiertos > 0.02 && (
              <group scale={[abiertos, abiertos * parpadeo, 1]}>
                <mesh geometry={ESFERA} scale={[0.047 * tam, 0.055 * tam, 0.02]}><Tinta /></mesh>
                <mesh geometry={ESFERA} position={[-0.014 * tam, 0.02 * tam, 0.02]} scale={0.014 * tam}><Tinta color="#FFFFFF" /></mesh>
              </group>
            )}
            {/* dormido: media luna hacia abajo */}
            {d > 0.4 && aprieta < 0.5 && (
              <mesh geometry={ARCO_CARA} rotation={[0, 0, Math.PI]} position={[0, 0.012 * tam, 0.004]} scale={0.05 * tam * suave((d - 0.4) / 0.3)}><Tinta /></mesh>
            )}
            {/* llanto: ojos apretados, > de un lado y < del otro */}
            {aprieta > 0.02 && [-1, 1].map((k) => (
              <mesh key={k} position={[lado * 0.008 * tam, k * 0.02 * tam, 0.004]} rotation={[0, 0, k * lado * 0.5]} scale={[0.055 * tam * aprieta, 0.012 * tam, 0.012]}>
                <capsuleGeometry args={[1, 1.4, 4, 10]} />
                <Tinta />
              </mesh>
            ))}
            {/* cejitas de apuro */}
            {l > 0.15 && (
              <mesh position={[0, 0.1 * tam, 0.002]} rotation={[0, 0, -lado * 0.45]} scale={[0.036 * tam, 0.009 * tam, 0.01]}>
                <capsuleGeometry args={[1, 1.4, 4, 10]} />
                <Tinta opacidad={clamp01((l - 0.15) * 4)} />
              </mesh>
            )}
          </group>
        );
      })}
      {/* chapitas */}
      {[-1, 1].map((lado) => {
        const c = enHuevo(r, lado * 0.6 * r[0], ey - 0.2 * r[1], 0.002);
        return (
          <mesh key={lado} geometry={ESFERA} position={c.position} rotation={c.rotation} scale={[0.085 * tam, 0.055 * tam, 0.012]}>
            <Tinta color={l > 0.3 ? "#FF7F96" : PASTEL.rosaFuerte} opacidad={0.75} />
          </mesh>
        );
      })}
      {/* lágrimas gorditas que resbalan */}
      {aprieta > 0.3 && [-1, 1].map((lado) => [0, 0.5].map((desfase) => {
        const k = (t * 0.9 + desfase + (lado > 0 ? 0.25 : 0)) % 1;
        const gota = enHuevo(r, lado * (ex + 0.05 * r[0] * k), ey - 0.07 * r[1] - k * 0.55 * r[1], 0.02);
        return (
          <mesh key={`${lado}${desfase}`} geometry={ESFERA} position={gota.position} scale={[0.028 * tam, 0.04 * tam, 0.026 * tam].map((x) => x * Math.sin(k * Math.PI) ** 0.5) as V3}>
            <meshPhysicalMaterial color="#A9DBFA" roughness={0.25} emissive="#A9DBFA" emissiveIntensity={0.25} />
          </mesh>
        );
      }))}
      {/* la boca */}
      {(() => {
        const b = enHuevo(r, 0, ey - 0.2 * r[1], 0.004);
        return (
          <group position={b.position} rotation={b.rotation}>
            {aprieta < 0.98 && (
              <mesh geometry={ARCO_CARA} rotation={[0, 0, l > 0.2 ? 0 : Math.PI]} position={[0, l > 0.2 ? -0.02 * tam : 0.012 * tam, 0]}
                scale={(d > 0.5 ? 0.024 : 0.034) * tam * (1 - aprieta)}><Tinta /></mesh>
            )}
            {aprieta > 0.02 && <>
              <mesh geometry={ESFERA} position={[0, -0.03 * tam, 0]} scale={[0.07 * tam * aprieta, (0.03 + 0.06 * l) * tam * aprieta, 0.016]}><Tinta color="#C2566B" /></mesh>
              <mesh geometry={ESFERA} position={[0, (-0.05 - 0.03 * l) * tam, 0.008]} scale={[0.04 * tam * aprieta, 0.022 * tam * aprieta, 0.012]}><Tinta color="#FF9DB5" /></mesh>
            </>}
          </group>
        );
      })()}
    </group>
  );
}

/** Destellos de 4 puntas alrededor de lo que brilla. */
const DESTELLO = estrella(4, 1, 0.34);
function Destellos({ t, fuerza, radio = 0.95, alto = 0.2 }: { t: number; fuerza: number; radio?: number; alto?: number }) {
  if (fuerza < 0.05) return null;
  return (
    <group>
      {[0, 1, 2, 3, 4, 5].map((i) => {
        const a = i * 1.047 + 0.4 + Math.sin(t * 0.5 + i) * 0.12;
        const pulso = 0.5 + 0.5 * Math.sin(t * 2.6 + i * 1.9);
        return (
          <mesh key={i} geometry={DESTELLO} position={[Math.cos(a) * radio * (i % 2 ? 1 : 0.86), alto + Math.sin(a) * radio * 1.15, -0.25 + (i % 3) * 0.1]}
            rotation={[0, 0, t * 0.6 + i]} scale={(0.045 + 0.05 * pulso) * fuerza}>
            <meshBasicMaterial color={i % 2 ? "#FFFFFF" : PASTEL.mantequilla} />
          </mesh>
        );
      })}
    </group>
  );
}

// --- El bebé ------------------------------------------------------------------------
const CABEZA: V3 = [0.55, 0.47, 0.48];
// El envoltorio: una pera gordita, de y = -1.05 a 0.14.
const PERFIL_CUERPO: [number, number][] = [[0.002, -1.05], [0.3, -1.045], [0.45, -0.98], [0.525, -0.82], [0.54, -0.62],
  [0.515, -0.4], [0.46, -0.2], [0.38, -0.04], [0.27, 0.08], [0.002, 0.14]];
const CUERPO = torno(PERFIL_CUERPO);
const radioCuerpo = (y: number) => {
  for (let i = 1; i < PERFIL_CUERPO.length; i++) {
    const [x0, y0] = PERFIL_CUERPO[i - 1], [x1, y1] = PERFIL_CUERPO[i];
    if (y <= y1) return lerp(x0, x1, (y - y0) / (y1 - y0));
  }
  return 0;
};
const LUNARES: [number, number][] = [[-0.62, -0.28], [0.6, -0.34], [-0.95, -0.62], [1.0, -0.66], [-0.42, -0.78], [0.45, -0.8]];
const GORRO = new THREE.SphereGeometry(1, 40, 20, 0, Math.PI * 2, 0, Math.PI * 0.47);

/** Un bebé envuelto, de plastilina (alto ~2.1: de y = -1.05 a 1.05). Mismos
 *  props que siempre. duerme: ojos de media luna, cabeza ladeada y respiración
 *  lenta. llora: ojos apretados, lágrimas, boca abierta y temblorina.
 *  brazos: saca los bracitos. brillo: destellos alrededor. */
export function Bebe({ t = 0, duerme = 0, llora = 0, brazos = 0, brillo = 0, cobija = "#7FB3D5" }: {
  t?: number; duerme?: number; llora?: number; brazos?: number; brillo?: number; cobija?: string;
}) {
  const l = clamp01(llora), d = clamp01(duerme), b = clamp01(brazos);
  const tela = pastel(cobija, 0.84);
  const piel = `#${_c.set(PASTEL.piel).lerp(new THREE.Color("#FFC2BA"), l * 0.5).getHexString()}`;
  // squash & stretch: respira despacio dormido, rebota apurado si llora
  const ritmo = lerp(lerp(1.9, 1.1, d), 9, l);
  const pulso = Math.sin(t * ritmo);
  const estira = pulso * lerp(lerp(0.018, 0.03, d), 0.035, l);
  const tiembla = Math.sin(t * 23) * 0.018 * l;
  const flota = Math.sin(t * 1.3) * 0.02 * (1 - l);
  const ladea = 0.09 * d + Math.sin(t * 1.1) * 0.035 * (1 - d) * (1 - l) + tiembla * 0.6;
  return (
    <group position={[tiembla, flota, 0]}>
      {/* el cuerpo se aplasta desde abajo: su origen está en la base */}
      <group position={[0, -1.05, 0]} scale={[1 - estira * 0.6, 1 + estira, 1 - estira * 0.6]}>
        <group position={[0, 1.05, 0]}>
          <mesh geometry={CUERPO} castShadow receiveShadow><Arcilla color={tela} brillo={brillo} /></mesh>
          {LUNARES.map(([a, y], i) => {
            const r = radioCuerpo(y) - 0.006;
            return (
              <mesh key={i} geometry={ESFERA} position={[Math.sin(a) * r, y, Math.cos(a) * r]} rotation={[0, a, 0]} scale={[0.05, 0.05, 0.01]}>
                <Arcilla color={PASTEL.blanco} />
              </mesh>
            );
          })}
          {/* un corazón en la pancita */}
          <mesh geometry={CORAZON} position={[0, -0.5, radioCuerpo(-0.5) - 0.01]} scale={0.1}><Arcilla color={PASTEL.rosaFuerte} /></mesh>
          {/* el doblez de la cobija: un rollito crema alrededor del cuello */}
          <mesh position={[0, 0.03, 0.02]} rotation={[Math.PI / 2 + 0.1, 0, 0]} scale={[1, 1, 0.9]} castShadow receiveShadow>
            <torusGeometry args={[0.3, 0.1, 18, 40]} />
            <Arcilla color={PASTEL.crema} brillo={brillo} />
          </mesh>
          {/* bracitos: el origen en el hombro; guardados son dos manitas que asoman */}
          {[-1, 1].map((lado) => (
            <group key={lado} position={[lado * 0.37, -0.04, 0.2]}
              rotation={[lerp(0.5, 0.25, b), 0, -lado * (lerp(0.9, lerp(1.2, 0.55, l), b) + Math.sin(t * lerp(2, 11, l) + lado) * 0.14 * b)]}>
              <Rollo a={[0, 0, 0]} b={[0, lerp(0.02, 0.26, b), 0]} radio={lerp(0.07, 0.085, b)} color={b > 0.5 ? piel : tela} brillo={b > 0.5 ? 1.3 : 0} />
              <Bola p={[0, lerp(0.07, 0.36, b), 0]} s={lerp(0.085, 0.105, b)} color={piel} brillo={1.3} />
            </group>
          ))}
          {/* la cabeza: el origen en el cuello, para ladearla */}
          <group position={[0, 0.02, 0]} rotation={[0, 0, ladea]}>
            <group position={[0, 0.46, 0.02]}>
              <Bola s={CABEZA} color={piel} brillo={brillo + 1.3} />
              {/* gorrito con orejas de osito */}
              <mesh geometry={GORRO} position={[0, 0.04, -0.015]} scale={[0.568, 0.5, 0.5]} castShadow><Arcilla color={tela} brillo={brillo} /></mesh>
              <mesh position={[0, 0.14, 0]} rotation={[Math.PI / 2 - 0.12, 0, 0]} scale={[1, 0.9, 1]}>
                <torusGeometry args={[0.52, 0.07, 14, 44]} />
                <Arcilla color={PASTEL.crema} brillo={brillo} />
              </mesh>
              {[-1, 1].map((lado) => (
                <group key={lado} position={[lado * 0.36, 0.42, -0.03]} rotation={[0, 0, -lado * 0.5]}>
                  <Bola s={[0.14, 0.14, 0.09]} color={tela} brillo={brillo} />
                  <Bola p={[0, 0, 0.055]} s={[0.075, 0.075, 0.03]} color={PASTEL.rosa} sombra={false} />
                </group>
              ))}
              <Carita r={CABEZA} t={t} duerme={d} llora={l} y0={-0.1} tam={1.08} />
            </group>
          </group>
        </group>
      </group>
      <Destellos t={t} fuerza={clamp01(brillo) * (1 - l * 0.7)} />
    </group>
  );
}

// --- La cuna ------------------------------------------------------------------------
/** Cuna de barrotes gorditos (2.5 de largo; el colchón queda en y ≈ -0.4 y las
 *  patas llegan a la nube). Vacía a propósito: sin almohadas ni cobijas.
 *  colchon 0 = sin colchón. barrotes: cuántos por lado largo. */
export function Cuna({ colchon = 1, barrotes = 9, brillo = 0, madera = "#B9793C" }: {
  colchon?: number; barrotes?: number; brillo?: number; madera?: string;
}) {
  const c = clamp01(colchon);
  const palo = pastel(madera, 0.86);
  const X = 1.18, Z = 0.62, ARR = 0.6, ABA = -0.5;
  const n = Math.max(0, Math.min(14, Math.round(barrotes)));
  return (
    <group>
      <Caja p={[0, -0.6, 0]} t={[2 * X + 0.1, 0.16, 2 * Z + 0.1]} radio={0.07} color={palo} brillo={brillo} />
      {c > 0.01 && (
        <group position={[0, -0.5, 0]} scale={[1, c, 1]}>
          <Caja p={[0, 0.1, 0]} t={[2 * X - 0.12, 0.24, 2 * Z - 0.12]} radio={0.11} color={PASTEL.blanco} brillo={brillo} />
        </group>
      )}
      {[[-X, -Z], [X, -Z], [-X, Z], [X, Z]].map(([x, z], i) => (
        <group key={i}>
          <Rollo a={[x, -1.02, z]} b={[x, ARR + 0.02, z]} radio={0.085} color={palo} brillo={brillo} />
          <Bola p={[x, ARR + 0.2, z]} s={0.13} color={PASTEL.rosa} brillo={brillo} />
        </group>
      ))}
      {[-Z, Z].map((z) => <Rollo key={z} a={[-X, ARR, z]} b={[X, ARR, z]} radio={0.075} color={palo} brillo={brillo} />)}
      {[-X, X].map((x) => <Rollo key={x} a={[x, ARR, -Z]} b={[x, ARR, Z]} radio={0.075} color={palo} brillo={brillo} />)}
      {Array.from({ length: n }, (_, i) => {
        const x = lerp(-X + 0.2, X - 0.2, n > 1 ? i / (n - 1) : 0.5);
        return [-Z, Z].map((z) => <Rollo key={`${i}${z}`} a={[x, ABA, z]} b={[x, ARR, z]} radio={0.045} color={palo} brillo={brillo} />);
      })}
      {[0, 1, 2, 3].map((i) => {
        const z = lerp(-Z + 0.22, Z - 0.22, i / 3);
        return [-X, X].map((x) => <Rollo key={`${i}${x}`} a={[x, ABA, z]} b={[x, ARR, z]} radio={0.045} color={palo} brillo={brillo} />);
      })}
      {/* un corazón en la cabecera */}
      <mesh geometry={CORAZON} position={[0, ARR + 0.02, Z + 0.07]} scale={0.13} castShadow><Arcilla color={PASTEL.rosaFuerte} /></mesh>
    </group>
  );
}

// --- El biberón ---------------------------------------------------------------------
const B_ALTO = 1.1, B_BASE = -1.0;
const FRASCO = torno([[0.002, 0], [0.24, 0.005], [0.33, 0.06], [0.355, 0.2], [0.345, 0.55], [0.355, 0.85], [0.34, 1.0], [0.27, 1.08], [0.2, 1.1]]);
const LECHE = torno([[0.002, 0.03], [0.22, 0.035], [0.3, 0.08], [0.32, 0.2], [0.312, 0.55], [0.32, 0.85], [0.31, 1.0]]);
const CHUPON = torno([[0.002, 0.44], [0.07, 0.43], [0.1, 0.37], [0.095, 0.3], [0.1, 0.24], [0.17, 0.17], [0.24, 0.09], [0.25, 0]]);

/** Biberón gordito con carita; el nivel de leche se anima (0 a 1). Alto ~1.75,
 *  sentado en la nube (base en y = -1.0). `t` lo hace mecerse. */
export function Biberon({ t = 0, nivel = 0.6, brillo = 0, leche = "#FFF6E4", tapa = "#59A6C9" }: {
  t?: number; nivel?: number; brillo?: number; leche?: string; tapa?: string;
}) {
  const n = clamp01(nivel);
  const aro = pastel(tapa, 0.8);
  const mece = Math.sin(t * 1.4) * 0.04;
  const estira = Math.sin(t * 2.8) * 0.012;
  return (
    <group position={[0, B_BASE, 0]} rotation={[0, 0, mece]} scale={[1 - estira * 0.5, 1 + estira, 1 - estira * 0.5]}>
      {/* la leche va dentro: se recorta con la altura */}
      <group scale={[1, Math.max(0.02, n), 1]}>
        <mesh geometry={LECHE}><Arcilla color={pastel(leche, 0.95)} brillo={0.4 + brillo} relieveFuerza={0.3} /></mesh>
      </group>
      <mesh geometry={FRASCO} castShadow>
        <meshPhysicalMaterial color="#BFE0F7" roughness={0.35} transparent opacity={0.5} emissive="#BFE0F7" emissiveIntensity={0.2}
          sheen={0.6} sheenColor="#FFFFFF" depthWrite={false} />
      </mesh>
      {/* el brillo del plástico: una tirita blanca */}
      <mesh position={[-0.27, 0.6, 0.25]} rotation={[0, 0, 0.03]} scale={[0.022, 0.2, 0.022]}>
        <capsuleGeometry args={[1, 1.6, 4, 10]} />
        <meshBasicMaterial color="#FFFFFF" transparent opacity={0.85} />
      </mesh>
      {[0.32, 0.55, 0.78].map((f) => (
        <mesh key={f} position={[0.22, B_ALTO * f, 0.275]} rotation={[0, 0.68, Math.PI / 2]} scale={[0.012, 0.035, 0.012]}>
          <capsuleGeometry args={[1, 1.6, 4, 8]} />
          <Tinta color="#8FB9D6" />
        </mesh>
      ))}
      {/* el aro y el chupón */}
      <group position={[0, B_ALTO - 0.02, 0]}>
        <mesh position={[0, 0.07, 0]} castShadow>
          <cylinderGeometry args={[0.3, 0.33, 0.17, 36]} />
          <Arcilla color={aro} brillo={brillo} />
        </mesh>
        {[0, 0.155].map((y) => (
          <mesh key={y} position={[0, y, 0]} rotation={[Math.PI / 2, 0, 0]}>
            <torusGeometry args={[y ? 0.285 : 0.315, 0.045, 12, 40]} />
            <Arcilla color={aro} brillo={brillo} />
          </mesh>
        ))}
        <mesh geometry={CHUPON} position={[0, 0.15, 0]} castShadow><Arcilla color="#FFDFCB" brillo={brillo + 1.3} /></mesh>
      </group>
      <group position={[0, 0.5, 0]}><Carita r={[0.352, 0.5, 0.352]} t={t + 1.3} tam={0.9} /></group>
      <group position={[0, -B_BASE, 0]}><Destellos t={t} fuerza={clamp01(brillo)} radio={0.85} alto={-0.1} /></group>
    </group>
  );
}

// --- Versiones de plastilina de lo que el guion ya usa -------------------------------
function sector(r0: number, r1: number, a0: number, a1: number) {
  const s = new THREE.Shape();
  s.absarc(0, 0, r1, a0, a1, false);
  s.absarc(0, 0, r0, a1, a0, true);
  s.closePath();
  return new THREE.ExtrudeGeometry(s, { depth: 0.08, bevelEnabled: true, bevelSize: 0.045, bevelThickness: 0.045, bevelSegments: 5, curveSegments: 14 });
}

/** La rueda de casillas, en fichas gorditas; la marcada salta y toma color. */
export function Calendario({ giro = 0, marca = 0, casillas = 18, marcada = 0, color = "#FF9F0A" }: {
  giro?: number; marca?: number; casillas?: number; marcada?: number; color?: string;
}) {
  const n = Math.max(2, Math.round(casillas));
  const paso = (Math.PI * 2) / n;
  const hueco = Math.min(0.09, paso * 0.22);
  const ficha = useMemo(() => sector(0.78, 1.08, hueco, paso - hueco), [n]);
  const m = clamp01(marca);
  const vivo = pastel(color, 0.7);
  const am = marcada * paso;  // la marcada, contada desde arriba
  return (
    <group rotation={[0, 0, giro]}>
      {Array.from({ length: n }, (_, i) => {
        const activa = i === marcada;
        return (
          <mesh key={i} geometry={ficha} rotation={[0, 0, i * paso + Math.PI / 2 - paso / 2]} castShadow receiveShadow
            position={[0, 0, activa ? 0.1 * m - 0.04 : -0.04]} scale={activa ? 1 + 0.09 * m : 1}>
            <Arcilla color={activa ? vivo : i % 2 ? PASTEL.blanco : "#E9DEFA"} brillo={activa ? m : 0} />
          </mesh>
        );
      })}
      {m > 0.05 && <Estrella p={[-Math.sin(am) * 0.93, Math.cos(am) * 0.93, 0.22]} s={0.11 * m} color="#FFFFFF" giro={-giro} />}
    </group>
  );
}

/** El "sol" de atrás: un círculo pastel en la pared, como telón de la figura. */
let _halo: THREE.DataTexture | null = null;
function halo(): THREE.DataTexture {
  if (_halo) return _halo;
  const n = 128;
  const data = new Uint8Array(n * n * 4);
  for (let j = 0; j < n; j++) for (let i = 0; i < n; i++) {
    const r = Math.hypot(i - n / 2 + 0.5, j - n / 2 + 0.5) / (n / 2);
    data.set([255, 255, 255, Math.round(255 * suave(1 - r) ** 1.3)], (j * n + i) * 4);
  }
  const t = new THREE.DataTexture(data, n, n, THREE.RGBAFormat);
  t.magFilter = t.minFilter = THREE.LinearFilter;
  t.needsUpdate = true;
  _halo = t;
  return t;
}

export function Sol({ fuerza = 1, color = "#FFC94A" }: { fuerza?: number; color?: string }) {
  const f = clamp01(fuerza);
  return (
    <group position={[0, 0.1, -2.2]} scale={2.2 + f * 1.6}>
      <mesh><planeGeometry args={[2, 2]} /><meshBasicMaterial map={halo()} color="#FFFFFF" transparent opacity={0.55 + 0.4 * f} depthWrite={false} /></mesh>
      <mesh position={[0, 0, 0.01]} scale={0.72}><planeGeometry args={[2, 2]} />
        <meshBasicMaterial map={halo()} color={pastel(color, 0.86)} transparent opacity={0.5 + 0.4 * f} depthWrite={false} /></mesh>
    </group>
  );
}

/** Estrellitas y bolitas pastel que suben meciéndose. */
export function Particulas({ t, fuerza = 1, color = "#FFD27A", cantidad = 70, alto = 3.2, ancho = 0.9 }: {
  t: number; fuerza?: number; color?: string; cantidad?: number; alto?: number; ancho?: number;
}) {
  const tono = pastel(color, 0.8);
  const n = Math.min(26, Math.max(6, Math.round(cantidad * 0.3)));
  return (
    <group position={[0, -0.4, 0]}>
      {Array.from({ length: n }, (_, i) => {
        const fase = (t * 0.22 + random(`cl${i}`)) % 1;
        const x = Math.sin(fase * 6 + i) * (0.5 + fase * ancho) + (random(`cx${i}`) - 0.5) * 1.6;
        const s = (0.05 + random(`cs${i}`) * 0.05) * Math.sin(fase * Math.PI) ** 0.6 * (0.5 + 0.5 * clamp01(fuerza));
        const p: V3 = [x, fase * alto, -0.5 + (random(`cz${i}`) - 0.5) * 1.2];
        return i % 3 === 0
          ? <Estrella key={i} p={p} s={s * 1.5} color={i % 2 ? PASTEL.mantequilla : tono} giro={t + i} />
          : <Bola key={i} p={p} s={s} color={[tono, PASTEL.rosa, PASTEL.blanco][i % 3]} sombra={false} />;
      })}
    </group>
  );
}

const _formas = new Map<string, THREE.BufferGeometry>();
function geoForma(forma: string): THREE.BufferGeometry {
  if (!_formas.has(forma)) {
    const g: Record<string, () => THREE.BufferGeometry> = {
      esfera: () => new THREE.SphereGeometry(0.5, 40, 28),
      caja: () => new RoundedBoxGeometry(1, 1, 1, 6, 0.16),
      cilindro: () => torno([[0.002, -0.5], [0.4, -0.5], [0.5, -0.4], [0.5, 0.4], [0.4, 0.5], [0.002, 0.5]]),
      cono: () => torno([[0.002, -0.5], [0.4, -0.5], [0.5, -0.38], [0.1, 0.42], [0.002, 0.5]]),
      capsula: () => new THREE.CapsuleGeometry(0.25, 0.5, 8, 20),
      dona: () => new THREE.TorusGeometry(0.4, 0.14, 18, 44),
      plano: () => new RoundedBoxGeometry(1, 1, 0.08, 4, 0.04),
    };
    _formas.set(forma, (g[forma] ?? g.esfera)());
  }
  return _formas.get(forma)!;
}

/** La primitiva suelta del guion, en plastilina y en pastel. */
export function Forma({ forma = "esfera", color = "#C98A4B", tamano = [1, 1, 1], brillo = 0, opacidad = 1, giro = 0 }: {
  forma?: string; color?: string; tamano?: number | number[]; brillo?: number; opacidad?: number; giro?: number;
}) {
  const s = typeof tamano === "number" ? [tamano, tamano, tamano] : tamano;
  return (
    <group rotation={[0, giro, 0]}>
      <mesh geometry={geoForma(forma)} scale={[s[0], s[1] ?? s[0], s[2] ?? s[0]]} castShadow receiveShadow>
        <Arcilla color={pastel(color, 0.78)} brillo={brillo} opacidad={opacidad} />
      </mesh>
    </group>
  );
}
