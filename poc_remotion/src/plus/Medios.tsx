// POC (14/10/2026): evidencia visual en movimiento. Javier: "los videos son
// muy planos y es solo texto". Tres tipos de toma, todas con crédito visible:
//   nota  -> la nota real: entra el titular, baja hasta el párrafo del dato y
//            se resalta (captura alta de scripts/multimedia.py)
//   foto  -> la foto de la nota (medios en verde o amarillo, con crédito)
//   video -> toma de archivo (Pexels) o video del medio (solo en verde)
import { Video } from "@remotion/media";
import { AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { Toma } from "../Escenas";
import type { Medio } from "../types";

const fijo = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

export const Credito: React.FC<{ readonly texto: string }> = ({ texto }) => (
  <div
    style={{
      position: "absolute",
      left: 40,
      bottom: 80,
      maxWidth: 1000,
      padding: "8px 18px",
      borderRadius: 10,
      background: "rgba(5,11,22,0.72)",
      color: "white",
      fontFamily: "sans-serif",
      fontSize: 28,
      fontWeight: 700,
      letterSpacing: 1,
      textTransform: "uppercase",
    }}
  >
    {texto}
  </div>
);

const NotaAnimada: React.FC<{ readonly medio: Medio }> = ({ medio }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const alto = medio.alto ?? height;
  const caja = medio.caja;
  const destino = caja
    ? Math.min(Math.max(caja.y + caja.h / 2 - height * 0.42, 0), Math.max(alto - height, 0))
    : Math.min(900, Math.max(alto - height, 0));
  // El titular medio segundo, la bajada en ~1 s y el resaltado al llegar.
  const y = interpolate(frame, [0.45 * fps, 1.45 * fps], [0, destino], {
    ...fijo,
    easing: Easing.bezier(0.45, 0, 0.2, 1),
  });
  const marca = interpolate(frame, [1.5 * fps, 2.0 * fps], [0, 1], fijo);
  const x = caja ? Math.max(12, Math.min(caja.x, width - 40)) : 0;
  const w = caja ? Math.min(caja.w, width - x - 12) : 0;
  return (
    <AbsoluteFill style={{ backgroundColor: "white", overflow: "hidden" }}>
      <div style={{ position: "absolute", left: 0, top: -y, width, scale: interpolate(frame, [0, 3 * fps], [1, 1.03], fijo) }}>
        <Img src={staticFile(medio.src)} style={{ width, display: "block" }} />
        {caja ? (
          <div
            style={{
              position: "absolute",
              left: x - 10,
              top: caja.y - 8,
              width: (w + 20) * marca,
              height: caja.h + 16,
              background: "rgba(212,165,55,0.42)",
              mixBlendMode: "multiply",
              borderRadius: 8,
            }}
          />
        ) : null}
      </div>
      <Credito texto={`Fuente: ${medio.credito}`} />
    </AbsoluteFill>
  );
};

export const TomaMedio: React.FC<{ readonly medio: Medio; readonly indice: number; readonly duracion: number }> = ({
  medio,
  indice,
  duracion,
}) => {
  const { width, height } = useVideoConfig();
  if (medio.tipo === "nota") return <NotaAnimada medio={medio} />;
  if (medio.tipo === "video") {
    return (
      <AbsoluteFill>
        <Video src={staticFile(medio.src)} muted loop objectFit="cover" style={{ width, height }} />
        <Credito texto={medio.credito} />
      </AbsoluteFill>
    );
  }
  return (
    <AbsoluteFill>
      <Toma src={medio.src} indice={indice} duracion={duracion} />
      <Credito texto={`Foto: ${medio.credito}`} />
    </AbsoluteFill>
  );
};
