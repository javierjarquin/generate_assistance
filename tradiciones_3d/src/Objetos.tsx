// Objetos 3D hechos con primitivas: todo sale de código, sin modelos ni IA.
// Salen del POC del cempasúchil (30/10/2026). El catálogo que Claude puede usar
// está en el bot (instruccion_tradiciones.CATALOGO): si se agrega un objeto o un
// prop aquí, también va allá, o la revisión del guion lo rechaza.
import { useThree } from "@react-three/fiber";
import { useEffect, useMemo, useState } from "react";
import { continueRender, delayRender, random, staticFile } from "remotion";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { clone as cloneConEsqueleto } from "three/examples/jsm/utils/SkeletonUtils.js";

export const clamp01 = (x: number) => Math.min(1, Math.max(0, x));
export const suave = (x: number) => {
  const t = clamp01(x);
  return t * t * (3 - 2 * t);
};
export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

// Cuatro tonos por paleta: del más claro al más profundo.
export const PALETAS: Record<string, string[]> = {
  naranja: ["#FF9F0A", "#FFB20F", "#F57C00", "#E8590C"],
  amarillo: ["#FFD60A", "#FFC300", "#F2B705", "#E0A100"],
  magenta: ["#E0218A", "#C2185B", "#AD1457", "#880E4F"],
  rojo: ["#E53935", "#C62828", "#B71C1C", "#8E1B1B"],
  blanco: ["#FFF8EC", "#F3E9D7", "#E8DCC4", "#D9CBB0"],
  morado: ["#9C4DCC", "#7B1FA2", "#6A1B9A", "#4A148C"],
};
const paleta = (nombre?: string) => PALETAS[nombre ?? "naranja"] ?? PALETAS.naranja;
const ARRIBA = new THREE.Vector3(0, 1, 0);

export function Camara({ pos, mira }: { pos: number[]; mira: number[] }) {
  const camera = useThree((s) => s.camera);
  camera.position.set(pos[0], pos[1], pos[2]);
  camera.lookAt(mira[0], mira[1], mira[2]);
  return null;
}

type Petalo = { base: THREE.Vector3; normal: THREE.Vector3; q: THREE.Quaternion; color: number; orden: number; destino: THREE.Vector3 };

function petalosDeFlor(n: number, semilla: string): Petalo[] {
  const aureo = Math.PI * (3 - Math.sqrt(5));
  const out: Petalo[] = [];
  for (let i = 0; i < n; i++) {
    const y = 1 - (i / (n - 1)) * 1.65;
    const r = Math.sqrt(Math.max(0, 1 - y * y));
    const th = aureo * i;
    const normal = new THREE.Vector3(Math.cos(th) * r, y, Math.sin(th) * r).normalize();
    const radio = 0.88 + random(`${semilla}r${i}`) * 0.17;
    const inclina = new THREE.Quaternion().setFromAxisAngle(
      new THREE.Vector3(random(`${semilla}a${i}`) - 0.5, 0, random(`${semilla}b${i}`) - 0.5).normalize(),
      (random(`${semilla}t${i}`) - 0.5) * 0.9);
    const q = new THREE.Quaternion().setFromUnitVectors(ARRIBA, normal).premultiply(inclina);
    // Más hundido = tono más profundo
    const color = Math.min(3, Math.floor((1.05 - radio) / 0.05 + random(`${semilla}c${i}`) * 1.5));
    out.push({
      base: normal.clone().multiplyScalar(radio), normal, q, color,
      orden: random(`${semilla}o${i}`),
      destino: new THREE.Vector3((random(`${semilla}x${i}`) - 0.5) * 1.4, -1.57, 0.6 + random(`${semilla}z${i}`) * 3.4),
    });
  }
  return out;
}

const geoPetalo = new THREE.SphereGeometry(1, 18, 10);

function usaMateriales(brillo: number, nombre?: string) {
  const mats = useMemo(() => paleta(nombre).map((c) => new THREE.MeshStandardMaterial({ color: c, emissive: c, roughness: 0.55 })), [nombre]);
  mats.forEach((m) => (m.emissiveIntensity = 0.12 + 0.55 * brillo));
  return mats;
}

/** Un pompón de pétalos (cempasúchil, flor de ofrenda). explota = se separa en
 *  florecitas; deshoje = los pétalos caen al piso y forman un camino. */
export function Flor({ n = 340, semilla = "flor", brillo = 0, explota = 0, deshoje = 0, giro = 0,
  escala = 1, tallo = true, paleta: nombre }: {
  n?: number; semilla?: string; brillo?: number; explota?: number; deshoje?: number; giro?: number;
  escala?: number; tallo?: boolean; paleta?: string; position?: [number, number, number];
}) {
  const petalos = useMemo(() => petalosDeFlor(n, semilla), [n, semilla]);
  const mats = usaMateriales(brillo, nombre);
  const rot = new THREE.Quaternion().setFromAxisAngle(ARRIBA, giro);
  return (
    <group scale={escala}>
      {petalos.map((p, i) => {
        const suelto = suave((deshoje - p.orden * 0.75) * 4);
        const pos = p.base.clone().applyQuaternion(rot).add(p.normal.clone().applyQuaternion(rot).multiplyScalar(explota * 1.1 * (0.6 + p.orden)));
        let q = rot.clone().multiply(p.q);
        let s: [number, number, number] = [0.2, 0.045, 0.14];
        if (suelto > 0) {
          pos.lerp(p.destino, suelto);
          pos.y += Math.sin(suelto * Math.PI) * 0.8;
          q = q.slerp(new THREE.Quaternion().setFromAxisAngle(ARRIBA, p.orden * 6), suelto);
        }
        if (explota > 0) s = s.map((v) => v * (1 - explota * 0.45)) as [number, number, number];
        return <mesh key={i} geometry={geoPetalo} material={mats[p.color]} position={pos} quaternion={q} scale={s} />;
      })}
      {tallo && deshoje < 0.95 && (
        <mesh position={[0, -1.3, 0]}>
          <cylinderGeometry args={[0.07, 0.09, 1.0, 10]} />
          <meshStandardMaterial color="#3E7B27" roughness={0.8} />
        </mesh>
      )}
      {brillo > 0 && (
        <mesh scale={1.55}>
          <sphereGeometry args={[1, 24, 16]} />
          <meshBasicMaterial color={paleta(nombre)[1]} transparent opacity={0.12 * brillo} blending={THREE.AdditiveBlending} depthWrite={false} />
        </mesh>
      )}
    </group>
  );
}

/** Una corona de florecitas que gira alrededor del centro ("muchas florecitas"). */
export function Corona({ t, cantidad = 6, radio = [1.05, 1.75], velocidad = 0.35, tamano = 0.13, brillo = 0.3, paleta: nombre }: {
  t: number; cantidad?: number; radio?: number[]; velocidad?: number; tamano?: number; brillo?: number; paleta?: string;
}) {
  return (
    <group>
      {Array.from({ length: cantidad }, (_, i) => {
        const a = (i / cantidad) * Math.PI * 2 + t * velocidad;
        return (
          <group key={i} position={[Math.cos(a) * radio[0], Math.sin(a) * (radio[1] ?? radio[0]), 0.6]}>
            <Flor n={60} semilla={`m${i}`} escala={tamano} tallo={false} brillo={brillo} giro={t + i} paleta={nombre} />
          </group>
        );
      })}
    </group>
  );
}

export function Piso({ color = "#24160D" }: { color?: string }) {
  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -1.6, 0]}>
      <planeGeometry args={[60, 60]} />
      <meshStandardMaterial color={color} roughness={0.95} />
    </mesh>
  );
}

/** Un halo de luz detrás del objeto ("parece un pedazo de sol"). */
export function Sol({ fuerza = 1, color = "#FFC94A" }: { fuerza?: number; color?: string }) {
  return (
    <group position={[0, 0.2, -3.5]} scale={0.5 + fuerza * 1.1}>
      <mesh>
        <sphereGeometry args={[1, 32, 16]} />
        <meshBasicMaterial color={color} transparent opacity={0.5 * fuerza} />
      </mesh>
      {[1.5, 2.2].map((r) => (
        <mesh key={r} scale={r}>
          <sphereGeometry args={[1, 32, 16]} />
          <meshBasicMaterial color="#FF9F0A" transparent opacity={0.06 * fuerza} blending={THREE.AdditiveBlending} depthWrite={false} />
        </mesh>
      ))}
    </group>
  );
}

/** Chispas que suben ondulando: aroma, humo de copal, vapor. */
export function Particulas({ t, fuerza = 1, color = "#FFD27A", cantidad = 70, alto = 3.2, ancho = 0.9 }: {
  t: number; fuerza?: number; color?: string; cantidad?: number; alto?: number; ancho?: number;
}) {
  return (
    <group position={[0, 0.6, 0]}>
      {Array.from({ length: cantidad }, (_, i) => {
        const fase = (t * 0.35 + random(`ar${i}`)) % 1;
        const x = Math.sin(fase * 7 + i) * (0.25 + fase * ancho) + (random(`ax${i}`) - 0.5) * 0.4;
        return (
          <mesh key={i} position={[x, fase * alto, (random(`az${i}`) - 0.5) * 0.8]} scale={0.025 + random(`as${i}`) * 0.03}>
            <sphereGeometry args={[1, 8, 6]} />
            <meshBasicMaterial color={color} transparent opacity={fuerza * Math.sin(fase * Math.PI)} />
          </mesh>
        );
      })}
    </group>
  );
}

/** Una rueda de casillas con una marcada (las 18 veintenas del año mexica,
 *  los meses, los días de una fiesta). */
export function Calendario({ giro = 0, marca = 0, casillas = 18, marcada = 0, color = "#FF9F0A" }: {
  giro?: number; marca?: number; casillas?: number; marcada?: number; color?: string;
}) {
  const paso = (Math.PI * 2) / casillas;
  return (
    <group rotation={[0, 0, giro]}>
      {Array.from({ length: casillas }, (_, i) => {
        const activa = i === marcada;
        return (
          <mesh key={i}>
            <ringGeometry args={[0.72, 1.12, 6, 1, i * paso + 0.02, paso - 0.04]} />
            <meshStandardMaterial color={activa ? color : "#5A4636"} emissive={activa ? color : "#000000"}
              emissiveIntensity={activa ? 0.3 + marca : 0} roughness={0.7} side={THREE.DoubleSide} />
          </mesh>
        );
      })}
    </group>
  );
}

/** Lluvia que se va apagando. */
export function Lluvia({ t, fuerza = 1 }: { t: number; fuerza?: number }) {
  return (
    <group>
      {Array.from({ length: 140 }, (_, i) => {
        const y = 5 - ((t * 6 + random(`ly${i}`) * 7) % 7);
        return (
          <mesh key={i} position={[(random(`lx${i}`) - 0.5) * 5, y, (random(`lz${i}`) - 0.5) * 6 - 1]}>
            <cylinderGeometry args={[0.008, 0.008, 0.35, 4]} />
            <meshBasicMaterial color="#9EC7FF" transparent opacity={0.55 * fuerza} />
          </mesh>
        );
      })}
    </group>
  );
}

/** Un campo de flores que brota del piso. */
export function Campo({ crece = 1, paleta: nombre }: { crece?: number; paleta?: string }) {
  const lugares = useMemo(() => {
    const out: { x: number; z: number; d: number }[] = [];
    for (let fila = 0; fila < 6; fila++)
      for (let col = 0; col < 5; col++)
        out.push({ x: (col - 2) * 0.62 + (random(`cx${fila}${col}`) - 0.5) * 0.25, z: 1.6 - fila * 1.1, d: random(`cd${fila}${col}`) * 0.5 });
    return out;
  }, []);
  return (
    <group>
      {lugares.map((l, i) => {
        const s = suave((crece - l.d) * 2.2);
        return s > 0.01 ? (
          <group key={i} position={[l.x, -1.6 + 0.62 * s, l.z]}>
            <Flor n={70} semilla={`campo${i}`} escala={0.26 * s} giro={i} paleta={nombre} />
          </group>
        ) : null;
      })}
    </group>
  );
}

/** Huevo estrellado: la yema se pinta con el pigmento que le cae. */
export function Huevo({ pinta = 0, t }: { pinta?: number; t: number }) {
  const yema = new THREE.Color("#F6E7A1").lerp(new THREE.Color("#FF8F00"), pinta);
  return (
    <group>
      <mesh scale={[1.25, 0.12, 1.05]} position={[0, -0.1, 0]}>
        <sphereGeometry args={[1, 32, 16]} />
        <meshStandardMaterial color="#FBF6EC" roughness={0.35} />
      </mesh>
      <mesh position={[0.1, 0.12, 0.1]} scale={[0.5, 0.3, 0.5]}>
        <sphereGeometry args={[1, 32, 16]} />
        <meshStandardMaterial color={yema} emissive={yema} emissiveIntensity={0.15 + pinta * 0.25} roughness={0.25} />
      </mesh>
      {Array.from({ length: 40 }, (_, i) => {
        const f = (t * 0.6 + random(`hy${i}`)) % 1;
        const desde = new THREE.Vector3(-0.35, 1.25, -0.6);
        const hasta = new THREE.Vector3(0.1, 0.35, 0.1);
        const p = desde.clone().lerp(hasta, f);
        p.y += Math.sin(f * Math.PI) * 0.35;
        return (
          <mesh key={i} position={p} scale={0.03}>
            <sphereGeometry args={[1, 8, 6]} />
            <meshBasicMaterial color="#FF9F0A" transparent opacity={Math.sin(f * Math.PI) * clamp01(pinta * 3)} />
          </mesh>
        );
      })}
    </group>
  );
}

/** Corte de tierra: raíces que sueltan una sustancia y gusanitos que se alejan. */
export function Raices({ t, sustancia = 0 }: { t: number; sustancia?: number }) {
  const raices: [number, number, number, number][] = [[0, -0.75, 0, 0.7], [-0.25, -0.85, 0.5, 0.55], [0.25, -0.85, -0.5, 0.55],
    [-0.45, -1.15, 0.9, 0.4], [0.45, -1.15, -0.9, 0.4], [0, -1.2, 0, 0.5]];
  return (
    <group>
      <mesh position={[0, -1.5, -0.6]}>
        <boxGeometry args={[6, 2.2, 1]} />
        <meshStandardMaterial color="#3A2416" roughness={1} />
      </mesh>
      {raices.map(([x, y, rz, l], i) => (
        <mesh key={i} position={[x, y, 0]} rotation={[0, 0, rz]}>
          <cylinderGeometry args={[0.012, 0.025, l, 6]} />
          <meshStandardMaterial color="#D9C49A" roughness={0.8} />
        </mesh>
      ))}
      <mesh position={[0, -0.95, 0]} scale={0.25 + sustancia * 0.45}>
        <sphereGeometry args={[1, 24, 16]} />
        <meshBasicMaterial color="#FF9F0A" transparent opacity={0.22 * sustancia} blending={THREE.AdditiveBlending} depthWrite={false} />
      </mesh>
      {Array.from({ length: 10 }, (_, i) => {
        const lado = i % 2 ? 1 : -1;
        const y = -0.7 - random(`gy${i}`) * 0.75;
        // Se acercan hasta que la sustancia los hace retroceder
        const cerca = Math.min(suave(t / 2.5 + random(`gd${i}`) * 0.2), 1 - sustancia * 0.9);
        const x = lado * lerp(1.0, 0.42, cerca);
        const onda = Math.sin(t * 6 + i) * 0.1;
        return (
          <mesh key={i} position={[x, y + onda * 0.15, 0.05]} rotation={[0, 0, Math.PI / 2 + onda]}>
            <capsuleGeometry args={[0.04, 0.2, 4, 8]} />
            <meshStandardMaterial color="#F7C6B2" emissive="#F7C6B2" emissiveIntensity={0.25} roughness={0.6} transparent opacity={1 - sustancia * 0.75} />
          </mesh>
        );
      })}
    </group>
  );
}

/** Un camino de pétalos en el piso, de enfrente hacia el fondo (z = -7). */
export function Camino({ brillo = 0, hasta = 1, paleta: nombre }: { brillo?: number; hasta?: number; paleta?: string }) {
  const petalos = useMemo(() => Array.from({ length: 320 }, (_, i) => {
    const z = 4.2 - (i / 320) * 10.6;
    return { z, x: Math.sin(z * 0.55) * 0.3 + (random(`px${i}`) - 0.5) * 0.85, rot: random(`pr${i}`) * 6, c: Math.floor(random(`pc${i}`) * 4) };
  }), []);
  const mats = usaMateriales(brillo, nombre);
  return (
    <group>
      {petalos.map((p, i) => i / petalos.length <= hasta && (
        <mesh key={i} geometry={geoPetalo} material={mats[p.c]} position={[p.x, -1.57, p.z]} rotation={[0, p.rot, 0]} scale={[0.13, 0.025, 0.085]} />
      ))}
    </group>
  );
}

function Vela({ t, i, fuerza = 1 }: { t: number; i: number; fuerza?: number }) {
  const llama = (0.85 + Math.sin(t * 13 + i * 2.1) * 0.08 + Math.sin(t * 7.3 + i) * 0.07) * fuerza;
  return (
    <group>
      <mesh position={[0, 0.2, 0]}>
        <cylinderGeometry args={[0.06, 0.06, 0.4, 12]} />
        <meshStandardMaterial color="#F3EBDD" roughness={0.6} />
      </mesh>
      {llama > 0.01 && <>
        <mesh position={[0, 0.47, 0]} scale={[0.04, 0.08 * llama, 0.04]}>
          <sphereGeometry args={[1, 10, 8]} />
          <meshBasicMaterial color="#FFD27A" />
        </mesh>
        <mesh position={[0, 0.47, 0]} scale={0.2 * llama}>
          <sphereGeometry args={[1, 12, 8]} />
          <meshBasicMaterial color="#FFB347" transparent opacity={0.18} blending={THREE.AdditiveBlending} depthWrite={false} />
        </mesh>
      </>}
    </group>
  );
}

/** Una fila de velas encendidas; fuerza 0 = apagadas. */
export function Velas({ t, cantidad = 5, fuerza = 1, separacion = 0.5 }: { t: number; cantidad?: number; fuerza?: number; separacion?: number }) {
  return (
    <group>
      {Array.from({ length: cantidad }, (_, i) => (
        <group key={i} position={[(i - (cantidad - 1) / 2) * separacion, -0.2, 0]}>
          <Vela t={t} i={i} fuerza={fuerza} />
        </group>
      ))}
      {fuerza > 0.01 && <pointLight position={[0, 0.8, 0.8]} color="#FFB04A" intensity={4 * fuerza} distance={6} decay={1.2} />}
    </group>
  );
}

/** El altar: tres escalones con velas y flores, al fondo (z = -7). */
export function Ofrenda({ t, paleta: nombre }: { t: number; paleta?: string }) {
  const z = -7;
  const velas: [number, number, number][] = [[-1.1, -1.0, z + 0.35], [1.1, -1.0, z + 0.35], [-0.7, -0.5, z - 0.05], [0.7, -0.5, z - 0.05], [-0.3, 0.0, z - 0.4], [0.3, 0.0, z - 0.4]];
  return (
    <group>
      {[[3.0, -1.35, z + 0.35], [2.3, -0.85, z - 0.05], [1.6, -0.35, z - 0.4]].map(([w, y, zz], i) => (
        <mesh key={i} position={[0, y, zz]}>
          <boxGeometry args={[w, 0.5, 0.8]} />
          <meshStandardMaterial color={["#4A2C1A", "#55331E", "#603A22"][i]} roughness={0.8} />
        </mesh>
      ))}
      {velas.map((v, i) => (
        <group key={i} position={v}><Vela t={t} i={i} /></group>
      ))}
      {[[-0.95, -0.38, z - 0.05], [0.95, -0.38, z - 0.05], [0, 0.25, z - 0.45]].map((p, i) => (
        <group key={i} position={p as [number, number, number]}>
          <Flor n={90} semilla={`ofrenda${i}`} escala={0.24} tallo={false} brillo={0.3} paleta={nombre} />
        </group>
      ))}
      <pointLight position={[0, 0.6, z + 1.2]} color="#FFB04A" intensity={6} distance={9} decay={1.2} />
    </group>
  );
}

/** Una tira de banderitas de papel picado que ondean. */
export function PapelPicado({ t, cantidad = 7, colores = ["#E0218A", "#FF9F0A", "#7B1FA2", "#2E9E5B", "#FFD60A"], ondea = 1 }: {
  t: number; cantidad?: number; colores?: string[]; ondea?: number;
}) {
  const ancho = 0.55;
  return (
    <group>
      <mesh position={[0, 0.02, 0]} rotation={[0, 0, Math.PI / 2]}>
        <cylinderGeometry args={[0.008, 0.008, cantidad * ancho + 0.4, 4]} />
        <meshStandardMaterial color="#D9C49A" />
      </mesh>
      {Array.from({ length: cantidad }, (_, i) => {
        const c = colores[i % colores.length];
        const vaiven = Math.sin(t * 2.2 + i * 0.9) * 0.25 * ondea;
        return (
          <group key={i} position={[(i - (cantidad - 1) / 2) * ancho, 0, 0]} rotation={[vaiven, 0, 0]}>
            <mesh position={[0, -0.33, 0]}>
              <planeGeometry args={[ancho * 0.9, 0.62]} />
              <meshStandardMaterial color={c} emissive={c} emissiveIntensity={0.25} roughness={0.7} side={THREE.DoubleSide} transparent opacity={0.92} />
            </mesh>
          </group>
        );
      })}
    </group>
  );
}

// --- Modelos de la biblioteca (public/modelos, Kenney CC0, estilo juguete) ----
const CARGADOS = new Map<string, Promise<THREE.Object3D>>();

function cargar(modelo: string): Promise<THREE.Object3D> {
  if (!CARGADOS.has(modelo)) {
    CARGADOS.set(modelo, new Promise((ok, mal) =>
      new GLTFLoader().load(staticFile(`modelos/${modelo}.glb`), (g) => ok(g.scene), undefined, mal)));
  }
  return CARGADOS.get(modelo)!;
}

/** Un modelo de la biblioteca, escalado para medir `alto`, centrado y apoyado en
 *  y = 0. brillo: se ilumina con sus propios colores. */
export function Modelo({ modelo, alto = 1, brillo = 0, giro = 0 }: { modelo: string; alto?: number; brillo?: number; giro?: number }) {
  const [escena, setEscena] = useState<THREE.Object3D | null>(null);
  const [espera] = useState(() => delayRender(`modelo ${modelo}`));
  const advance = useThree((s) => s.advance);
  useEffect(() => {
    cargar(modelo).then((original) => {
      const copia = cloneConEsqueleto(original);
      copia.traverse((o) => {
        const malla = o as THREE.Mesh;
        if (malla.isMesh) malla.material = (malla.material as THREE.MeshStandardMaterial).clone();
      });
      const caja = new THREE.Box3().setFromObject(copia);
      const tam = caja.getSize(new THREE.Vector3());
      const centro = caja.getCenter(new THREE.Vector3());
      const s = alto / Math.max(tam.y, 1e-3);
      copia.scale.setScalar(s);
      copia.position.set(-centro.x * s, -caja.min.y * s, -centro.z * s);
      setEscena(copia);
    }).catch((e) => {
      console.error(`modelo ${modelo}:`, e);
      continueRender(espera);
    });
  }, [modelo, alto, espera]);
  useEffect(() => {
    if (!escena) return;
    // ThreeCanvas no redibuja solo: sin advance, el cuadro sale sin el modelo.
    advance(performance.now());
    requestAnimationFrame(() => requestAnimationFrame(() => continueRender(espera)));
  }, [escena, advance, espera]);
  useMemo(() => escena?.traverse((o) => {
    const m = (o as THREE.Mesh).material as THREE.MeshStandardMaterial | undefined;
    if (m?.isMeshStandardMaterial) {
      m.emissive.set("#FFFFFF");
      m.emissiveMap = m.map;
      m.emissiveIntensity = brillo * 0.55;
    }
  }), [escena, brillo]);
  return escena ? <group rotation={[0, giro, 0]}><primitive object={escena} /></group> : null;
}

const GEOMETRIAS: Record<string, () => THREE.BufferGeometry> = {
  esfera: () => new THREE.SphereGeometry(0.5, 32, 20),
  caja: () => new THREE.BoxGeometry(1, 1, 1),
  cilindro: () => new THREE.CylinderGeometry(0.5, 0.5, 1, 28),
  cono: () => new THREE.ConeGeometry(0.5, 1, 28),
  capsula: () => new THREE.CapsuleGeometry(0.25, 0.5, 6, 16),
  dona: () => new THREE.TorusGeometry(0.4, 0.12, 16, 40),
  plano: () => new THREE.PlaneGeometry(1, 1),
};

/** Una primitiva para armar lo que el catálogo no tiene: un pan es una esfera
 *  aplastada, un hueso una cápsula, una vela un cilindro. Tamaño 1 = 1 unidad. */
export function Forma({ forma = "esfera", color = "#C98A4B", tamano = [1, 1, 1], brillo = 0, opacidad = 1, giro = 0 }: {
  forma?: string; color?: string; tamano?: number | number[]; brillo?: number; opacidad?: number; giro?: number;
}) {
  const geo = useMemo(() => (GEOMETRIAS[forma] ?? GEOMETRIAS.esfera)(), [forma]);
  const s = typeof tamano === "number" ? [tamano, tamano, tamano] : tamano;
  return (
    <group rotation={[0, giro, 0]}>
      <mesh geometry={geo} scale={[s[0], s[1] ?? s[0], s[2] ?? s[0]]}>
        <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.08 + brillo * 0.6} roughness={0.6}
          transparent={opacidad < 1} opacity={opacidad} side={forma === "plano" ? THREE.DoubleSide : THREE.FrontSide} />
      </mesh>
      {brillo > 0 && (
        <mesh geometry={geo} scale={[s[0] * 1.35, (s[1] ?? s[0]) * 1.35, (s[2] ?? s[0]) * 1.35]}>
          <meshBasicMaterial color={color} transparent opacity={0.14 * brillo} blending={THREE.AdditiveBlending} depthWrite={false} />
        </mesh>
      )}
    </group>
  );
}
