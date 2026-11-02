import { describe, expect, test } from "vitest";
import {
  AI_PROVIDER_PRESETS,
  applyAIProviderPreset,
  detectAIProviderPreset,
  getAIProviderPreset,
} from "../use-ai-provider-presets";

function emptyForm() {
  return { name: "", baseUrl: "", model: "" };
}

describe("detectAIProviderPreset", () => {
  test("a blank base url is openai", () => {
    expect(detectAIProviderPreset("")).toBe("openai");
    expect(detectAIProviderPreset(null)).toBe("openai");
    expect(detectAIProviderPreset(undefined)).toBe("openai");
  });

  test.each(
    AI_PROVIDER_PRESETS.filter(preset => preset.baseUrl).map(preset => [preset.id, preset.baseUrl] as const),
  )("detects %s from its own base url", (id, baseUrl) => {
    expect(detectAIProviderPreset(baseUrl)).toBe(id);
  });

  test("ignores a trailing slash, surrounding whitespace, and case", () => {
    expect(detectAIProviderPreset("https://api.anthropic.com/v1")).toBe("anthropic");
    expect(detectAIProviderPreset(" http://LOCALHOST:11434/v1/ ")).toBe("ollama");
  });

  test("an unknown base url is custom", () => {
    expect(detectAIProviderPreset("https://my-azure.openai.azure.com/openai/v1")).toBe("custom");
    // a self-hosted Ollama on another host isn't the preset's URL either
    expect(detectAIProviderPreset("http://ollama:11434/v1")).toBe("custom");
  });
});

describe("applyAIProviderPreset", () => {
  const openai = getAIProviderPreset("openai")!;
  const anthropic = getAIProviderPreset("anthropic")!;
  const ollama = getAIProviderPreset("ollama")!;
  const custom = getAIProviderPreset("custom")!;

  test("fills a blank form", () => {
    const form = emptyForm();
    applyAIProviderPreset(form, undefined, anthropic);

    expect(form).toEqual({ name: "Anthropic", baseUrl: "https://api.anthropic.com/v1/", model: "claude-opus-5-5" });
  });

  test("replaces values the previous preset filled in", () => {
    const form = emptyForm();
    applyAIProviderPreset(form, undefined, anthropic);
    applyAIProviderPreset(form, anthropic, ollama);

    expect(form).toEqual({ name: "Ollama", baseUrl: "http://localhost:11434/v1", model: "" });
  });

  test("keeps a name, base url, and model the user typed", () => {
    const form = { name: "Kitchen server", baseUrl: "http://ollama:11434/v1", model: "qwen2.5vl" };
    applyAIProviderPreset(form, undefined, anthropic);

    expect(form).toEqual({ name: "Kitchen server", baseUrl: "http://ollama:11434/v1", model: "qwen2.5vl" });
  });

  test("keeps a field the user changed after picking a preset", () => {
    const form = emptyForm();
    applyAIProviderPreset(form, undefined, openai);
    form.model = "gpt-5-mini";
    applyAIProviderPreset(form, openai, anthropic);

    expect(form.model).toBe("gpt-5-mini");
    expect(form.name).toBe("Anthropic");
    expect(form.baseUrl).toBe("https://api.anthropic.com/v1/");
  });

  test("treats a preset's base url with or without a trailing slash as untouched", () => {
    const form = { name: "Anthropic", baseUrl: "https://api.anthropic.com/v1", model: "claude-opus-5-5" };
    applyAIProviderPreset(form, anthropic, openai);

    expect(form).toEqual({ name: "OpenAI", baseUrl: "", model: "gpt-5" });
  });

  test("switching to custom clears what the previous preset filled in", () => {
    const form = emptyForm();
    applyAIProviderPreset(form, undefined, ollama);
    applyAIProviderPreset(form, ollama, custom);

    expect(form).toEqual(emptyForm());
  });
});
