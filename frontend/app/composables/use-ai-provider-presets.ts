export type AIProviderPresetId = "openai" | "anthropic" | "gemini" | "ollama" | "openrouter" | "custom";

export interface AIProviderPreset {
  id: AIProviderPresetId;
  /** Vendor name, also suggested as the provider's name. Left blank for the custom preset. */
  name: string;
  /** OpenAI-compatible endpoint. Blank means OpenAI itself (the backend stores it as null). */
  baseUrl: string;
  /** Suggested model, left blank where there's no single sensible default to suggest. */
  model: string;
  /** Translation key for setup notes shown under the preset picker */
  hintKey: string;
  /** Shown in the API key field, for providers that don't use a real key */
  apiKeyPlaceholder?: string;
}

/**
 * Known providers with an OpenAI-compatible API. Every provider is still stored as a plain base URL,
 * model, and API key, so a preset only fills in the form; it isn't saved anywhere.
 */
export const AI_PROVIDER_PRESETS: readonly AIProviderPreset[] = [
  {
    id: "openai",
    name: "OpenAI",
    baseUrl: "",
    model: "gpt-5",
    hintKey: "group.ai-provider-settings.preset-hint-openai",
  },
  {
    id: "anthropic",
    name: "Anthropic",
    baseUrl: "https://api.anthropic.com/v1/",
    model: "claude-opus-5-5",
    hintKey: "group.ai-provider-settings.preset-hint-anthropic",
  },
  {
    id: "gemini",
    name: "Google Gemini",
    baseUrl: "https://generativelanguage.googleapis.com/v1beta/openai/",
    model: "",
    hintKey: "group.ai-provider-settings.preset-hint-gemini",
  },
  {
    id: "ollama",
    name: "Ollama",
    baseUrl: "http://localhost:11434/v1",
    model: "",
    hintKey: "group.ai-provider-settings.preset-hint-ollama",
    apiKeyPlaceholder: "ollama",
  },
  {
    id: "openrouter",
    name: "OpenRouter",
    baseUrl: "https://openrouter.ai/api/v1",
    model: "",
    hintKey: "group.ai-provider-settings.preset-hint-openrouter",
  },
  {
    id: "custom",
    name: "",
    baseUrl: "",
    model: "",
    hintKey: "group.ai-provider-settings.preset-hint-custom",
  },
];

export function getAIProviderPreset(id: AIProviderPresetId | null | undefined): AIProviderPreset | undefined {
  return AI_PROVIDER_PRESETS.find(preset => preset.id === id);
}

function normalizeUrl(url: string | null | undefined): string {
  return (url ?? "").trim().replace(/\/+$/, "").toLowerCase();
}

/**
 * Work out which preset a saved provider was most likely created from, by its base URL.
 * A blank base URL is OpenAI; a URL that matches no preset is a custom provider.
 */
export function detectAIProviderPreset(baseUrl: string | null | undefined): AIProviderPresetId {
  const normalized = normalizeUrl(baseUrl);
  if (!normalized) {
    return "openai";
  }

  const match = AI_PROVIDER_PRESETS.find(preset => preset.baseUrl && normalizeUrl(preset.baseUrl) === normalized);
  return match?.id ?? "custom";
}

type PresetField = "name" | "baseUrl" | "model";
const PRESET_FIELDS: PresetField[] = ["name", "baseUrl", "model"];

/**
 * Fill the form from the `to` preset without clobbering anything the user typed.
 *
 * A field is only replaced when it's blank, or still holds the value the previous preset (`from`)
 * put there; a name, URL, or model the user entered themselves is left alone. The API key is never
 * touched.
 */
export function applyAIProviderPreset(
  form: Record<PresetField, string>,
  from: AIProviderPreset | undefined,
  to: AIProviderPreset,
): void {
  for (const field of PRESET_FIELDS) {
    const current = (form[field] ?? "").trim();
    const previous = from?.[field] ?? "";
    const untouched = field === "baseUrl"
      ? normalizeUrl(current) === normalizeUrl(previous)
      : current === previous.trim();

    if (!current || untouched) {
      form[field] = to[field];
    }
  }
}
