# AI Integration

:octicons-tag-24: v1.7.0

Mealie's AI integration enables several features and enhancements throughout the application. To enable AI features, you must have access to an AI provider (such as OpenAI). Mealie works with any OpenAI-compatible API.

## Configuration

To set up AI providers, visit your group settings.

[Group Settings Demo](https://demo.mealie.io/group){ .md-button .md-button--primary }

- To enable AI features at all, you *must* set a default provider (e.g. `gpt-5`)
- To enable image recognition features, such as creating a recipe from an image, configure a provider capable of image recognition (e.g. `gpt-5`)
- To enable audio transcription features, such as importing a recipe from a video, configure a provider capable of audio transcriptions (e.g. `whisper-1`)

For most users, choosing an OpenAI model (such as `gpt-5`) and supplying the OpenAI API key is all you need to do. Note that while OpenAI has a free tier, it's not sufficiently capable for Mealie (or most other production use cases). For more information, check out [OpenAI's rate limits](https://platform.openai.com/docs/guides/rate-limits). If you deposit $5 into your OpenAI account, you will be permanently bumped up to Tier 1, which is sufficient for Mealie. Cost per-request is dependant on many factors, but Mealie tries to keep token counts conservative.

If you have another provider you'd like to use, you can configure Mealie to use that instead as long as it has an OpenAI-compatible API. See [Provider presets](#provider-presets) below.

Note that some models are capable of handling multiple features (e.g. `gpt-5` can handle both normal chat requests and image recognition requests). You may configure one provider for multiple provider features.

While Mealie has prompts for each AI task, you can customize them with your own instructions if you'd like. See [Custom prompts](#custom-prompts) below.

### Provider presets

When you create a provider, you can pick a **Provider Preset** to fill in the base URL and, where there's an obvious choice, a suggested model. A preset only fills in the form: every provider is saved as a base URL, model, and API key, and you can change any of them. Values you've already typed are never overwritten.

| Preset | Base URL | Notes |
| ------ | -------- | ----- |
| OpenAI | *(blank)* | Handles text, images, and audio (with a transcription model such as `whisper-1`). |
| Anthropic | `https://api.anthropic.com/v1/` | Use a Claude API key. Supports text and images, but not audio, so it can't be your audio provider. |
| Google Gemini | `https://generativelanguage.googleapis.com/v1beta/openai/` | Use a Gemini API key from Google AI Studio and enter a current Gemini model name. |
| Ollama | `http://localhost:11434/v1` | Replace `localhost:11434` with wherever you host Ollama (in Docker, usually `host.docker.internal` or the Ollama container's name). You *must* enter an API key, even though Ollama ignores it. Use a vision model if it will be your image provider. |
| OpenRouter | `https://openrouter.ai/api/v1` | Model names include the vendor (e.g. `openai/gpt-5`). |
| Custom | *(your own)* | Any other OpenAI-compatible API, such as Azure OpenAI or a self-hosted server. |

Mealie asks every provider for its answer in a fixed JSON format (OpenAI's "structured outputs"), so the model you choose must support them. If a provider's compatibility layer ignores that request, **Test Connection** reports a `ValidationError` and explains the cause. Try a different model, or a different provider.

## AI Features
- The AI Ingredient Parser can be used as an alternative to the NLP and Brute Force parsers. Simply choose the AI parser while parsing ingredients (:octicons-tag-24: v1.7.0)
- When importing a recipe via URL, if the default recipe scraper is unable to read the recipe data from a webpage, the webpage contents will be parsed by AI (:octicons-tag-24: v1.9.0)
- The **Import with AI** page creates a recipe out of just about anything: pasted text, HTML, or JSON, photos of a recipe, a link, or any combination of them (:octicons-tag-24: v3.23.0)

## Import with AI

The **Import with AI** page, found under *Create ➞ Import with AI*, creates a recipe from any combination of:

- **A URL.** Mealie fetches the page and reads the recipe from it. Give it a link to a video (e.g. YouTube or Instagram) and the video is transcribed instead, provided you've configured an audio provider. The URL is always saved as the recipe's source.
- **Content.** Paste a recipe as plain text, or paste raw HTML or a [schema.org Recipe](https://schema.org/Recipe) JSON object. This is useful when a site blocks Mealie from reading it directly. It's also where you write notes about a recipe you're importing from somewhere else.
- **Images.** Upload one or more photos of a recipe, hand-written or typed. Multiple photos are treated as pages of a single recipe, and the first one becomes the recipe's image. This requires an image provider.

Every source you provide is read, and the results are combined into one description of the recipe. Content you paste alongside a URL, a video, or photos adds to them rather than replacing them, so a page that only partly loaded can be topped up by hand. Where your own content disagrees with the other sources it wins, so it doubles as a place for notes: what to name the recipe, a correction to an ingredient, a step the video skipped over. If content is the only thing you provide, it's simply the recipe's source material.

You can also optionally have the recipe translated into your own language.

### Organizers

Mealie asks AI which tags, categories, and tools the recipe refers to, and always matches what comes back against the organizers you already have, so an import doesn't create a near-duplicate of a tag you're already using.

Organizers that don't match anything you have are discarded, unless you check **Create new organizers**, in which case they're created for you.

Mealie only assigns an organizer that the recipe itself refers to. It won't guess a cuisine from the ingredients or a course from the kind of dish, so a bare list of ingredients and steps usually imports with no organizers at all.

### Which provider is used

Reading the source material is the only step that needs to understand images or audio, so that's the only step that uses your image or audio provider. Turning what it read into a recipe, and working out its organizers, always use your default provider.

This means an import with photos attached is read by your image provider even if you also pasted text alongside them.

### Fallback image provider

You can optionally choose a **Fallback Image Provider** in your group settings. If your image provider can't read the photos in an import (for example, the service is down, rate limits you, or rejects the request), Mealie retries them with the fallback provider before giving up. This is useful for pairing a self-hosted model with a hosted one, or two hosted providers with each other.

- The fallback must be a different provider from your image provider, and it's only used when an image provider is set.
- It's only used when reading the photos fails. If your image provider reads them and finds no recipe, the fallback isn't asked to try again.
- Like your image provider, the fallback must be able to read images. **Test Connection** tells you whether a provider can.

## Custom prompts

:octicons-tag-24: v3.30.0

Each AI task Mealie performs has its own prompt. Group managers can customize them from the AI section of the group settings page, and admins can do the same for any group from the group management page.

- **Instructions for all prompts** are added to every prompt that produces recipe data, such as building the recipe, parsing ingredients, or translating. This is the place for preferences that apply everywhere, like "use metric units".
- **Append** adds your own instructions to a single prompt. Mealie's prompt is kept, so you still get improvements to it in future updates, and your instructions take priority wherever the two conflict.
- **Override** replaces a prompt entirely. Future updates to Mealie's prompt won't apply to yours, so Mealie lets you know when the prompt you replaced has changed. You can then compare it against yours, or reset to the default.

Some prompts are *system* prompts. These transcribe your source material as faithfully as possible before it's turned into a recipe, so the instructions for all prompts aren't added to them. You can still append to or override them individually, but this usually isn't necessary, and can make imports less reliable.

Mealie's prompts are written in English, but that doesn't change the language of your recipes: they keep the language of their source unless you choose to translate them. You can write your own instructions in any language.

Whatever you write, Mealie still adds the data a task needs (such as your list of units when parsing ingredients) after your prompt.

!!! note
    Custom prompts used to be configured with the `OPENAI_CUSTOM_PROMPT_DIR` environment variable. When you upgrade, any prompt files in that folder are imported into every group as overrides, after which the folder and the variable can be removed.
