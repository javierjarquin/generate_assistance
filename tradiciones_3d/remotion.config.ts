import { Config } from "@remotion/cli/config";

Config.setVideoImageFormat("jpeg");
Config.setOverwriteOutput(true);
// Three.js necesita WebGL en el Chrome sin pantalla
Config.setChromiumOpenGlRenderer("angle");
