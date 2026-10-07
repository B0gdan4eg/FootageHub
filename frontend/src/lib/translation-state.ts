export type TranslationState = { source: string; rendered: string };

// React updates are new source text; our own last write is not.
export function nextTranslation(
  current: string,
  previous: TranslationState | undefined,
  translate: (source: string) => string,
): TranslationState {
  const source = previous && current === previous.rendered ? previous.source : current;
  return { source, rendered: translate(source) };
}
