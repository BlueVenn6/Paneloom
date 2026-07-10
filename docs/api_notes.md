# API Notes

The current implementation uses an OpenAI-compatible Image API client with the
configured default model `gpt-image-2`. Live provider acceptance is still required.

## Image Generation

Storyboard frame generation uses:

```text
POST {base_url}/images/generations
```

The backend passes:

- `model`: configured image model, default `gpt-image-2`
- `prompt`
- `size`: default `1024x1024`
- `quality`: default `low`

The client supports responses containing either `url` or `b64_json`. URL
responses are downloaded to `assets/generated/<project_id>/`.

## Image Edits

Reference-image editing is wrapped for later UI work through:

```text
POST {base_url}/images/edits
```

Milestone 1 includes the client function but does not yet expose a reference
image upload workflow in the frontend.

## Provider Modes

Official OpenAI mode uses:

```text
https://api.openai.com/v1
```

Custom OpenAI-compatible mode allows a user-provided base URL, such as:

```text
https://api.codexzh.com/v1
```

## Why Not Responses Image Generation

This project intentionally does not use the Responses API `image_generation`
tool in Milestone 1. The current relay/provider tests show that
`/responses + image_generation` is not supported, while `gpt-image-2` works
through `/images/generations` and `/images/edits`.
