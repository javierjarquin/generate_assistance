// POC (14/10/2026): portada del video para TikTok (imagen fija 1080x1920).
// Lo que hay que leer va entre el 22% y el 75% de la altura: la cuadrícula del
// perfil recorta a ~3:4 y se come arriba y abajo. Dos variantes para medir:
//   nota -> el titular real de la prensa como protagonista (credibilidad)
//   dato -> la cifra grande sobre la foto del lugar
import { loadFont as cargarAnton } from "@remotion/google-fonts/Anton";
import { loadFont as cargarRoboto } from "@remotion/google-fonts/RobotoCondensed";
import { AbsoluteFill, Img, staticFile } from "remotion";

const { fontFamily: anton } = cargarAnton("normal", { weights: ["400"], subsets: ["latin", "latin-ext"] });
const { fontFamily: roboto } = cargarRoboto("normal", { weights: ["700"], subsets: ["latin", "latin-ext"] });

const ROJO = "#FF4D3D";

export type PortadaProps = {
  readonly variante: "nota" | "dato";
  readonly fondo: string | null; // foto del lugar o de la nota
  readonly nota: { src: string; credito: string } | null; // captura de la nota (arriba = titular)
  readonly antes: string;
  readonly numero: string;
  readonly despues: string;
  readonly logo: string | null;
  readonly palette: { readonly navy: string; readonly gold: string };
};

const Dato: React.FC<{ readonly p: PortadaProps; readonly grande: boolean }> = ({ p, grande }) => (
  <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
    {p.antes ? (
      <div style={{ fontFamily: anton, fontSize: grande ? 96 : 78, color: "white", WebkitTextStroke: "12px #050b16", paintOrder: "stroke fill" }}>
        {p.antes}
      </div>
    ) : null}
    <div
      style={{
        fontFamily: anton,
        fontSize: grande ? 400 : 250,
        lineHeight: 0.92,
        color: ROJO,
        WebkitTextStroke: "20px #050b16",
        paintOrder: "stroke fill",
        textShadow: "0 20px 50px rgba(0,0,0,0.6)",
      }}
    >
      {p.numero}
    </div>
    <div
      style={{
        fontFamily: anton,
        fontSize: grande ? 96 : 82,
        lineHeight: 1.05,
        color: p.palette.navy,
        background: p.palette.gold,
        padding: "10px 34px",
        borderRadius: 18,
        textAlign: "center",
        textTransform: "uppercase",
        boxShadow: `0 12px 0 ${p.palette.navy}, 0 20px 44px rgba(0,0,0,0.5)`,
      }}
    >
      {p.despues}
    </div>
  </div>
);

export const Portada: React.FC<PortadaProps> = (p) => {
  const { navy } = p.palette;
  return (
    <AbsoluteFill style={{ backgroundColor: navy }}>
      {p.fondo ? (
        <Img src={staticFile(p.fondo)} style={{ width: "100%", height: "100%", objectFit: "cover", filter: "saturate(1.1)" }} />
      ) : null}
      <AbsoluteFill
        style={{ background: `linear-gradient(to bottom, ${navy}cc 0%, ${navy}66 30%, ${navy}99 62%, ${navy}f2 100%)` }}
      />
      {p.variante === "nota" && p.nota ? (
        <>
          {/* El titular real: la parte de arriba de la nota, como recorte de periódico. */}
          <div
            style={{
              position: "absolute",
              top: 430,
              left: 80,
              width: 920,
              height: 560,
              rotate: "-2.5deg",
              borderRadius: 16,
              overflow: "hidden",
              background: "white",
              boxShadow: "0 30px 70px rgba(0,0,0,0.6)",
              border: "6px solid white",
            }}
          >
            <Img src={staticFile(p.nota.src)} style={{ width: "100%", objectFit: "cover", objectPosition: "top" }} />
          </div>
          <div style={{ position: "absolute", top: 1010, left: 80, fontFamily: roboto, fontSize: 30, color: "white",
            textTransform: "uppercase", letterSpacing: 2, opacity: 0.9 }}>
            Fuente: {p.nota.credito}
          </div>
          <div style={{ position: "absolute", top: 1060, width: "100%", display: "flex", justifyContent: "center" }}>
            <Dato p={p} grande={false} />
          </div>
        </>
      ) : (
        <>
          <div style={{ position: "absolute", top: 470, width: "100%", display: "flex", justifyContent: "center" }}>
            <Dato p={p} grande />
          </div>
          {p.nota ? (
            <div style={{ position: "absolute", top: 1330, width: "100%", textAlign: "center", fontFamily: roboto,
              fontSize: 34, color: "white", textTransform: "uppercase", letterSpacing: 2 }}>
              Según {p.nota.credito}
            </div>
          ) : null}
        </>
      )}
      {p.logo ? (
        <Img src={staticFile(p.logo)} style={{ position: "absolute", top: 70, left: 40, width: 150, height: 150, objectFit: "contain" }} />
      ) : null}
      <div style={{ position: "absolute", bottom: 120, width: "100%", textAlign: "center", fontFamily: anton,
        fontSize: 52, color: "white", letterSpacing: 6, opacity: 0.85 }}>
        DATO MATA GATO
      </div>
    </AbsoluteFill>
  );
};
