import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { nextTick } from "vue";
import GroupAIProviderDialog from "./GroupAIProviderDialog.vue";
import type { AIProviderOut } from "~/lib/api/types/group";

const wrappers: VueWrapper[] = [];

const mocks = vi.hoisted(() => ({
  getOne: vi.fn(),
  testSavedOne: vi.fn(),
}));

vi.mock("~/composables/use-ai-providers", () => ({
  useAIProviders: () => ({
    loading: ref(false),
    getOne: mocks.getOne,
    testOne: vi.fn(),
    testSavedOne: mocks.testSavedOne,
  }),
}));

function provider(overrides: Partial<AIProviderOut>): AIProviderOut {
  return {
    id: "id",
    name: "name",
    model: "model",
    baseUrl: null,
    timeout: 300,
    requestHeaders: {},
    requestParams: {},
    ...overrides,
  } as AIProviderOut;
}

function mountDialog(providerId?: string) {
  const wrapper = mount(GroupAIProviderDialog, {
    props: {
      modelValue: true,
      providerId,
    },
    global: {
      mocks: {
        $globals: { icons: { robot: "robot", save: "save", createAlt: "createAlt" } },
      },
      stubs: {
        BaseDialog: {
          template: "<div><slot /><slot name=\"custom-card-action\" /></div>",
        },
        AppLoader: { template: "<div />" },
        BaseKeyValueEditor: { template: "<div />" },
        VForm: { template: "<form><slot /></form>" },
        VSelect: {
          props: ["modelValue", "items", "hint"],
          emits: ["update:modelValue"],
          template: `
            <div>
              <select :value="modelValue" @change="$emit('update:modelValue', $event.target.value)">
                <option v-for="item in items" :key="item.value" :value="item.value">{{ item.title }}</option>
              </select>
              <span class="select-hint">{{ hint }}</span>
            </div>
          `,
        },
        VTextField: {
          props: ["modelValue"],
          template: "<input :value=\"modelValue\" @input=\"$emit('update:modelValue', $event.target.value)\">",
        },
        VNumberInput: { template: "<div />" },
        VExpansionPanels: { template: "<div><slot /></div>" },
        VExpansionPanel: { template: "<div><slot /></div>" },
        VExpansionPanelTitle: { template: "<div><slot /></div>" },
        VExpansionPanelText: { template: "<div><slot /></div>" },
        VAlert: { template: "<div><slot /></div>" },
        VDivider: { template: "<div />" },
        VBtn: { template: "<button type=\"button\"><slot /></button>" },
      },
    },
  });

  wrappers.push(wrapper);
  return wrapper;
}

describe("groupAIProviderDialog", () => {
  beforeEach(() => {
    mocks.getOne.mockReset();
    mocks.testSavedOne.mockReset();
    vi.stubGlobal("useNuxtApp", () => ({ $globals: { icons: {} } }));
  });

  afterEach(() => {
    wrappers.forEach(wrapper => wrapper.unmount());
    wrappers.length = 0;
    vi.unstubAllGlobals();
  });

  test("a stale fetch for a previously-selected provider does not clobber the form after switching providers", async () => {
    let resolveA: (value: unknown) => void;
    let resolveB: (value: unknown) => void;
    const pendingA = new Promise((resolve) => { resolveA = resolve; });
    const pendingB = new Promise((resolve) => { resolveB = resolve; });

    mocks.getOne.mockImplementation((id: string) => {
      if (id === "provider-a") return pendingA;
      if (id === "provider-b") return pendingB;
      throw new Error(`unexpected provider id: ${id}`);
    });

    const wrapper = mountDialog("provider-a");
    await nextTick();

    // Switch to provider B before A's fetch has resolved (e.g. the user closed A's
    // edit dialog and opened B's before the network responded).
    await wrapper.setProps({ providerId: "provider-b" });
    await nextTick();

    // B's fetch resolves first...
    resolveB!({ data: provider({ id: "provider-b", name: "Provider B", model: "model-b" }) });
    await flushPromises();

    const nameInput = () => wrapper.findAll("input")[0];
    expect(nameInput().element.value).toBe("Provider B");

    // ...and A's now-stale fetch resolves afterward. It must be ignored rather than
    // overwriting the form with provider A's data while provider B is being edited.
    resolveA!({ data: provider({ id: "provider-a", name: "Provider A", model: "model-a" }) });
    await flushPromises();

    expect(nameInput().element.value).toBe("Provider B");
  });

  async function runSavedProviderTest(supportsImages: boolean | null) {
    mocks.getOne.mockResolvedValue({ data: provider({ id: "provider-a", name: "Provider A", model: "model-a" }) });
    mocks.testSavedOne.mockResolvedValue({ data: { success: true, message: null, supportsImages } });

    const wrapper = mountDialog("provider-a");
    await flushPromises();

    const testButton = wrapper.findAll("button").find(button => button.text() === "Test Connection");
    await testButton!.trigger("click");
    await flushPromises();

    return wrapper.text();
  }

  test("a successful test with no image check does not call the provider text-only", async () => {
    // An audio-only provider is tested by transcription, so its image support is never checked
    // and comes back as null. That must not be read as "can't do images".
    const text = await runSavedProviderTest(null);

    expect(text).toContain("Connection successful");
    expect(text).not.toContain("Text-only");
    expect(text).not.toContain("Supports images");
  });

  test.each([
    [true, "Supports images"],
    [false, "Text-only, can't be your image provider"],
  ])("a successful test with supportsImages %s still shows the image note", async (supportsImages, note) => {
    const text = await runSavedProviderTest(supportsImages);

    expect(text).toContain("Connection successful");
    expect(text).toContain(note);
  });

  describe("provider presets", () => {
    // findAll("input") order: name, model, API key, base URL
    const inputValues = (wrapper: VueWrapper) => wrapper.findAll("input").map(input => input.element.value);

    test("choosing a preset fills in the name, model, and base URL", async () => {
      const wrapper = mountDialog();
      await flushPromises();

      await wrapper.find("select").setValue("anthropic");
      await nextTick();

      expect(inputValues(wrapper)).toEqual(["Anthropic", "claude-opus-5-5", "", "https://api.anthropic.com/v1/"]);
      expect(wrapper.find(".select-hint").text()).toContain("Claude API key");
    });

    test("choosing a preset keeps values the user already typed", async () => {
      const wrapper = mountDialog();
      await flushPromises();

      const [name, model] = wrapper.findAll("input");
      await name!.setValue("Kitchen server");
      await model!.setValue("qwen2.5vl");

      await wrapper.find("select").setValue("ollama");
      await nextTick();

      expect(inputValues(wrapper)).toEqual(["Kitchen server", "qwen2.5vl", "", "http://localhost:11434/v1"]);
    });

    test("editing a provider pre-selects the preset matching its base URL", async () => {
      mocks.getOne.mockResolvedValue({
        data: provider({ id: "provider-a", name: "Claude", model: "claude-opus-5-5", baseUrl: "https://api.anthropic.com/v1" }),
      });

      const wrapper = mountDialog("provider-a");
      await flushPromises();

      expect((wrapper.find("select").element as HTMLSelectElement).value).toBe("anthropic");
      // detecting the preset must not change the saved values
      expect(inputValues(wrapper)).toEqual(["Claude", "claude-opus-5-5", "", "https://api.anthropic.com/v1"]);
    });

    test("a ValidationError test result explains structured outputs", async () => {
      mocks.getOne.mockResolvedValue({ data: provider({ id: "provider-a", name: "Provider A", model: "model-a" }) });
      mocks.testSavedOne.mockResolvedValue({ data: { success: false, message: "ValidationError", supportsImages: null } });

      const wrapper = mountDialog("provider-a");
      await flushPromises();

      const testButton = wrapper.findAll("button").find(button => button.text() === "Test Connection");
      await testButton!.trigger("click");
      await flushPromises();

      expect(wrapper.text()).toContain("ValidationError");
      expect(wrapper.text()).toContain("structured outputs");
    });
  });
});
