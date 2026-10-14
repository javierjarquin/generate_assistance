import { CalculateMetadataFunction, Composition } from "remotion";
import { Capitulo } from "./Capitulo";
import { CapituloPlus } from "./CapituloPlus";
import type { CapituloProps, PlusProps } from "./types";

const FPS = 30;

// Duración = duración del audio de la narración (la pone armar_props.py).
const calculateMetadata: CalculateMetadataFunction<CapituloProps> = ({ props }) => ({
  durationInFrames: Math.max(1, Math.ceil(props.durationSec * FPS)),
});

const vacio: CapituloProps = {
  slug: "",
  durationSec: 5,
  audio: "",
  musica: null,
  musicaVolumen: 0.12,
  logo: null,
  palette: { navy: "#0B1F3A", gold: "#D4A537" },
  words: [],
  planos: [],
};

const vacioPlus: PlusProps = { ...vacio, fichas: {}, contador: null, mapa: null, contradiccion: null, destellos: [] };

const calculateMetadataPlus: CalculateMetadataFunction<PlusProps> = ({ props }) => ({
  durationInFrames: Math.max(1, Math.ceil(props.durationSec * FPS)),
});

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="Capitulo"
        component={Capitulo}
        durationInFrames={5 * FPS}
        fps={FPS}
        width={1080}
        height={1920}
        defaultProps={vacio}
        calculateMetadata={calculateMetadata}
      />
      {/* POC 13/10/2026: valor visual para retención (scripts/render_plus.py). */}
      <Composition
        id="CapituloPlus"
        component={CapituloPlus}
        durationInFrames={5 * FPS}
        fps={FPS}
        width={1080}
        height={1920}
        defaultProps={vacioPlus}
        calculateMetadata={calculateMetadataPlus}
      />
    </>
  );
};
