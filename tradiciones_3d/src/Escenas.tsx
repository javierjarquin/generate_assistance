// Piloto de escenas 3D para casos y cercanía (11/11/2026). El formato "noticia"
// (la nota que baja, fichas de texto) no dibujaba lo que pasó; aquí cada plano es
// una escena: escenario + personajes animados + cámara. Todo sale de código y de
// modelos de Kenney (CC0), sin IA. Modelos en public/modelos/indice_escenas.json.
import { useThree } from "@react-three/fiber";
import { useEffect, useMemo, useState } from "react";
import { continueRender, delayRender, random, staticFile } from "remotion";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { clone as cloneConEsqueleto } from "three/examples/jsm/utils/SkeletonUtils.js";

// Personajes de Kenney (mini-characters) con 32 animaciones: idle, walk, sprint,
// sit, drive, pick-up, emote-yes, emote-no, interact-right, holding-right...
// La pose sale del tiempo de la escena, no del reloj: cada render da el mismo cuadro.
const GLTFS = new Map<string, Promise<{ scene: THREE.Object3D; animations: THREE.AnimationClip[] }>>();

function cargarGltf(modelo: string) {
  if (!GLTFS.has(modelo)) {
    GLTFS.set(modelo, new Promise((ok, mal) =>
      new GLTFLoader().load(staticFile(`modelos/${modelo}.glb`), (g) => ok({ scene: g.scene, animations: g.animations }), undefined, mal)));
  }
  return GLTFS.get(modelo)!;
}

type Armado = { escena: THREE.Object3D; mixer: THREE.AnimationMixer; clips: THREE.AnimationClip[] };

export function Personaje({ modelo = "personajes/character-male-a", animacion = "idle", alto = 0.9, giro = 0, t = 0,
  velocidad = 1, desfase = 0, una_vez = false, brillo = 0 }: {
  modelo?: string; animacion?: string; alto?: number; giro?: number; t?: number; velocidad?: number; desfase?: number;
  una_vez?: boolean; brillo?: number;
}) {
  const [armado, setArmado] = useState<Armado | null>(null);
  const [espera] = useState(() => delayRender(`personaje ${modelo}`));
  const advance = useThree((s) => s.advance);
  useEffect(() => {
    cargarGltf(modelo).then((g) => {
      const copia = cloneConEsqueleto(g.scene);
      copia.traverse((o) => {
        const malla = o as THREE.Mesh;
        if (malla.isMesh) {
          malla.material = (malla.material as THREE.MeshStandardMaterial).clone();
          malla.frustumCulled = false; // la caja de una malla animada no sigue a la pose
        }
      });
      // Se mide ya en pose (idle): antes de la primera pose, las matrices de los
      // huesos no están listas y la caja sale de cualquier tamaño (un personaje
      // salía del doble que otro, 11/11/2026).
      const mixer = new THREE.AnimationMixer(copia);
      const pose = g.animations.find((c) => c.name === "idle") ?? g.animations[0];
      if (pose) {
        mixer.clipAction(pose).play();
        mixer.update(0);
      }
      copia.updateMatrixWorld(true);
      const caja = new THREE.Box3();
      copia.traverse((o) => {
        const m = o as THREE.SkinnedMesh;
        if (m.isSkinnedMesh) {
          m.skeleton.update();
          m.computeBoundingBox();
          caja.union(m.boundingBox!.clone().applyMatrix4(m.matrixWorld));
        } else if ((o as THREE.Mesh).isMesh) {
          caja.expandByObject(o);
        }
      });
      const tam = caja.getSize(new THREE.Vector3());
      const s = alto / Math.max(tam.y, 1e-3);
      const raiz = new THREE.Group();
      copia.scale.setScalar(s);
      copia.position.set(0, -caja.min.y * s, 0);
      raiz.add(copia);
      setArmado({ escena: raiz, mixer, clips: g.animations });
    }).catch((e) => {
      console.error(`personaje ${modelo}:`, e);
      continueRender(espera);
    });
  }, [modelo, alto, espera]);
  useEffect(() => {
    if (!armado) return;
    advance(performance.now());
    requestAnimationFrame(() => requestAnimationFrame(() => continueRender(espera)));
  }, [armado, advance, espera]);
  useMemo(() => armado?.escena.traverse((o) => {
    const m = (o as THREE.Mesh).material as THREE.MeshStandardMaterial | undefined;
    if (m?.isMeshStandardMaterial) {
      m.emissive.set("#FFFFFF");
      m.emissiveMap = m.map;
      m.emissiveIntensity = brillo * 0.55;
    }
  }), [armado, brillo]);
  if (armado) {
    const { mixer, clips } = armado;
    const clip = clips.find((c) => c.name === animacion) ?? clips.find((c) => c.name === "idle") ?? clips[0];
    if (clip) {
      const accion = mixer.clipAction(clip);
      for (const c of clips) if (c !== clip) mixer.existingAction(c)?.stop();
      accion.enabled = true;
      accion.paused = false;
      accion.setEffectiveWeight(1);
      if (!accion.isRunning()) accion.play();
      const crudo = Math.max(0, t * velocidad + desfase);
      accion.time = una_vez ? Math.min(crudo, clip.duration - 1e-3) : crudo % clip.duration;
      mixer.update(0);
    }
  }
  return armado ? <group rotation={[0, giro, 0]}><primitive object={armado.escena} /></group> : null;
}

const GENTE = [
  ...["a", "b", "c", "d", "e", "f", "g"].map((x) => `personajes/character-male-${x}`),
  ...["a", "b", "c", "d", "e", "f"].map((x) => `personajes/character-female-${x}`),
];

/** Mucha gente: n personas repartidas en un rectángulo, cada una con su modelo,
 *  su giro y su desfase. aparece (0 a 1): qué fracción ya está (para que llegue gente). */
export function Multitud({ n = 12, ancho = 6, fondo = 2.5, alto = 0.9, animacion = "idle", giro = 0, semilla = "m", t = 0,
  aparece = 1 }: {
  n?: number; ancho?: number; fondo?: number; alto?: number; animacion?: string; giro?: number; semilla?: string; t?: number;
  aparece?: number;
}) {
  const gente = useMemo(() => Array.from({ length: n }, (_, i) => ({
    modelo: GENTE[Math.floor(random(`${semilla}m${i}`) * GENTE.length)],
    x: (random(`${semilla}x${i}`) - 0.5) * ancho,
    z: (random(`${semilla}z${i}`) - 0.5) * fondo,
    g: giro + (random(`${semilla}g${i}`) - 0.5) * 0.9,
    d: random(`${semilla}d${i}`) * 3,
    a: alto * (0.92 + random(`${semilla}a${i}`) * 0.12),
    orden: (i + 0.5) / n,
  })), [n, ancho, fondo, giro, semilla, alto]);
  return <>{gente.filter((p) => p.orden <= aparece).map((p, i) => (
    <group key={i} position={[p.x, 0, p.z]}>
      <Personaje modelo={p.modelo} animacion={animacion} alto={p.a} giro={p.g} t={t} desfase={p.d} />
    </group>
  ))}</>;
}

/** Un vagón de metro hecho por código (Kenney no trae trenes), a lo largo de x.
 *  apagado (0 a 1): gris y sin luces, un tren parado. */
export function Vagon({ largo = 4, color = "#F26B1D", franja = "#7DBE3A", apagado = 0, luces = 1 }: {
  largo?: number; color?: string; franja?: string; apagado?: number; luces?: number;
}) {
  const cuerpo = useMemo(() => new THREE.Color(color).lerp(new THREE.Color("#5A5F66"), apagado), [color, apagado]);
  const banda = useMemo(() => new THREE.Color(franja).lerp(new THREE.Color("#44484E"), apagado), [franja, apagado]);
  const ventanas = Math.max(2, Math.round(largo / 0.7));
  const prende = luces * (1 - apagado);
  return (
    <group position={[0, 0.12, 0]}>
      <mesh position={[0, 0.5, 0]}>
        <boxGeometry args={[largo, 0.82, 0.78]} />
        <meshStandardMaterial color={cuerpo} roughness={0.45} metalness={0.15} />
      </mesh>
      <mesh position={[0, 0.2, 0]}>
        <boxGeometry args={[largo + 0.01, 0.09, 0.79]} />
        <meshStandardMaterial color={banda} roughness={0.5} />
      </mesh>
      <mesh position={[0, 0.93, 0]}>
        <boxGeometry args={[largo - 0.05, 0.06, 0.7]} />
        <meshStandardMaterial color="#D9DCE0" roughness={0.6} />
      </mesh>
      {Array.from({ length: ventanas }, (_, i) => (
        <group key={i} position={[-largo / 2 + (i + 0.5) * (largo / ventanas), 0.6, 0]}>
          {[0.395, -0.395].map((z) => (
            <mesh key={z} position={[0, 0, z]}>
              <boxGeometry args={[(largo / ventanas) * 0.62, 0.3, 0.01]} />
              <meshStandardMaterial color="#1B2430" emissive="#FFE9B8" emissiveIntensity={0.35 * prende} roughness={0.2} />
            </mesh>
          ))}
        </group>
      ))}
      {[largo / 2 + 0.005, -largo / 2 - 0.005].map((x) => (
        <group key={x} position={[x, 0, 0]}>
          <mesh position={[0, 0.62, 0]}>
            <boxGeometry args={[0.01, 0.32, 0.6]} />
            <meshStandardMaterial color="#141A22" roughness={0.2} />
          </mesh>
          {[0.25, -0.25].map((z) => (
            <mesh key={z} position={[0, 0.3, z]}>
              <sphereGeometry args={[0.05, 12, 8]} />
              <meshBasicMaterial color={prende > 0.05 ? "#FFF6D8" : "#555555"} />
            </mesh>
          ))}
        </group>
      ))}
      {Array.from({ length: 4 }, (_, i) => [0.3, -0.3].map((z) => (
        <mesh key={`${i}${z}`} position={[-largo / 2 + 0.45 + i * ((largo - 0.9) / 3), 0.02, z]} rotation={[Math.PI / 2, 0, 0]}>
          <cylinderGeometry args={[0.12, 0.12, 0.06, 20]} />
          <meshStandardMaterial color="#B8BEC6" metalness={0.9} roughness={0.25} />
        </mesh>
      )))}
    </group>
  );
}

/** Vías de acero: dos rieles y durmientes, a lo largo de x. */
export function Vias({ largo = 30 }: { largo?: number }) {
  const n = Math.round(largo / 0.5);
  return (
    <group>
      {[0.3, -0.3].map((z) => (
        <mesh key={z} position={[0, 0.03, z]}>
          <boxGeometry args={[largo, 0.05, 0.05]} />
          <meshStandardMaterial color="#C9CFD6" metalness={0.95} roughness={0.2} />
        </mesh>
      ))}
      {Array.from({ length: n }, (_, i) => (
        <mesh key={i} position={[-largo / 2 + i * 0.5, 0, 0]}>
          <boxGeometry args={[0.12, 0.04, 0.9]} />
          <meshStandardMaterial color="#3A3330" roughness={0.9} />
        </mesh>
      ))}
    </group>
  );
}

/** Andén: losa gris con la franja amarilla en el borde de enfrente (z = +fondo/2). */
export function Anden({ largo = 14, fondo = 3, alto = 0.45 }: { largo?: number; fondo?: number; alto?: number }) {
  return (
    <group>
      <mesh position={[0, -alto / 2, 0]}>
        <boxGeometry args={[largo, alto, fondo]} />
        <meshStandardMaterial color="#8E9196" roughness={0.85} />
      </mesh>
      <mesh position={[0, 0.002, fondo / 2 - 0.12]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[largo, 0.14]} />
        <meshStandardMaterial color="#F2C318" roughness={0.6} />
      </mesh>
    </group>
  );
}

/** Piso grande al nivel y = 0 (el Piso de tradiciones está en y = -1.6). */
export function Suelo({ color = "#2A2D33", tamano = 80 }: { color?: string; tamano?: number }) {
  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.001, 0]}>
      <planeGeometry args={[tamano, tamano]} />
      <meshStandardMaterial color={color} roughness={0.95} />
    </mesh>
  );
}

/** Una luz de color que parpadea (torreta de patrulla, foco de interrogatorio). */
export function Luz({ color = "#FF2B2B", fuerza = 3, distancia = 6, parpadeo = 0, t = 0 }: {
  color?: string; fuerza?: number; distancia?: number; parpadeo?: number; t?: number;
}) {
  const k = parpadeo > 0 ? 0.35 + 0.65 * (Math.sin(t * Math.PI * 2 * parpadeo) > 0 ? 1 : 0) : 1;
  return <pointLight color={color} intensity={fuerza * k} distance={distancia} decay={1.6} />;
}
