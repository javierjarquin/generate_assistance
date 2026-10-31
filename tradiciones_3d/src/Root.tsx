import { CalculateMetadataFunction, Composition } from "remotion";
import ejemplo from "../ejemplos/cempasuchil.props.json";
import { Tradicion, TradicionProps } from "./Video";

const FPS = 30;

// Cada render trae sus props (scripts/render.py); el ejemplo es para el Studio.
const calculateMetadata: CalculateMetadataFunction<TradicionProps> = ({ props }) => ({
  durationInFrames: Math.ceil((props.tiempos.duracion + 0.8) * FPS),
});

export const Root = () => (
  <Composition id="Tradicion" component={Tradicion} fps={FPS} width={1080} height={1920} durationInFrames={FPS}
    defaultProps={ejemplo as unknown as TradicionProps} calculateMetadata={calculateMetadata} />
);
