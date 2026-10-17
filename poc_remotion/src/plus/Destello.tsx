// POC CapituloPlus (13/10/2026): destello de luz sobre un corte de sección
// (skill remotion-markup, light-leaks). Va encima, en modo "screen".
import { lightLeak } from "@remotion/effects/light-leak";
import { interpolate, Solid, useCurrentFrame, useVideoConfig } from "remotion";

export const Destello: React.FC<{ readonly seed: number }> = ({ seed }) => {
  const frame = useCurrentFrame();
  const { durationInFrames, height, width } = useVideoConfig();
  return (
    <div style={{ position: "absolute", inset: 0, mixBlendMode: "screen", opacity: 0.55 }}>
      <Solid
        width={width}
        height={height}
        effects={[
          lightLeak({
            seed,
            hueShift: 0,
            progress: interpolate(frame, [0, durationInFrames - 1], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }),
        ]}
      />
    </div>
  );
};
