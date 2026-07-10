# Script To Manga Storyboard Prompt

Return only valid JSON:

```json
{
  "shots": [
    {
      "scene_id": "P001",
      "visual_description": "What the panel shows.",
      "prompt": "Image-generation prompt for one manga panel.",
      "negative_prompt": "watermark, random text, bad anatomy",
      "revision_notes": "Narration, dialogue, or continuity notes."
    }
  ]
}
```

Panel guidance:

- One shot equals one manga panel or storyboard frame.
- Split by story beat, emotional turn, important action, or location change.
- Use prompts that describe composition, character pose, expression, lighting, and setting.
- Keep dialogue out of the image prompt unless it is meant only as context.
