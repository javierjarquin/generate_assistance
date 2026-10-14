// Props que arma scripts/armar_props.py a partir de un capítulo ya generado
// por illustrated-narrator (projects/<slug>/). Las rutas son relativas a public/.

export type Palabra = {
  readonly text: string;
  readonly start: number; // segundos
  readonly end: number;
  readonly enfasis?: boolean; // CapituloPlus: la palabra sale en el texto_en_pantalla de su plano
};

// --- CapituloPlus (POC 13/10/2026) ------------------------------------------

export type FichaDatos = {
  readonly titulo: string;
  readonly renglones: string[];
  readonly fuente: string;
  readonly resaltar: number; // renglón que la voz dice en esa toma (-1: ninguno, no se marca)
  readonly resaltarDesde: number; // segundos desde que entra la toma
};

export type Bloque = { readonly titulo: string; readonly renglones: string[] };

export type PlusProps = CapituloProps & {
  // Toma (índice como texto) -> ficha que se dibuja animada en vez de su imagen.
  readonly fichas: Record<string, Record<string, FichaDatos>>;
  readonly contador: { plano: string; numero: number; antes: string; despues: string } | null;
  readonly mapa: { plano: string; centro: [number, number]; etiqueta: string; desde: number; dur: number } | null;
  readonly contradiccion: {
    plano: string;
    arriba: Bloque;
    abajo: Bloque;
    abajoDesde: number; // segundos desde el inicio del plano
    resaltar: string;
    fuente: string;
  } | null;
  readonly destellos: number[]; // segundos de los cortes con destello
};

export type Plano = {
  readonly id: string;
  readonly seccion: string;
  readonly tipo: string; // archivo_historico | imagen_ia | grafico_movimiento
  readonly start: number; // segundos en el audio
  readonly end: number;
  readonly texto: string; // texto_en_pantalla
  readonly shots: string[];
};

export type CapituloProps = {
  readonly slug: string;
  readonly durationSec: number;
  readonly audio: string;
  readonly musica: string | null;
  readonly musicaVolumen: number;
  readonly logo: string | null;
  readonly palette: { readonly navy: string; readonly gold: string };
  readonly words: Palabra[];
  readonly planos: Plano[];
};
