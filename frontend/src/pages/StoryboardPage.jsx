import { useEffect, useMemo, useRef, useState } from "react";
import { Lock, Unlock } from "lucide-react";

import { api, assetUrl } from "../api";
import { useI18n } from "../i18n.jsx";

const emptyShot = {
  scene_id: "",
  start_time: "",
  end_time: "",
  duration: 0,
  visual_description: "",
  prompt: "",
  negative_prompt: "",
  revision_notes: "",
};

const defaultScriptForm = {
  script: "",
  style: "black and white manga storyboard, clean line art, consistent characters",
  target_panel_count: 8,
  include_dialogue: true,
  use_ai: true,
};

const defaultBible = {
  visual_style: "black and white manga storyboard, clean line art",
  characters: "",
  locations: "",
  props: "",
  world_notes: "",
  prompt_prefix: "",
  negative_prompt:
    "watermark, random text, speech bubble text, logo, distorted hands, bad anatomy",
};

const stylePresets = [
  {
    id: "bw_manga",
    labelKey: "styleBwManga",
    prompt: "black-and-white manga storyboard style, crisp clean ink line art, white paper base, expressive faces, cinematic panel composition, controlled hatching, clear silhouettes, minimal gray tones, no color except grayscale values",
  },
  {
    id: "webtoon_color",
    labelKey: "styleWebtoonColor",
    prompt: "vertical color webcomic style, clean digital line art, soft cel shading, bright readable colors, smooth gradients only where needed, expressive character acting, polished mobile webtoon finish, clear foreground/background separation",
  },
  {
    id: "cinematic_grayscale",
    labelKey: "styleCinematicGrayscale",
    prompt: "cinematic grayscale comic style, dramatic film lighting, detailed backgrounds, clean panel storytelling, strong value contrast, grayscale tonal rendering, realistic depth, lens-like composition, no bright color palette",
  },
  {
    id: "watercolor_storybook",
    labelKey: "styleWatercolorStorybook",
    prompt: "soft watercolor storybook comic style, translucent washes, gentle paper texture, warm diffused lighting, expressive illustrated characters, soft edges, hand-painted color blooms, airy composition, no hard neon or heavy ink dominance",
  },
  {
    id: "minimal_line",
    labelKey: "styleMinimalLine",
    prompt: "minimal clean line comic style, restrained detail, strong silhouettes, elegant negative space, sparse backgrounds, precise contour lines, flat limited colors or monochrome accents, quiet modern composition, no dense rendering",
  },
  {
    id: "retro_print",
    labelKey: "styleRetroPrint",
    prompt: "retro print comic style, bold ink outlines, halftone shading, limited color accents, slightly misregistered vintage print texture, paper grain, punchy panel shapes, high readability, no glossy digital gradients",
  },
  {
    id: "urban_pop",
    labelKey: "styleUrbanPop",
    prompt: "urban pop comic style, bright poster colors, bold graphic shapes, clean outlines, street fashion details, playful composition, high-energy city mood, flat color blocks, sticker-like accents, contemporary signage shapes without readable text",
  },
  {
    id: "vintage_newspaper",
    labelKey: "styleVintageNewspaper",
    prompt: "vintage newspaper comic strip style, sepia ink, halftone dots, aged paper texture, editorial panel layout, muted contrast, archival print feeling, monochrome-to-sepia palette, old press imperfections, no modern glossy color",
  },
  {
    id: "ink_gufeng",
    labelKey: "styleInkGufeng",
    prompt: "Chinese ink wash historical fantasy comic style, flowing brush lines, rice paper texture, misty atmospheric space, elegant costume silhouettes, restrained ink palette, mineral ink accents, poetic negative space, no neon or glossy 3D rendering",
  },
  {
    id: "heritage_chinese_animation",
    labelKey: "styleHeritageChineseAnimation",
    prompt: "Chinese heritage animation inspired comic style, handcrafted ink wash texture, paper-cut shapes, folk decorative colors, theatrical composition, poetic movement, layered flat scenery, traditional ornament rhythm, no modern cyberpunk lighting",
  },
  {
    id: "future_sci_fi",
    labelKey: "styleFutureSciFi",
    prompt: "futuristic sci-fi comic style, sleek architecture, luminous interfaces, clean hard-surface design, cinematic lighting, blue and cyan accent lights, precise perspective, polished technology surfaces, controlled glow, no fantasy parchment texture",
  },
  {
    id: "cyber_neon",
    labelKey: "styleCyberNeon",
    prompt: "cyber neon city comic style, rainy streets, glowing signage shapes without readable text, dense urban layers, reflective wet surfaces, high contrast magenta and cyan lighting, night atmosphere, electric rim light, no soft pastoral palette",
  },
  {
    id: "solarpunk_future",
    labelKey: "styleSolarpunkFuture",
    prompt: "solarpunk future comic style, green architecture, warm sunlight, optimistic technology, botanical details, clean line art, hopeful color palette, airy sustainable city design, organic curves, soft gold and green accents, no dystopian neon mood",
  },
  {
    id: "silk_road_mural",
    labelKey: "styleSilkRoadMural",
    prompt: "Silk Road fantasy mural comic style, mineral pigments, desert light, ornate textiles, ancient trade city atmosphere, decorative borders, epic composition, fresco-like texture, warm earth and lapis accents, no modern streetwear styling",
  },
  {
    id: "afrofuturist_graphic",
    labelKey: "styleAfrofuturistGraphic",
    prompt: "Afrofuturist graphic novel style, geometric patterns, advanced technology blended with cultural ornament, bold silhouettes, vibrant metallic accents, sculptural costume shapes, rhythmic graphic composition, luminous but grounded palette",
  },
  {
    id: "latin_mural_magic",
    labelKey: "styleLatinMuralMagic",
    prompt: "Latin American magical realism mural comic style, sun-washed colors, symbolic motifs, expressive figures, textured plaster, dreamlike everyday scenes, mural-scale composition, warm dust and turquoise accents, no cold sci-fi interface look",
  },
  {
    id: "ukiyoe_woodblock",
    labelKey: "styleUkiyoeWoodblock",
    prompt: "ukiyo-e woodblock inspired comic style, flat color planes, elegant linework, patterned textiles, dramatic waves and clouds, traditional print texture, carved contour feeling, limited layered inks, no Western oil-paint gradients",
  },
  {
    id: "art_deco_noir",
    labelKey: "styleArtDecoNoir",
    prompt: "art deco noir comic style, geometric architecture, elegant silhouettes, dramatic shadows, gold and black accents, cinematic mystery mood, symmetrical luxury shapes, smoky contrast, refined angular composition, no cute webtoon palette",
  },
  {
    id: "custom",
    labelKey: "styleCustom",
    prompt: "",
  },
];

function stylePresetIdForPrompt(prompt) {
  const normalized = String(prompt || "").trim();
  if (normalized === "black and white manga storyboard, clean line art") {
    return "bw_manga";
  }
  if (normalized === "black and white manga storyboard, clean line art, consistent characters") {
    return "bw_manga";
  }
  const preset = stylePresets.find(
    (item) => item.id !== "custom" && item.prompt.trim() === normalized,
  );
  return preset?.id || "custom";
}

function stylePromptForPreset(presetId) {
  return stylePresets.find((item) => item.id === presetId)?.prompt || "";
}

const SCRIPT_IMPORT_ACCEPT =
  ".txt,.md,.markdown,.srt,.csv,.pdf,.docx,.epub,.rtf,.html,.htm,.xlsx";

const aspectLabelKeys = {
  square: "aspectSquare",
  portrait_4_5: "aspectPortrait45",
  vertical_9_16: "aspectVertical916",
  landscape_16_9: "aspectLandscape169",
  pin_2_3: "aspectPin23",
  default: "aspectDefault",
};

const aspectPlatformKeys = {
  square: "aspectSquarePlatforms",
  portrait_4_5: "aspectPortrait45Platforms",
  vertical_9_16: "aspectVertical916Platforms",
  landscape_16_9: "aspectLandscape169Platforms",
  pin_2_3: "aspectPin23Platforms",
};

function loadImage(src) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.crossOrigin = "anonymous";
    image.onload = () => resolve(image);
    image.onerror = reject;
    image.src = src;
  });
}

function drawCover(context, image, x, y, width, height) {
  const scale = Math.max(width / image.width, height / image.height);
  const sourceWidth = width / scale;
  const sourceHeight = height / scale;
  const sourceX = (image.width - sourceWidth) / 2;
  const sourceY = (image.height - sourceHeight) / 2;
  context.drawImage(image, sourceX, sourceY, sourceWidth, sourceHeight, x, y, width, height);
}

function aspectLabel(preset, t) {
  const id = typeof preset === "string" ? preset : preset?.id || preset?.aspect_preset;
  return aspectLabelKeys[id] ? t(aspectLabelKeys[id]) : preset?.label || preset?.aspect_label || id;
}

function aspectPlatforms(preset, t) {
  return aspectPlatformKeys[preset.id] ? t(aspectPlatformKeys[preset.id]) : preset.platforms;
}

function outputSizeText(output, t) {
  if (!output) return "";
  const size = output.final_size || output.size || "";
  if (!size) return "";
  return output.normalized ? `${size} · ${t("imageSizeVerified")}` : size;
}

function outputVersion(shot, output = null) {
  return [shot?.updated_at, output?.final_size, output?.original_size, output?.normalized]
    .filter((item) => item !== undefined && item !== null && item !== "")
    .join("-");
}

function outputAspectStyle(output) {
  const size = output?.final_size || output?.size || "";
  const [width, height] = size.split("x").map(Number);
  if (!width || !height) return {};
  return { aspectRatio: `${width} / ${height}` };
}

function shotStatusLabel(status, t) {
  const statusMap = {
    pending: "shotStatusPending",
    generating: "shotStatusGenerating",
    done: "shotStatusDone",
    generated: "shotStatusDone",
    failed: "shotStatusFailed",
    generated_url_download_failed: "shotStatusDownloadFailed",
  };
  return t(statusMap[status] || "shotStatusPending");
}

function shotProgressText(progress, t) {
  if (!progress?.stageKey) return "";
  const label = t(progress.stageKey);
  const parts = [label, progress.detail, progress.updatedAt].filter(Boolean);
  return parts.join(" · ");
}

function sleep(ms) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

export default function StoryboardPage({ currentProject, cloudAiAvailable = true }) {
  const { locale, t } = useI18n();
  const [shots, setShots] = useState([]);
  const [references, setReferences] = useState([]);
  const [aspectPresets, setAspectPresets] = useState([]);
  const [form, setForm] = useState(emptyShot);
  const [scriptForm, setScriptForm] = useState(defaultScriptForm);
  const [bible, setBible] = useState(defaultBible);
  const [referenceRefinement, setReferenceRefinement] = useState("");
  const [referencePlan, setReferencePlan] = useState([]);
  const [referenceJobProgress, setReferenceJobProgress] = useState(null);
  const [selectedReferences, setSelectedReferences] = useState([]);
  const [styleAnalysis, setStyleAnalysis] = useState("");
  const [editingShotId, setEditingShotId] = useState("");
  const [draftShot, setDraftShot] = useState(emptyShot);
  const [message, setMessage] = useState("");
  const [busyShotId, setBusyShotId] = useState("");
  const [queuedShotIds, setQueuedShotIds] = useState([]);
  const [busy, setBusy] = useState("");
  const [storyGoal, setStoryGoal] = useState("");
  const [storyAdvice, setStoryAdvice] = useState(null);
  const [scriptImportInfo, setScriptImportInfo] = useState(null);
  const [scriptVersions, setScriptVersions] = useState([]);
  const [shotErrors, setShotErrors] = useState({});
  const [shotProgress, setShotProgress] = useState({});
  const [selectedAspects, setSelectedAspects] = useState(["vertical_9_16"]);
  const [visualFormat, setVisualFormat] = useState("webtoon_strip");
  const [panelGutterStyle, setPanelGutterStyle] = useState("framed");
  const [generationQuality, setGenerationQuality] = useState("medium");
  const [gridAspect, setGridAspect] = useState("vertical_9_16");
  const [gridColumns, setGridColumns] = useState(2);
  const [previewImage, setPreviewImage] = useState(null);
  const generationQueueRef = useRef([]);
  const processingQueueRef = useRef(false);
  const shouldStopQueueRef = useRef(false);
  const workspaceSaveTimerRef = useRef(null);
  const workspaceLoadedProjectIdRef = useRef("");

  useEffect(() => {
    setReferencePlan([]);
    setReferenceJobProgress(null);
  }, [currentProject?.project_id]);

  function setShotProgressStage(shotId, stageKey, detail = "") {
    if (!shotId) return;
    setShotProgress((current) => ({
      ...current,
      [shotId]: {
        stageKey,
        detail,
        updatedAt: new Date().toLocaleTimeString(),
      },
    }));
  }

  function mergeShotUpdate(shotId, updates) {
    if (!shotId) return;
    setShots((current) =>
      current.map((shot) =>
        shot.shot_id === shotId
          ? { ...shot, ...updates, updated_at: new Date().toISOString() }
          : shot,
      ),
    );
  }

  function isGlobalGenerationBlocker(errorCode = "", message = "") {
    const text = `${errorCode} ${message}`.toLowerCase();
    return [
      "insufficient_quota",
      "invalid_api_key",
      "model_not_found",
      "endpoint_not_found",
      "configuration_error",
      "quota",
      "额度",
      "令牌",
      "unauthorized",
    ].some((token) => text.includes(token));
  }

  function responseErrorMessage(response, fallback = "") {
    if (!response) return fallback || t("unknownError");
    const data = response.data || {};
    if (data.error_code === "image_test_running") return t("generationBlockedByImageTest");
    const errors = Array.isArray(data.errors) ? data.errors.filter(Boolean).join(" · ") : "";
    return (
      errors ||
      data.error_message ||
      data.error ||
      data.short_error ||
      data.error_code ||
      response.message ||
      fallback ||
      t("unknownError")
    );
  }

  function localizedGenerationError(message) {
    const text = String(message || "");
    if (text.includes("Generation was interrupted when the backend stopped")) {
      return t("generationInterruptedRetry");
    }
    if (
      text.includes("Image provider exceeded the total response deadline") ||
      text.includes("request_timeout")
    ) {
      return t("generationProviderTimedOut");
    }
    return text;
  }

  function workspacePayload(overrides = {}) {
    return {
      script: scriptForm.script,
      script_import: scriptImportInfo || {},
      script_versions: scriptVersions,
      story_goal: storyGoal,
      story_optimization: storyAdvice,
      target_panel_count: Number(scriptForm.target_panel_count) || 8,
      include_dialogue: scriptForm.include_dialogue,
      use_ai: scriptForm.use_ai,
      visual_format: visualFormat,
      panel_gutter_style: panelGutterStyle,
      generation_quality: generationQuality,
      selected_aspects: selectedAspects,
      selected_reference_filenames: selectedReferences,
      ...overrides,
    };
  }

  async function saveWorkspace(overrides = {}) {
    if (!currentProject) return null;
    return api.saveProjectWorkspace(
      currentProject.project_id,
      workspacePayload(overrides),
    );
  }

  async function refreshAll(hydrateWorkspace = false) {
    if (!currentProject) {
      setShots([]);
      setReferences([]);
      setScriptForm(defaultScriptForm);
      setStoryGoal("");
      setStoryAdvice(null);
      setScriptImportInfo(null);
      setScriptVersions([]);
      workspaceLoadedProjectIdRef.current = "";
      return;
    }
    const [shotResponse, bibleResponse, referenceResponse, aspectResponse, workspaceResponse, settingsResponse] = await Promise.all([
      api.listShots(currentProject.project_id),
      api.getProjectBible(currentProject.project_id),
      api.listReferences(currentProject.project_id),
      api.getAspectPresets(currentProject.project_id),
      api.getProjectWorkspace(currentProject.project_id),
      api.getSettings(),
    ]);
    const nextShots = shotResponse.data || [];
    setShots(nextShots);
    const terminalShotIds = new Set(
      nextShots
        .filter((shot) => shot.status === "failed" || (shot.status === "done" && shot.output_url))
        .map((shot) => shot.shot_id),
    );
    if (terminalShotIds.size > 0) {
      generationQueueRef.current = generationQueueRef.current.filter(
        (shotId) => !terminalShotIds.has(shotId),
      );
      setQueuedShotIds((current) => current.filter((shotId) => !terminalShotIds.has(shotId)));
      setBusyShotId((current) => (terminalShotIds.has(current) ? "" : current));
      setShotErrors((current) => {
        const next = { ...current };
        nextShots.forEach((shot) => {
          if (shot.status === "done" && shot.output_url) {
            next[shot.shot_id] = "";
          } else if (shot.status === "failed" && shot.generation_error) {
            next[shot.shot_id] = localizedGenerationError(shot.generation_error);
          }
        });
        return next;
      });
      setShotProgress((current) => {
        const next = { ...current };
        nextShots.forEach((shot) => {
          if (!current[shot.shot_id]) return;
          if (shot.status === "done" && shot.output_url) {
            next[shot.shot_id] = {
              stageKey: "generationProgressDone",
              detail: shot.output_url,
              updatedAt: new Date().toLocaleTimeString(),
            };
          } else if (shot.status === "failed") {
            next[shot.shot_id] = {
              stageKey: "generationProgressFailed",
              detail: localizedGenerationError(shot.generation_error) || t("unknownError"),
              updatedAt: new Date().toLocaleTimeString(),
            };
          }
        });
        return next;
      });
    }
    const nextBible = { ...defaultBible, ...(bibleResponse.data || {}) };
    setBible(nextBible);
    setStyleAnalysis(nextBible.style_analysis || "");
    const nextReferences = referenceResponse.data || [];
    const nextAspects = aspectResponse.data || [];
    setReferences(nextReferences);
    setAspectPresets(nextAspects);
    if (hydrateWorkspace) {
      const workspace = workspaceResponse.data || {};
      setScriptForm((current) => ({
        ...defaultScriptForm,
        style: nextBible.visual_style || current.style,
        script: workspace.script || "",
        target_panel_count: workspace.target_panel_count || 8,
        include_dialogue: workspace.include_dialogue ?? true,
        use_ai: workspace.use_ai ?? true,
      }));
      setStoryGoal(workspace.story_goal || "");
      const savedAdvice = workspace.story_optimization || null;
      setStoryAdvice(
        savedAdvice
          ? { ...savedAdvice, stale: savedAdvice.stale === true || savedAdvice.source !== "ai" }
          : null,
      );
      const savedImport =
        workspace.script_import && Object.keys(workspace.script_import).length > 0
          ? workspace.script_import
          : null;
      setScriptImportInfo(
        savedImport
          ? {
              ...savedImport,
              warnings: Array.isArray(savedImport.warnings) ? savedImport.warnings : [],
              // Legacy imports did not record derivation freshness. Treat them as
              // stale until the current script is explicitly analyzed again.
              optimizationCurrent: savedImport.optimizationCurrent === true,
              bibleCurrent: savedImport.bibleCurrent === true,
              storyboardCurrent: savedImport.storyboardCurrent === true,
            }
          : null,
      );
      setScriptVersions(
        Array.isArray(workspace.script_versions) ? workspace.script_versions : [],
      );
      setVisualFormat(workspace.visual_format || "webtoon_strip");
      setPanelGutterStyle(workspace.panel_gutter_style || "framed");
      setGenerationQuality(
        workspace.generation_quality || settingsResponse.data?.image_quality || "medium",
      );
      const savedAspects = Array.isArray(workspace.selected_aspects)
        ? workspace.selected_aspects.filter((aspectId) =>
            nextAspects.some((aspect) => aspect.id === aspectId),
          )
        : [];
      setSelectedAspects(savedAspects.length > 0 ? savedAspects : ["vertical_9_16"]);
      const savedReferences = Array.isArray(workspace.selected_reference_filenames)
        ? workspace.selected_reference_filenames
        : [];
      setSelectedReferences(
        savedReferences.filter((filename) =>
          nextReferences.some((reference) => reference.filename === filename),
        ),
      );
      workspaceLoadedProjectIdRef.current = currentProject.project_id;
    } else {
      setScriptForm((current) => ({
        ...current,
        style: nextBible.visual_style || current.style,
      }));
      setSelectedReferences((current) =>
        current.filter((filename) =>
          nextReferences.some((reference) => reference.filename === filename),
        ),
      );
    }
  }

  useEffect(() => {
    workspaceLoadedProjectIdRef.current = "";
    refreshAll(true).catch((error) => setMessage(error.message));
    return () => {
      if (workspaceSaveTimerRef.current) window.clearTimeout(workspaceSaveTimerRef.current);
    };
  }, [currentProject?.project_id]);

  useEffect(() => {
    if (
      !currentProject ||
      workspaceLoadedProjectIdRef.current !== currentProject.project_id
    ) {
      return undefined;
    }
    if (workspaceSaveTimerRef.current) window.clearTimeout(workspaceSaveTimerRef.current);
    workspaceSaveTimerRef.current = window.setTimeout(() => {
      saveWorkspace().catch((error) => setMessage(error.message));
    }, 700);
    return () => window.clearTimeout(workspaceSaveTimerRef.current);
  }, [
    currentProject?.project_id,
    scriptForm.script,
    scriptForm.target_panel_count,
    scriptForm.include_dialogue,
    scriptForm.use_ai,
    storyGoal,
    storyAdvice,
    scriptImportInfo,
    scriptVersions,
    visualFormat,
    panelGutterStyle,
    generationQuality,
    selectedAspects,
    selectedReferences,
  ]);

  const generatedShots = useMemo(
    () => shots.filter((shot) => shot.output_url),
    [shots],
  );

  const queueableShots = useMemo(
    () =>
      shots.filter((shot) =>
        !shot.locked &&
        ["pending", "failed", "generating", "generated_url_download_failed"].includes(shot.status),
      ),
    [shots],
  );

  async function run(label, action) {
    setBusy(label);
    setMessage("");
    try {
      const response = await action();
      await refreshAll();
      if (response && response.ok === false) {
        const errorMessage = responseErrorMessage(response);
        setMessage(errorMessage);
        return response;
      }
      setMessage(response?.localizedMessage || response?.message || t("doneMessage"));
      return response;
    } catch (error) {
      setMessage(error.message);
      return null;
    } finally {
      setBusy("");
    }
  }

  function handleScriptTextChange(value) {
    setScriptForm((current) => ({ ...current, script: value }));
    if (storyAdvice && !storyAdvice.stale) {
      setStoryAdvice((current) => (current ? { ...current, stale: true } : current));
    }
    if (scriptImportInfo) {
      setScriptImportInfo((current) => ({
        ...current,
        optimizationCurrent: false,
        bibleCurrent: false,
        storyboardCurrent: false,
      }));
    }
  }

  function saveGlobalStyle(prompt) {
    if (!currentProject || !prompt) return;
    api
      .saveProjectBible(currentProject.project_id, { ...bible, visual_style: prompt })
      .then((response) => {
        setBible((current) => ({ ...current, ...(response.data || {}), visual_style: prompt }));
      })
      .catch((error) => setMessage(error.message));
  }

  function applyStylePreset(presetId) {
    const prompt = stylePromptForPreset(presetId);
    if (!prompt) return;
    setScriptForm((current) => ({ ...current, style: prompt }));
    setBible((current) => ({ ...current, visual_style: prompt }));
    saveGlobalStyle(prompt);
  }

  function updateGlobalStyle(prompt) {
    setScriptForm((current) => ({ ...current, style: prompt }));
    setBible((current) => ({ ...current, visual_style: prompt }));
  }

  async function syncBibleBeforeGeneration() {
    if (!currentProject) return bible;
    await saveWorkspace();
    const response = await api.saveProjectBible(currentProject.project_id, bible);
    const savedBible = { ...defaultBible, ...(response.data || bible) };
    setBible(savedBible);
    return savedBible;
  }

  async function handleBreakdownScript(event) {
    event.preventDefault();
    if (!currentProject || !scriptForm.script.trim()) return;
    await run("script", async () => {
      const savedBible = await syncBibleBeforeGeneration();
      const response = await api.createShotsFromScript(currentProject.project_id, {
        ...scriptForm,
        style: savedBible.visual_style || scriptForm.style,
        visual_format: visualFormat,
        panel_gutter_style: panelGutterStyle,
        target_panel_count: Number(scriptForm.target_panel_count) || 8,
      });
      if (!response.ok) return response;
      const nextImportInfo = scriptImportInfo
        ? { ...scriptImportInfo, storyboardCurrent: true }
        : scriptImportInfo;
      if (nextImportInfo) {
        setScriptImportInfo(nextImportInfo);
        await saveWorkspace({ script_import: nextImportInfo });
      }
      const source = response.data?.source === "ai" ? t("sourceAi") : t("sourceLocal");
      const warnings = response.data?.warnings || [];
      return {
        ...response,
        localizedMessage:
          warnings.length > 0
            ? `${t("scriptBreakdownComplete")} ${t("sourceLabel")}: ${source}. ${warnings.join(" ")}`
            : `${t("scriptBreakdownComplete")} ${t("sourceLabel")}: ${source}.`,
      };
    });
  }

  async function handleRewriteStoryboard() {
    if (!currentProject || shots.length === 0) return;
    await run("rewrite-storyboard", async () => {
      const savedBible = await syncBibleBeforeGeneration();
      const response = await api.rewriteStoryboard(currentProject.project_id, {
        script: scriptForm.script,
        style: savedBible.visual_style || scriptForm.style,
        visual_format: visualFormat,
        panel_gutter_style: panelGutterStyle,
        use_ai: scriptForm.use_ai,
        reset_outputs: true,
      });
      const source = response.data?.source === "ai" ? t("sourceAi") : t("sourceLocal");
      const warnings = response.data?.warnings || [];
      return {
        ...response,
        localizedMessage:
          warnings.length > 0
            ? `${t("storyboardRewriteComplete")} ${t("sourceLabel")}: ${source}. ${warnings.join(" ")}`
            : `${t("storyboardRewriteComplete")} ${t("sourceLabel")}: ${source}.`,
      };
    });
  }

  async function handleOptimizeStory() {
    if (!currentProject || !scriptForm.script.trim()) return;
    await run("story-optimization", async () => {
      const savedBible = await syncBibleBeforeGeneration();
      const targetPlatforms = selectedAspects.map((aspectId) => {
        const preset = aspectPresets.find((item) => item.id === aspectId) || aspectId;
        return aspectLabel(preset, t);
      });
      const response = await api.optimizeStory(currentProject.project_id, {
        script: scriptForm.script,
        goal: storyGoal,
        style: savedBible.visual_style || scriptForm.style,
        target_platforms: targetPlatforms,
        use_ai: true,
        output_language: locale,
      });
      if (!response.ok) return response;
      const nextAdvice = { ...(response.data || {}), stale: false };
      const nextImportInfo = scriptImportInfo
        ? { ...scriptImportInfo, optimizationCurrent: true }
        : scriptImportInfo;
      setStoryAdvice(nextAdvice);
      if (nextImportInfo) setScriptImportInfo(nextImportInfo);
      await saveWorkspace({
        story_optimization: nextAdvice,
        ...(nextImportInfo ? { script_import: nextImportInfo } : {}),
      });
      return {
        ...response,
        localizedMessage: `${t("storyboardStrategy")} · ${
          response.data?.source === "ai" ? t("sourceAi") : t("sourceLocal")
        }`,
      };
    });
  }

  async function applyOptimizedScript() {
    if (!storyAdvice?.improved_script || storyAdvice.stale || storyAdvice.source !== "ai") return;
    const nextVersions = scriptForm.script
      ? [
          ...scriptVersions,
          {
            script: scriptForm.script,
            created_at: new Date().toISOString(),
            reason: "accepted_optimization",
          },
        ].slice(-20)
      : scriptVersions;
    setScriptVersions(nextVersions);
    setScriptForm((current) => ({ ...current, script: storyAdvice.improved_script }));
    await saveWorkspace({
      script: storyAdvice.improved_script,
      script_versions: nextVersions,
    });
    setMessage(t("applyOptimizedScript"));
  }

  async function discardStoryOptimization() {
    setStoryAdvice(null);
    await saveWorkspace({ story_optimization: null });
    setMessage(t("storyOptimizationDiscarded"));
  }

  async function undoScriptChange() {
    const previous = scriptVersions[scriptVersions.length - 1];
    if (!previous?.script) return;
    const remaining = scriptVersions.slice(0, -1);
    setScriptVersions(remaining);
    setScriptForm((current) => ({ ...current, script: previous.script }));
    await saveWorkspace({ script: previous.script, script_versions: remaining });
    setMessage(t("scriptChangeUndone"));
  }

  async function applyRecommendedPanels() {
    const panelCount = Number(storyAdvice?.recommended_panel_count);
    if (!panelCount) return;
    setScriptForm((current) => ({ ...current, target_panel_count: panelCount }));
    setMessage(t("applyRecommendedPanels"));
  }

  async function handleAddShot(event) {
    event.preventDefault();
    if (!currentProject) return;
    await run("add-shot", async () => {
      const response = await api.createShot(currentProject.project_id, {
        ...form,
        duration: Number(form.duration) || 0,
      });
      setForm(emptyShot);
      return response;
    });
  }

  async function handleSaveBible(event) {
    event.preventDefault();
    if (!currentProject) return;
    await run("bible", () => api.saveProjectBible(currentProject.project_id, bible));
  }

  async function handleAnalyzeBible() {
    if (!currentProject) return;
    await run("analyze-bible", async () => {
      const response = await api.analyzeProjectBible(currentProject.project_id, {
        script: scriptForm.script,
        use_ai: true,
        replace_existing: scriptImportInfo?.bibleCurrent === false,
      });
      if (!response.ok) return response;
      if (response.data?.bible) {
        const nextBible = {
          ...defaultBible,
          ...response.data.bible,
          visual_style: bible.visual_style || response.data.bible.visual_style,
        };
        setBible(nextBible);
        setScriptForm((current) => ({ ...current, style: nextBible.visual_style || current.style }));
      }
      const warnings = response.data?.warnings || [];
      const nextImportInfo = scriptImportInfo
        ? { ...scriptImportInfo, bibleCurrent: true }
        : scriptImportInfo;
      if (nextImportInfo) {
        setScriptImportInfo(nextImportInfo);
        await saveWorkspace({ script_import: nextImportInfo });
      }
      return {
        ...response,
        message:
          warnings.length > 0
            ? `${t("bibleAnalyzed")} ${warnings.join(" ")}`
            : t("bibleAnalyzed"),
      };
    });
  }

  async function handleGenerateReferences(
    categories = ["main_characters", "supporting_characters", "locations", "props"],
    label = "reference-concepts",
  ) {
    if (!currentProject) return;
    await run(label, async () => {
      let currentBible = await syncBibleBeforeGeneration();
      const shouldAnalyzeBeforeAssets =
        scriptImportInfo?.bibleCurrent === false ||
        !currentBible.characters?.trim() ||
        !currentBible.locations?.trim() ||
        !currentBible.world_notes?.trim() ||
        !currentBible.prompt_prefix?.trim();
      if (shouldAnalyzeBeforeAssets) {
        const bibleResponse = await api.analyzeProjectBible(currentProject.project_id, {
          script: scriptForm.script,
          use_ai: true,
          replace_existing: scriptImportInfo?.bibleCurrent === false,
        });
        if (!bibleResponse.ok) return bibleResponse;
        if (bibleResponse.data?.bible) {
          currentBible = {
            ...defaultBible,
            ...bibleResponse.data.bible,
            visual_style: currentBible.visual_style || bibleResponse.data.bible.visual_style,
          };
          await api.saveProjectBible(currentProject.project_id, currentBible);
          setBible(currentBible);
          setScriptForm((current) => ({
            ...current,
            style: currentBible.visual_style || current.style,
          }));
        }
        if (scriptImportInfo) {
          const nextImportInfo = { ...scriptImportInfo, bibleCurrent: true };
          setScriptImportInfo(nextImportInfo);
          await saveWorkspace({ script_import: nextImportInfo });
        }
      }
      setMessage(t("planningReferenceAssets"));
      const planResponse = await api.planReferenceAssets(currentProject.project_id, {
        script: scriptForm.script,
        categories,
        refinement_prompt: referenceRefinement,
      });
      if (!planResponse.ok) return planResponse;
      const nextPlan = Array.isArray(planResponse.data?.plan) ? planResponse.data.plan : [];
      setReferencePlan(nextPlan);
      setReferenceJobProgress({ completed: 0, failed: 0, total: nextPlan.length, current: "" });
      if (nextPlan.length === 0) {
        return { ok: false, message: t("referencePlanEmpty"), data: {} };
      }
      const confirmed = window.confirm(
        `${t("referencePlanConfirmPrefix")} ${nextPlan.length} ${t("referencePlanConfirmSuffix")}\n\n${nextPlan
          .map((item, index) => `${index + 1}. ${item.name} - ${item.purpose}`)
          .join("\n")}`,
      );
      if (!confirmed) {
        return { ok: true, localizedMessage: t("referencePlanReadyNotStarted"), data: {} };
      }
      const startResponse = await api.startReferenceConceptJob(currentProject.project_id, {
        script: scriptForm.script,
        categories,
        refinement_prompt: referenceRefinement,
        plan: nextPlan,
      });
      const jobId = startResponse.data?.job_id;
      if (!jobId) {
        throw new Error(t("referenceJobMissingId"));
      }
      setMessage(`${t("referenceProgressQueued")} · ${jobId}`);
      let response = startResponse;
      let pollAttempts = 0;
      while (jobId) {
        pollAttempts += 1;
        if (pollAttempts > 200) throw new Error(t("generationPollingTimedOut"));
        await sleep(3000);
        const jobResponse = await api.getReferenceConceptJob(currentProject.project_id, jobId);
        const job = jobResponse.data || {};
        await refreshAll().catch(() => {});
        if (job.status === "queued") {
          setMessage(`${t("referenceProgressQueued")} · ${jobId} · ${job.duration_seconds || 0}s`);
        } else if (job.status === "running") {
          setReferenceJobProgress({
            completed: job.completed || 0,
            failed: job.failed_count || 0,
            total: job.planned_total || nextPlan.length,
            current: job.current_asset || "",
          });
          setMessage(
            `${t("referenceProgressRunning")} ${job.completed || 0}/${job.planned_total || nextPlan.length}` +
              `${job.failed_count ? ` · ${t("referenceFailedCount")} ${job.failed_count}` : ""}` +
              `${job.current_asset ? ` · ${job.current_asset}` : ""} · ${job.duration_seconds || 0}s`,
          );
        } else if (job.status === "done" || job.status === "failed") {
          response = {
            ok: job.status === "done",
            duration_seconds: job.duration_seconds,
            message: job.error_message || job.error || jobResponse.message,
            data: job.result || {
              error_message: job.error_message,
              error: job.error,
            },
          };
          break;
        }
      }
      await refreshAll();
      const filenames = response.data?.references?.map((reference) => reference.filename) || [];
      setReferenceJobProgress({
        completed: response.data?.completed || filenames.length,
        failed: response.data?.failed || 0,
        total: response.data?.planned || nextPlan.length,
        current: "",
      });
      if (filenames.length > 0) {
        setSelectedReferences((current) => Array.from(new Set([...current, ...filenames])));
      }
      if (!response.ok) {
        return response;
      }
      const generationErrors = Array.isArray(response.data?.errors) ? response.data.errors : [];
      return {
        ...response,
        localizedMessage: `${t("referenceProgressDone")} ${filenames.length} · ${response.duration_seconds || 0}s${
          generationErrors.length ? ` · ${generationErrors.join("; ")}` : ""
        }`,
      };
    });
  }

  async function handleAnalyzeReferenceStyle(reference) {
    if (!currentProject || !reference?.filename) return;
    await run(`style-analysis-${reference.filename}`, async () => {
      const response = await api.analyzeReferenceStyle(currentProject.project_id, {
        reference_filename: reference.filename,
        apply_to_bible: true,
      });
      if (response.data?.style_prompt) {
        updateGlobalStyle(response.data.style_prompt);
      }
      if (response.data?.style_analysis) {
        setStyleAnalysis(response.data.style_analysis);
      }
      return {
        ...response,
        localizedMessage: t("referenceStyleAnalyzed"),
      };
    });
  }

  async function handleDeleteReference(reference) {
    if (!currentProject || !reference?.filename) return;
    const confirmed = window.confirm(
      `${t("deleteReferenceConfirm")} ${reference.filename}`,
    );
    if (!confirmed) return;
    await run(`delete-reference-${reference.filename}`, async () => {
      const response = await api.deleteReference(currentProject.project_id, reference.filename);
      setSelectedReferences((current) =>
        current.filter((filename) => filename !== reference.filename),
      );
      await refreshAll();
      return { ...response, localizedMessage: t("referenceDeleted") };
    });
  }

  async function generateOneShot(shotId) {
    if (scriptImportInfo?.storyboardCurrent === false) {
      setMessage(t("storyboardStaleGenerationBlocked"));
      return false;
    }
    setBusyShotId(shotId);
    setMessage("");
    setShotErrors((current) => ({ ...current, [shotId]: "" }));
    mergeShotUpdate(shotId, { status: "generating", generation_error: "" });
    setShotProgressStage(shotId, "generationProgressQueued");
    try {
      await syncBibleBeforeGeneration();
      const startResponse = await api.startGenerationJob(currentProject.project_id, shotId, {
        aspect_presets: selectedAspects,
        reference_filenames: selectedReferences,
        visual_format: visualFormat,
        panel_gutter_style: panelGutterStyle,
        quality: generationQuality,
      });
      if (!startResponse.ok) {
        const errorMessage = responseErrorMessage(startResponse);
        setShotErrors((current) => ({ ...current, [shotId]: errorMessage }));
        setShotProgressStage(shotId, "generationProgressFailed", errorMessage);
        return false;
      }

      const jobId = startResponse.data?.job_id;
      if (!jobId) {
        throw new Error(t("generationJobMissingId"));
      }
      setShotProgressStage(shotId, "generationProgressSubmitting", t("generationProgressWithReferences"));
      let response = null;
      let pollAttempts = 0;
      while (jobId) {
        pollAttempts += 1;
        if (pollAttempts > 320) throw new Error(t("generationPollingTimedOut"));
        await sleep(3000);
        response = await api.getGenerationJob(currentProject.project_id, jobId);
        const job = response.data || {};
        await refreshAll().catch(() => {});
        if (job.status === "queued") {
          setShotProgressStage(shotId, "generationProgressQueued", `${jobId} · ${job.duration_seconds || 0}s`);
        } else if (job.status === "running") {
          mergeShotUpdate(shotId, { status: "generating", generation_error: "" });
          const duration = Number(job.duration_seconds || 0);
          setShotProgressStage(
            shotId,
            "generationProgressSubmitting",
            `${jobId} · ${duration}s${duration >= 180 ? ` · ${t("generationProviderSlow")}` : ""}`,
          );
        } else if (job.status === "done" || job.status === "failed") {
          response = {
            ok: job.status === "done",
            duration_seconds: job.duration_seconds,
            message: job.error_message || job.error || response.message,
            data: job.result || {
              error_message: job.error_message,
              error: job.error,
            },
          };
          break;
        }
      }

      setShotProgressStage(shotId, "generationProgressVerifying");
      await refreshAll();
      if (!response.ok) {
        const shortError = localizedGenerationError(
          response.data?.error_message ||
          response.data?.error ||
          response.data?.short_error ||
          response.data?.error_code ||
          response.message,
        );
        setShotErrors((current) => ({ ...current, [shotId]: shortError }));
        mergeShotUpdate(shotId, { status: "failed", generation_error: shortError });
        setShotProgressStage(shotId, "generationProgressFailed", shortError);
        if (isGlobalGenerationBlocker(response.data?.error_code || response.data?.short_error, shortError)) {
          shouldStopQueueRef.current = true;
        }
        setMessage(shortError);
        return false;
      }
      setShotErrors((current) => ({ ...current, [shotId]: "" }));
      mergeShotUpdate(shotId, {
        status: response.data?.status || "done",
        output_url: response.data?.output_url || "",
        output_path: response.data?.output_path || "",
        outputs: response.data?.outputs || [],
        generation_error: "",
        download_error: response.data?.download_error || "",
      });
      setShotProgressStage(shotId, "generationProgressDone", response.data?.output_url || "");
      setMessage(`${t("imageGenerated")} · ${response.duration_seconds || 0}s`);
      return true;
    } catch (error) {
      await refreshAll().catch(() => {});
      setShotErrors((current) => ({ ...current, [shotId]: error.message }));
      setShotProgressStage(shotId, "generationProgressFailed", error.message);
      if (isGlobalGenerationBlocker("", error.message)) {
        shouldStopQueueRef.current = true;
      }
      setMessage(error.message);
      return false;
    } finally {
      setBusyShotId("");
    }
  }

  async function handleGenerate(shotId) {
    if (!currentProject) return;
    await enqueueGeneration([shotId]);
  }

  async function enqueueGeneration(shotIds) {
    if (scriptImportInfo?.storyboardCurrent === false) {
      setMessage(t("storyboardStaleGenerationBlocked"));
      return;
    }
    const nextIds = shotIds.filter(
      (shotId) =>
        shotId &&
        shotId !== busyShotId &&
        !generationQueueRef.current.includes(shotId),
    );
    if (nextIds.length === 0) return;
    shouldStopQueueRef.current = false;
    generationQueueRef.current = [...generationQueueRef.current, ...nextIds];
    nextIds.forEach((shotId) => setShotProgressStage(shotId, "generationProgressQueued"));
    setQueuedShotIds([...generationQueueRef.current]);
    setMessage(`${t("generationQueueStarted")} ${generationQueueRef.current.length}`);
    if (!processingQueueRef.current) {
      await processGenerationQueue();
    }
  }

  async function processGenerationQueue() {
    if (!currentProject) return;
    processingQueueRef.current = true;
    while (generationQueueRef.current.length > 0 && !shouldStopQueueRef.current) {
      const [shotId, ...remaining] = generationQueueRef.current;
      generationQueueRef.current = remaining;
      setQueuedShotIds([...remaining]);
      await generateOneShot(shotId);
    }
    if (shouldStopQueueRef.current && generationQueueRef.current.length > 0) {
      generationQueueRef.current.forEach((shotId) =>
        setShotProgressStage(shotId, "generationProgressStopped", t("generationQueueStopped")),
      );
    }
    processingQueueRef.current = false;
    setQueuedShotIds([]);
    setMessage(shouldStopQueueRef.current ? t("generationQueueStopped") : t("generationQueueFinished"));
  }

  async function handleBatchGenerate() {
    if (!currentProject) return;
    const pendingShotIds = queueableShots.map((shot) => shot.shot_id);
    await enqueueGeneration(pendingShotIds);
  }

  function stopPendingQueue() {
    shouldStopQueueRef.current = true;
    generationQueueRef.current = [];
    setQueuedShotIds([]);
    setMessage(t("queueStopRequested"));
  }

  function toggleReference(filename) {
    setSelectedReferences((current) =>
      current.includes(filename)
        ? current.filter((item) => item !== filename)
        : [...current, filename],
    );
  }

  function toggleAspect(aspectId) {
    setSelectedAspects((current) => {
      if (current.includes(aspectId) && current.length === 1) {
        setMessage(t("selectAtLeastOneAspect"));
        return current;
      }
      return current.includes(aspectId)
        ? current.filter((item) => item !== aspectId)
        : [...current, aspectId];
    });
  }

  async function exportComicGridPng() {
    try {
      const panels = generatedShots.flatMap((shot) => {
      const outputs = Array.isArray(shot.outputs) ? shot.outputs : [];
      const preferred =
        outputs.find((output) => output.aspect_preset === gridAspect) ||
        outputs[0] ||
        { output_url: shot.output_url };
      return preferred.output_url ? [{ ...shot, output_url: preferred.output_url }] : [];
    });
    if (panels.length === 0) {
      setMessage(t("noGeneratedPanelsExport"));
      return;
    }
    const preset = aspectPresets.find((item) => item.id === gridAspect);
    const [width, height] = (preset?.size || "1024x1792").split("x").map(Number);
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext("2d");
    context.fillStyle = "#f4f1ea";
    context.fillRect(0, 0, width, height);
    const gap = Math.round(width * 0.018);
    const columns = Math.max(1, Number(gridColumns) || 1);
    const rows = Math.ceil(panels.length / columns);
    const cellWidth = Math.floor((width - gap * (columns + 1)) / columns);
    const cellHeight = Math.floor((height - gap * (rows + 1)) / rows);

    for (let index = 0; index < panels.length; index += 1) {
      const image = await loadImage(assetUrl(panels[index].output_url));
      const column = index % columns;
      const row = Math.floor(index / columns);
      const x = gap + column * (cellWidth + gap);
      const y = gap + row * (cellHeight + gap);
      context.fillStyle = "#111318";
      context.fillRect(x - 2, y - 2, cellWidth + 4, cellHeight + 4);
      drawCover(context, image, x, y, cellWidth, cellHeight);
    }

    const blob = await new Promise((resolve, reject) =>
      canvas.toBlob(
        (value) => (value ? resolve(value) : reject(new Error(t("exportFailed")))),
        "image/png",
      ),
    );
    await saveBlobToDesktop(blob, `comic-grid-${gridAspect}.png`);
    } catch (error) {
      setMessage(`${t("exportFailed")} ${error.message}`);
    }
  }

  async function handleExport(format) {
    if (!currentProject) return;
    if (format === "html") {
      const missingCount = shots.filter((shot) => !shot.output_url).length;
      if (missingCount > 0) {
        const confirmed = window.confirm(
          `${t("exportHtmlMissingImagesConfirm")} ${missingCount}`,
        );
        if (!confirmed) return;
      }
    }
    const response = await run(`export-${format}`, () =>
      api.exportProject(currentProject.project_id, format),
    );
    if (response?.data?.url) {
      try {
        const exported = await fetch(assetUrl(response.data.url));
        if (!exported.ok) throw new Error(`HTTP ${exported.status}`);
        const filename = String(response.data.path || response.data.url).split(/[\\/]/).pop();
        await saveBlobToDesktop(await exported.blob(), filename || `paneloom-export.${format}`);
      } catch (error) {
        setMessage(`${t("exportFailed")} ${error.message}`);
      }
    }
  }

  async function handleUploadReference(event) {
    const files = Array.from(event.target.files || []);
    if (!currentProject || files.length === 0) return;
    await run("reference", async () => {
      const responses = [];
      for (const file of files) {
        responses.push(await api.uploadReference(currentProject.project_id, file));
      }
      await refreshAll();
      const filenames = responses.map((response) => response.data?.filename).filter(Boolean);
      setSelectedReferences((current) => Array.from(new Set([...current, ...filenames])));
      return { ok: true, message: `${t("referenceUploaded")} ${responses.length}` };
    });
    event.target.value = "";
  }

  async function handleImportScriptFile(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    setBusy("script-import");
    setMessage("");
    setScriptImportInfo(null);
    try {
      const response = await api.importDocument(file);
      const result = response.data || {};
      const importInfo = {
        filename: result.filename || file.name,
        characterCount: result.character_count || 0,
        warnings: Array.isArray(result.warnings) ? result.warnings : [],
        optimizationCurrent: false,
        bibleCurrent: false,
        storyboardCurrent: false,
      };
      const nextVersions = scriptForm.script
        ? [
            ...scriptVersions,
            {
              script: scriptForm.script,
              created_at: new Date().toISOString(),
              reason: "document_import",
            },
          ].slice(-20)
        : scriptVersions;
      setScriptForm((current) => ({ ...current, script: result.text || "" }));
      setStoryAdvice(null);
      setSelectedReferences([]);
      setScriptVersions(nextVersions);
      const warnings = importInfo.warnings;
      setScriptImportInfo(importInfo);
      await saveWorkspace({
        script: result.text || "",
        script_import: importInfo,
        script_versions: nextVersions,
        story_optimization: null,
        selected_reference_filenames: [],
      });
      setMessage(
        `${t("scriptImportSuccess")} ${result.filename || file.name} · ${
          result.character_count || 0
        } ${t("charactersExtracted")}${warnings.length ? ` · ${warnings.join(" ")}` : ""}`,
      );
    } catch (error) {
      setMessage(`${t("scriptImportFailed")} ${error.message}`);
    } finally {
      setBusy("");
      event.target.value = "";
    }
  }

  function startEdit(shot) {
    setEditingShotId(shot.shot_id);
    setDraftShot({
      scene_id: shot.scene_id || "",
      start_time: shot.start_time || "",
      end_time: shot.end_time || "",
      duration: shot.duration || 0,
      visual_description: shot.visual_description || "",
      prompt: shot.prompt || "",
      negative_prompt: shot.negative_prompt || "",
      revision_notes: shot.revision_notes || "",
    });
  }

  async function saveEdit(shotId) {
    if (!currentProject) return;
    await run("edit-shot", async () => {
      const response = await api.updateShot(currentProject.project_id, shotId, {
        ...draftShot,
        duration: Number(draftShot.duration) || 0,
      });
      setEditingShotId("");
      return response;
    });
  }

  async function deleteShot(shotId) {
    if (!currentProject) return;
    if (!window.confirm(t("deleteShotConfirm"))) return;
    await run("delete-shot", () => api.deleteShot(currentProject.project_id, shotId));
  }

  async function handleSelectVersion(shotId, versionId) {
    if (!currentProject || !versionId) return;
    await run(`select-version-${shotId}`, () =>
      api.selectShotVersion(currentProject.project_id, shotId, versionId),
    );
  }

  async function handleShotLock(shot) {
    if (!currentProject) return;
    const nextLocked = !shot.locked;
    if (nextLocked && !shot.output_url) {
      setMessage(t("lockRequiresImage"));
      return;
    }
    if (nextLocked && !window.confirm(t("lockShotConfirm"))) return;
    await run(`lock-shot-${shot.shot_id}`, () =>
      api.updateShot(currentProject.project_id, shot.shot_id, {
        locked: nextLocked,
        approval_status: nextLocked ? "approved" : "draft",
      }),
    );
  }

  async function moveShot(index, direction) {
    if (!currentProject) return;
    const next = [...shots];
    const target = index + direction;
    if (target < 0 || target >= next.length) return;
    [next[index], next[target]] = [next[target], next[index]];
    setShots(next);
    await run("reorder", () =>
      api.reorderShots(
        currentProject.project_id,
        next.map((shot) => shot.shot_id),
      ),
    );
  }

  async function copyText(text) {
    if (!text) return;
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        const field = document.createElement("textarea");
        field.value = text;
        field.style.position = "fixed";
        field.style.opacity = "0";
        document.body.appendChild(field);
        field.select();
        if (!document.execCommand("copy")) throw new Error(t("textCopyFailed"));
        field.remove();
      }
      setMessage(t("textCopied"));
    } catch (error) {
      setMessage(`${t("textCopyFailed")} ${error.message}`);
    }
  }

  function shotTextForClipboard(shot) {
    return [
      `${t("sceneId")}: ${shot.scene_id || shot.shot_id}`,
      shot.visual_description ? `${t("visualDescription")}: ${shot.visual_description}` : "",
      shot.prompt ? `${t("prompt")}: ${shot.prompt}` : "",
      shot.negative_prompt ? `${t("negativePrompt")}: ${shot.negative_prompt}` : "",
      shot.revision_notes ? `${t("revisionNotes")}: ${shot.revision_notes}` : "",
    ]
      .filter(Boolean)
      .join("\n");
  }

  function storyRiskParts(item) {
    if (item && typeof item === "object") {
      return { risk: String(item.risk || item.issue || ""), solution: String(item.solution || item.mitigation || "") };
    }
    const text = String(item || "");
    const legacy = text.match(/["']risk["']\s*:\s*["']([\s\S]*?)["']\s*,\s*["']solution["']\s*:\s*["']([\s\S]*?)["']\s*\}?$/i);
    return legacy ? { risk: legacy[1], solution: legacy[2] } : { risk: text, solution: "" };
  }

  function scriptBoardLines(text) {
    return String(text || "")
      .replace(/\r\n/g, "\n")
      .split(/\n+|(?<=[。！？!?；;])\s+/)
      .map((line) => line.trim())
      .filter(Boolean);
  }

  async function saveBlobToDesktop(blob, filename) {
    if (!currentProject) return false;
    try {
      const response = await api.saveDesktopExport(currentProject.project_id, blob, filename);
      if (!response.ok) {
        setMessage(response.data?.cancelled ? t("saveCancelled") : response.message);
        return false;
      }
      setMessage(`${t("fileSavedTo")} ${response.data?.path || filename}`);
      return true;
    } catch (error) {
      setMessage(`${t("downloadFailed")} ${error.message}`);
      return false;
    }
  }

  async function downloadTextFile(text, filename = "paneloom-script.txt") {
    if (!text) return;
    const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    await saveBlobToDesktop(blob, filename);
  }

  function openPreview(shot, output = null) {
    const matchedOutput =
      output ||
      (Array.isArray(shot.outputs)
        ? shot.outputs.find((item) => item.output_url === shot.output_url) || shot.outputs[0]
        : null);
    const url = matchedOutput?.output_url || shot.output_url;
    if (!url) return;
    setPreviewImage({
      url,
      title: shot.scene_id || shot.shot_id,
      filename: `${shot.scene_id || shot.shot_id}-${matchedOutput?.aspect_preset || "image"}.png`,
      sizeText: outputSizeText(matchedOutput, t),
      version: outputVersion(shot, matchedOutput),
    });
  }

  function openAssetPreview(reference) {
    if (!reference?.url) return;
    setPreviewImage({
      url: reference.url,
      title: reference.filename,
      filename: reference.filename,
      sizeText: referenceCategoryLabel(reference.category),
      version: reference.filename,
    });
  }

  function referenceCategoryLabel(category) {
    const key = {
      main_characters: "referenceAssetCategory_character_turnaround",
      supporting_characters: "referenceAssetCategory_supporting_character",
      locations: "referenceAssetCategory_location",
      props: "referenceAssetCategory_prop",
      style: "referenceAssetCategory_style",
      character_turnaround: "referenceAssetCategory_character_turnaround",
      character_expression_action: "referenceAssetCategory_character_expression_action",
      supporting_character: "referenceAssetCategory_supporting_character",
      location: "referenceAssetCategory_location",
      prop: "referenceAssetCategory_prop",
    }[category];
    return key ? t(key) : "";
  }

  async function downloadImage(url, filename) {
    try {
      const response = await fetch(assetUrl(url));
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      await saveBlobToDesktop(await response.blob(), filename || "storyboard-image.png");
    } catch (error) {
      setMessage(`${t("downloadFailed")} ${error.message}`);
    }
  }

  if (!currentProject) {
    return (
      <div className="panel">
        <h3>{t("noProjectSelected")}</h3>
        <p className="muted">{t("createOrSelectProject")}</p>
      </div>
    );
  }

  return (
    <section className="storyboard-stack">
      <div className="workflow-strip">
        <div>
          <strong>1</strong>
          <span>{t("stepScript")}</span>
        </div>
        <div>
          <strong>2</strong>
          <span>{t("stepBible")}</span>
        </div>
        <div>
          <strong>3</strong>
          <span>{t("stepRatio")}</span>
        </div>
        <div>
          <strong>4</strong>
          <span>{t("stepGenerate")}</span>
        </div>
        <div>
          <strong>5</strong>
          <span>{t("stepExport")}</span>
        </div>
      </div>

      <form className="panel script-panel" onSubmit={handleBreakdownScript}>
        <div className="section-heading">
          <p className="eyebrow">1</p>
          <h3>{t("scriptBreakdown")}</h3>
        </div>
        <label>
          <span>{t("scriptOrNarration")}</span>
          <textarea
            required
            value={scriptForm.script}
            onChange={(event) => handleScriptTextChange(event.target.value)}
            rows={5}
            placeholder={t("scriptPlaceholder")}
          />
        </label>
        <div className="file-import-row">
          <label>
            <span>{t("importScriptFile")}</span>
            <input
              accept={SCRIPT_IMPORT_ACCEPT}
              disabled={busy === "script-import"}
              onChange={handleImportScriptFile}
              type="file"
            />
          </label>
          <p className="muted">{t("supportedScriptFormats")}</p>
          {busy === "script-import" && <p className="form-message">{t("scriptImporting")}</p>}
          {scriptImportInfo && (
            <>
              <p className="form-message">
                {t("scriptImportedFile")} {scriptImportInfo.filename} ·{" "}
                {scriptImportInfo.characterCount} {t("charactersExtracted")}
                {scriptImportInfo.warnings.length > 0
                  ? ` · ${scriptImportInfo.warnings.join(" ")}`
                  : ""}
              </p>
              {(scriptImportInfo.optimizationCurrent === false ||
                scriptImportInfo.bibleCurrent === false ||
                scriptImportInfo.storyboardCurrent === false) && (
                <div className="alert error">{t("newScriptDerivedDataStale")}</div>
              )}
            </>
          )}
        </div>
        <section className="story-advice-panel">
          <div className="section-heading compact-heading">
            <p className="eyebrow">{t("storyDevelopment")}</p>
            <h3>{t("optimizeStory")}</h3>
          </div>
          <p className="muted">{t("storyOptimizationHint")}</p>
          <label>
            <span>{t("storyGoal")}</span>
            <textarea
              rows={2}
              value={storyGoal}
              onChange={(event) => setStoryGoal(event.target.value)}
              placeholder={t("storyGoalPlaceholder")}
            />
          </label>
          <div className="button-row story-action-row">
            <button
              className="secondary"
              disabled={!cloudAiAvailable || busy === "story-optimization" || !scriptForm.script.trim()}
              onClick={handleOptimizeStory}
              type="button"
            >
              {busy === "story-optimization" ? t("optimizingStory") : t("optimizeStory")}
            </button>
            <button
              className="secondary"
              disabled={!storyAdvice?.improved_script || storyAdvice.stale || storyAdvice.source !== "ai"}
              onClick={applyOptimizedScript}
              type="button"
            >
              {t("applyOptimizedScript")}
            </button>
            <button
              className="secondary"
              disabled={!storyAdvice?.recommended_panel_count || storyAdvice.stale}
              onClick={applyRecommendedPanels}
              type="button"
            >
              {t("applyRecommendedPanels")}
            </button>
            <button
              className="secondary danger"
              disabled={!storyAdvice}
              onClick={discardStoryOptimization}
              type="button"
            >
              {t("discardOptimization")}
            </button>
            <button
              className="secondary"
              disabled={scriptVersions.length === 0}
              onClick={undoScriptChange}
              type="button"
            >
              {t("undoScriptChange")}
            </button>
          </div>
          {storyAdvice ? (
            <div className="story-advice-result">
              {storyAdvice.stale && <div className="alert error">{t("storyOptimizationStale")}</div>}
              <p className="form-message">
                {t("aiResultEvidence")}: {storyAdvice.source === "ai" ? t("sourceAi") : t("sourceLocal")}
                {storyAdvice.provider ? ` · ${storyAdvice.provider}` : ""}
                {storyAdvice.model ? ` · ${storyAdvice.model}` : ""}
                {storyAdvice.duration_seconds != null ? ` · ${storyAdvice.duration_seconds}s` : ""}
                {storyAdvice.analyzed_at ? ` · ${new Date(storyAdvice.analyzed_at).toLocaleString()}` : ""}
              </p>
              {storyAdvice.logline && (
                <div>
                  <strong>{t("storyLogline")}</strong>
                  <p>{storyAdvice.logline}</p>
                </div>
              )}
              {storyAdvice.recommended_panel_count && (
                <div>
                  <strong>{t("recommendedPanels")}</strong>
                  <p>{storyAdvice.recommended_panel_count}</p>
                </div>
              )}
              {Array.isArray(storyAdvice.platform_recommendations) &&
                storyAdvice.platform_recommendations.length > 0 && (
                  <div>
                    <strong>{t("platformAdvice")}</strong>
                    <ul>
                      {storyAdvice.platform_recommendations.map((item, index) => (
                        <li key={`platform-${index}`}>{item}</li>
                      ))}
                    </ul>
                  </div>
                )}
              {Array.isArray(storyAdvice.storyboard_strategy) &&
                storyAdvice.storyboard_strategy.length > 0 && (
                  <div>
                    <strong>{t("storyboardStrategy")}</strong>
                    <ul>
                      {storyAdvice.storyboard_strategy.map((item, index) => (
                        <li key={`strategy-${index}`}>{item}</li>
                      ))}
                    </ul>
                  </div>
                )}
              {Array.isArray(storyAdvice.revision_suggestions) &&
                storyAdvice.revision_suggestions.length > 0 && (
                  <div>
                    <strong>{t("revisionSuggestions")}</strong>
                    <ul>
                      {storyAdvice.revision_suggestions.map((item, index) => (
                        <li key={`revision-${index}`}>{item}</li>
                      ))}
                    </ul>
                  </div>
                )}
              {Array.isArray(storyAdvice.risks) && storyAdvice.risks.length > 0 && (
                <div>
                  <strong>{t("storyRisks")}</strong>
                  <ul>
                    {storyAdvice.risks.map((item, index) => {
                      const parts = storyRiskParts(item);
                      return (
                        <li key={`risk-${index}`}>
                          <strong>{t("riskItemLabel")}:</strong> {parts.risk}
                          {parts.solution && (
                            <span className="risk-solution">
                              <strong>{t("solutionItemLabel")}:</strong> {parts.solution}
                            </span>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                </div>
              )}
              {storyAdvice.improved_script && (
                <div className="script-board">
                  <div className="archive-section-header">
                    <strong>{t("optimizedScript")}</strong>
                    <div className="button-row mini-actions">
                      <button
                        className="chip-button"
                        onClick={() => copyText(storyAdvice.improved_script)}
                        type="button"
                      >
                        {t("copyText")}
                      </button>
                      <button
                        className="chip-button"
                        onClick={() => downloadTextFile(storyAdvice.improved_script, "paneloom-optimized-script.txt")}
                        type="button"
                      >
                        {t("downloadText")}
                      </button>
                    </div>
                  </div>
                  <div className="script-line-list">
                    {scriptBoardLines(storyAdvice.improved_script).map((line, index) => (
                      <div className="script-line" key={`optimized-line-${index}`}>
                        <span>{String(index + 1).padStart(2, "0")}</span>
                        <p>{line}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <p className="muted">{t("noStoryOptimization")}</p>
          )}
        </section>
        <div className="form-row three-col">
          <label>
            <span>{t("panels")}</span>
            <input
              min="1"
              max="80"
              type="number"
              value={scriptForm.target_panel_count}
              onChange={(event) =>
                setScriptForm({ ...scriptForm, target_panel_count: event.target.value })
              }
            />
          </label>
          <label className="checkbox-row">
            <input
              checked={scriptForm.include_dialogue}
              onChange={(event) =>
                setScriptForm({ ...scriptForm, include_dialogue: event.target.checked })
              }
              type="checkbox"
            />
            <span>{t("keepNarrationNotes")}</span>
          </label>
          <label className="checkbox-row">
            <input
              checked={scriptForm.use_ai}
              disabled={!cloudAiAvailable}
              onChange={(event) =>
                setScriptForm({ ...scriptForm, use_ai: event.target.checked })
              }
              type="checkbox"
            />
            <span>{t("useTextModel")}</span>
          </label>
        </div>
        <label>
          <span>{t("visualStyle")}</span>
            <select
              value={stylePresetIdForPrompt(scriptForm.style)}
              onChange={(event) => applyStylePreset(event.target.value)}
            >
            {stylePresets.map((preset) => (
              <option key={preset.id} value={preset.id}>
                {t(preset.labelKey)}
              </option>
            ))}
          </select>
            <input
              value={scriptForm.style}
              onChange={(event) => updateGlobalStyle(event.target.value)}
              onBlur={(event) => saveGlobalStyle(event.target.value)}
              placeholder={t("customStylePrompt")}
            />
          <small className="muted">{t("styleSyncHint")}</small>
        </label>
        <button className="primary" disabled={busy === "script"} type="submit">
          {busy === "script"
            ? t("breakingDown")
            : scriptForm.use_ai
              ? t("createPanelsWithAi")
              : t("splitPanelsLocally")}
        </button>
        <button
          className="secondary"
          disabled={busy === "rewrite-storyboard" || shots.length === 0}
          onClick={handleRewriteStoryboard}
          type="button"
        >
          {busy === "rewrite-storyboard" ? t("rewritingStoryboard") : t("rewriteStoryboard")}
        </button>
      </form>

      <section className="storyboard-layout">
        <div className="left-stack">
          <form className="panel form-panel" onSubmit={handleSaveBible}>
            <div className="section-heading">
              <p className="eyebrow">{t("projectBible")}</p>
              <h3>{t("charactersContinuity")}</h3>
            </div>
            <p className="muted">{t("bibleWorkflowHint")}</p>
            <div className="button-row stacked-actions">
              <button
                className="secondary"
                disabled={!cloudAiAvailable || busy === "analyze-bible"}
                onClick={handleAnalyzeBible}
                type="button"
              >
                {busy === "analyze-bible" ? t("analyzing") : t("analyzeBible")}
              </button>
              <button
                className="secondary"
                disabled={!cloudAiAvailable || busy === "reference-main"}
                onClick={() => handleGenerateReferences(["main_characters"], "reference-main")}
                type="button"
              >
                {busy === "reference-main" ? t("generatingCoreCharacters") : t("generateCoreCharacters")}
              </button>
              <button
                className="secondary"
                disabled={!cloudAiAvailable || busy === "reference-world"}
                onClick={() =>
                  handleGenerateReferences(
                    ["supporting_characters", "props", "locations"],
                    "reference-world",
                  )
                }
                type="button"
              >
                {busy === "reference-world" ? t("generatingWorldAssets") : t("generateWorldAssets")}
              </button>
            </div>
            {referencePlan.length > 0 && (
              <div className="reference-plan-panel">
                <div className="archive-section-header">
                  <strong>{t("referenceAssetPlan")}</strong>
                  <span className="muted">
                    {referenceJobProgress?.completed || 0}/{referenceJobProgress?.total || referencePlan.length}
                    {referenceJobProgress?.failed
                      ? ` · ${t("referenceFailedCount")} ${referenceJobProgress.failed}`
                      : ""}
                    {` · ${t("referenceConcurrency")} 2`}
                  </span>
                </div>
                <div className="reference-plan-list">
                  {referencePlan.map((item) => (
                    <div key={item.asset_id}>
                      <strong>{item.name}</strong>
                      <span>{t(`referenceAssetCategory_${item.category}`)}</span>
                      {item.purpose && <p>{item.purpose}</p>}
                    </div>
                  ))}
                </div>
              </div>
            )}
            {references.length > 0 && (
              <div className="inline-reference-panel">
                <strong>{t("generatedReferenceAssets")}</strong>
                <div className="reference-grid compact-reference-grid">
                  {references.map((reference) => {
                    const checked = selectedReferences.includes(reference.filename);
                    return (
                        <div
                          className={`reference-card ${checked ? "selected" : ""}`}
                          key={`inline-${reference.filename}`}
                        >
                          <button
                            className="reference-tile"
                            onClick={() => toggleReference(reference.filename)}
                            type="button"
                          >
                            <img alt={reference.filename} src={assetUrl(reference.url)} />
                            <span>{reference.name || reference.filename}</span>
                            {reference.purpose && <small>{reference.purpose}</small>}
                          </button>
                          <div className="reference-actions">
                            <button
                              className="chip-button"
                              onClick={() => openAssetPreview(reference)}
                              type="button"
                            >
                              {t("openImage")}
                            </button>
                            <button
                              className="chip-button"
                              onClick={() => downloadImage(reference.url, reference.filename)}
                              type="button"
                            >
                              {t("downloadImage")}
                            </button>
                            <button
                              className="chip-button danger"
                              disabled={busy === `delete-reference-${reference.filename}`}
                              onClick={() => handleDeleteReference(reference)}
                              type="button"
                            >
                              {t("deleteReference")}
                            </button>
                          </div>
                        </div>
                    );
                  })}
                </div>
              </div>
            )}
            <label>
              <span>{t("visualStyle")}</span>
              <select
                value={stylePresetIdForPrompt(bible.visual_style)}
                onChange={(event) => applyStylePreset(event.target.value)}
              >
                {stylePresets.map((preset) => (
                  <option key={preset.id} value={preset.id}>
                    {t(preset.labelKey)}
                  </option>
                ))}
              </select>
              <input
                value={bible.visual_style}
                onChange={(event) => updateGlobalStyle(event.target.value)}
                onBlur={(event) => saveGlobalStyle(event.target.value)}
                placeholder={t("customStylePrompt")}
              />
              <small className="muted">{t("styleSyncHint")}</small>
            </label>
            <label>
              <span>{t("characters")}</span>
              <textarea
                rows={3}
                value={bible.characters}
                onChange={(event) => setBible({ ...bible, characters: event.target.value })}
              />
            </label>
            <label>
              <span>{t("locations")}</span>
              <textarea
                rows={3}
                value={bible.locations}
                onChange={(event) => setBible({ ...bible, locations: event.target.value })}
              />
            </label>
            <label>
              <span>{t("props")}</span>
              <textarea
                rows={3}
                value={bible.props}
                onChange={(event) => setBible({ ...bible, props: event.target.value })}
              />
            </label>
            <label>
              <span>{t("worldNotes")}</span>
              <textarea
                rows={3}
                value={bible.world_notes}
                onChange={(event) => setBible({ ...bible, world_notes: event.target.value })}
              />
            </label>
            <label>
              <span>{t("promptPrefix")}</span>
              <textarea
                rows={2}
                value={bible.prompt_prefix}
                onChange={(event) => setBible({ ...bible, prompt_prefix: event.target.value })}
              />
            </label>
            <label>
              <span>{t("negativePrompt")}</span>
              <textarea
                rows={2}
                value={bible.negative_prompt}
                onChange={(event) => setBible({ ...bible, negative_prompt: event.target.value })}
              />
            </label>
            <label>
              <span>{t("referenceRefinement")}</span>
              <textarea
                rows={2}
                value={referenceRefinement}
                onChange={(event) => setReferenceRefinement(event.target.value)}
                placeholder={t("referenceRefinementPlaceholder")}
              />
            </label>
            <button className="primary" disabled={busy === "bible"} type="submit">
              {busy === "bible" ? t("saving") : t("saveBible")}
            </button>
          </form>

          <form className="panel shot-form" onSubmit={handleAddShot}>
            <div className="section-heading">
              <p className="eyebrow">{t("addShot")}</p>
              <h3>{t("manualPanel")}</h3>
            </div>
            <div className="form-row">
              <label>
                <span>{t("sceneId")}</span>
                <input
                  value={form.scene_id}
                  onChange={(event) => setForm({ ...form, scene_id: event.target.value })}
                  placeholder="P001"
                />
              </label>
              <label>
                <span>{t("duration")}</span>
                <input
                  min="0"
                  step="0.1"
                  type="number"
                  value={form.duration}
                  onChange={(event) => setForm({ ...form, duration: event.target.value })}
                />
              </label>
            </div>
            <label>
              <span>{t("visualDescription")}</span>
              <textarea
                value={form.visual_description}
                onChange={(event) =>
                  setForm({ ...form, visual_description: event.target.value })
                }
                rows={3}
              />
            </label>
            <label>
              <span>{t("prompt")}</span>
              <textarea
                required
                value={form.prompt}
                onChange={(event) => setForm({ ...form, prompt: event.target.value })}
                rows={4}
              />
            </label>
            <label>
              <span>{t("revisionNotes")}</span>
              <textarea
                value={form.revision_notes}
                onChange={(event) =>
                  setForm({ ...form, revision_notes: event.target.value })
                }
                rows={2}
              />
            </label>
            <button className="primary" disabled={busy === "add-shot"} type="submit">
              {t("addShot")}
            </button>
          </form>

          <div className="panel form-panel" id="project-assets">
            <div className="section-heading">
              <p className="eyebrow">{t("projectAssets")}</p>
              <h3>{t("referenceSource")}</h3>
            </div>
            <p className="muted">{t("projectAssetsHint")}</p>
            <p className="muted">{t("referenceHint")}</p>
            <input
              accept="image/png,image/jpeg,image/webp"
              multiple
              onChange={handleUploadReference}
              type="file"
            />
            {references.length === 0 ? (
              <div className="empty-state align-left">
                <strong>{t("noReferenceSelected")}</strong>
                <span>{t("generateOrUploadReference")}</span>
                <p>{t("assetEmptyWhy")}</p>
                <ul className="guide-list">
                  <li>{t("assetTypeCharacters")}</li>
                  <li>{t("assetTypeScenes")}</li>
                  <li>{t("assetTypeStyle")}</li>
                  <li>{t("assetTypeProps")}</li>
                </ul>
              </div>
            ) : (
              <div className="reference-grid">
                {references.map((reference) => {
                  const checked = selectedReferences.includes(reference.filename);
                  return (
                    <div
                      className={`reference-card ${checked ? "selected" : ""}`}
                      key={reference.filename}
                    >
                      <button
                        className="reference-tile"
                        onClick={() => toggleReference(reference.filename)}
                        type="button"
                      >
                        <img alt={reference.filename} src={assetUrl(reference.url)} />
                        <span>{reference.name || reference.filename}</span>
                        {reference.purpose && <small>{reference.purpose}</small>}
                      </button>
                      <div className="reference-actions">
                        <button
                          className="chip-button"
                          onClick={() => openAssetPreview(reference)}
                          type="button"
                        >
                          {t("openImage")}
                        </button>
                        <button
                          className="chip-button"
                          onClick={() => downloadImage(reference.url, reference.filename)}
                          type="button"
                        >
                          {t("downloadImage")}
                        </button>
                        <button
                          className="chip-button"
                          onClick={() => copyUrl(reference.url)}
                          type="button"
                        >
                          {t("copyImageUrl")}
                        </button>
                        <button
                          className="chip-button"
                          disabled={!cloudAiAvailable || busy === `style-analysis-${reference.filename}`}
                          onClick={() => handleAnalyzeReferenceStyle(reference)}
                          type="button"
                        >
                          {busy === `style-analysis-${reference.filename}`
                            ? t("extractingStyle")
                            : t("extractReferenceStyle")}
                        </button>
                        <button
                          className="chip-button danger"
                          disabled={busy === `delete-reference-${reference.filename}`}
                          onClick={() => handleDeleteReference(reference)}
                          type="button"
                        >
                          {t("deleteReference")}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
            <p className="muted">
              {selectedReferences.length} {t("selectedReferenceCount")}
            </p>
            {styleAnalysis && (
              <div className="style-analysis-panel">
                <strong>{t("extractedStyleGuide")}</strong>
                <p>{styleAnalysis}</p>
              </div>
            )}
          </div>
        </div>

        <div className="right-stack">
          <div className="panel tools-panel">
            <div>
              <p className="eyebrow">{t("production")}</p>
              <h3>{t("productionTools")}</h3>
            </div>
            <div className="queue-panel">
              <div>
                <strong>{t("autoQueueTitle")}</strong>
                <p>{t("generationQueueHint")}</p>
              </div>
              <div className="queue-stats">
                <span>
                  {t("storyboardConcurrency")} <strong>1</strong>
                </span>
                <span>
                  {t("queueable")} <strong>{queueableShots.length}</strong>
                </span>
                <span>
                  {t("waiting")} <strong>{queuedShotIds.length}</strong>
                </span>
              </div>
            </div>
            <label className="generation-quality-control">
              <span>{t("generationQuality")}</span>
              <select
                value={generationQuality}
                onChange={(event) => setGenerationQuality(event.target.value)}
              >
                <option value="low">{t("qualityLow")}</option>
                <option value="medium">{t("qualityMedium")}</option>
                <option value="high">{t("qualityHigh")}</option>
              </select>
              <small>{t("generationQualityHint")}</small>
            </label>
            <div className="format-switch" role="group" aria-label={t("visualFormat")}>
              <button
                className={visualFormat === "webtoon_strip" ? "selected" : ""}
                onClick={() => setVisualFormat("webtoon_strip")}
                type="button"
              >
                <strong>{t("formatWebtoonStrip")}</strong>
                <small>{t("formatWebtoonStripHint")}</small>
              </button>
              <button
                className={visualFormat === "single_panel" ? "selected" : ""}
                onClick={() => setVisualFormat("single_panel")}
                type="button"
              >
                <strong>{t("formatSinglePanel")}</strong>
                <small>{t("formatSinglePanelHint")}</small>
              </button>
            </div>
            {visualFormat === "webtoon_strip" && (
              <div className="format-switch compact-mode-switch" role="group" aria-label={t("panelSeparation")}>
                <button
                  className={panelGutterStyle === "framed" ? "selected" : ""}
                  onClick={() => setPanelGutterStyle("framed")}
                  type="button"
                >
                  <strong>{t("panelSeparationFramed")}</strong>
                  <small>{t("panelSeparationFramedHint")}</small>
                </button>
                <button
                  className={panelGutterStyle === "seamless" ? "selected" : ""}
                  onClick={() => setPanelGutterStyle("seamless")}
                  type="button"
                >
                  <strong>{t("panelSeparationSeamless")}</strong>
                  <small>{t("panelSeparationSeamlessHint")}</small>
                </button>
              </div>
            )}
            <div className="aspect-picker">
              {aspectPresets.map((preset) => (
                <label className="checkbox-row compact-check" key={preset.id}>
                  <input
                    checked={selectedAspects.includes(preset.id)}
                    onChange={() => toggleAspect(preset.id)}
                    type="checkbox"
                  />
                  <span>
                    {aspectLabel(preset, t)}
                    <small>{aspectPlatforms(preset, t)}</small>
                  </span>
                </label>
              ))}
            </div>
            <div className="button-row">
              <button
                className="primary"
                disabled={!cloudAiAvailable || processingQueueRef.current}
                onClick={handleBatchGenerate}
                type="button"
              >
                {busyShotId ? t("queueRunning") : t("autoQueueGenerate")}
              </button>
              <button className="secondary" onClick={() => handleExport("json")} type="button">
                {t("exportJson")}
              </button>
              <button className="secondary" onClick={() => handleExport("csv")} type="button">
                {t("exportCsv")}
              </button>
              <button className="secondary" onClick={() => handleExport("xlsx")} type="button">
                {t("exportExcel")}
              </button>
              <button className="secondary" onClick={() => handleExport("srt")} type="button">
                {t("exportSrt")}
              </button>
              <button className="secondary" onClick={() => handleExport("html")} type="button">
                {t("exportComicHtml")}
              </button>
              <button
                className="secondary"
                disabled={!busyShotId && queuedShotIds.length === 0}
                onClick={stopPendingQueue}
                type="button"
              >
                {t("stopQueue")}
              </button>
            </div>
            {(busyShotId || queuedShotIds.length > 0) && (
              <p className="form-message">
                {t("queueStatus")} {busyShotId || "-"} · {queuedShotIds.length}{" "}
                {t("queuedCount")}
              </p>
            )}
            {message && <p className="form-message">{message}</p>}
          </div>

          <div className="panel shot-table-panel">
            <div className="section-heading">
              <p className="eyebrow">{t("storyboard")}</p>
              <h3>{t("storyboardList")} · {shots.length} {t("panelCount")}</h3>
            </div>
            <div className="shot-card-list">
              {shots.length === 0 && (
                <div className="empty-state align-left">
                  <strong>{t("noShotsTitle")}</strong>
                  <span>{t("noShotsBody")}</span>
                  <ol className="guide-list">
                    <li>{t("firstShotStepPasteScript")}</li>
                    <li>{t("firstShotStepBreakdown")}</li>
                    <li>{t("firstShotStepGenerate")}</li>
                  </ol>
                </div>
              )}
              {shots.map((shot, index) => {
                const isEditing = editingShotId === shot.shot_id;
                const hasOutput = Boolean(shot.output_url);
                return (
                  <article className={`shot-card ${shot.locked ? "locked" : ""}`} key={shot.shot_id}>
                    <div className="shot-card-header">
                      <div>
                        <span className="shot-number">#{index + 1}</span>
                        {isEditing ? (
                          <input
                            value={draftShot.scene_id}
                            onChange={(event) =>
                              setDraftShot({ ...draftShot, scene_id: event.target.value })
                            }
                            placeholder={t("sceneId")}
                          />
                        ) : (
                          <h4>{shot.scene_id || t("untitledShot")}</h4>
                        )}
                        <small>{shot.shot_id}</small>
                      </div>
                      <div className="shot-state-badges">
                        {shot.locked && <span className="badge locked">{t("approvedLocked")}</span>}
                        <span className={`badge ${shot.status}`}>{shotStatusLabel(shot.status, t)}</span>
                      </div>
                    </div>

                    <div className="shot-card-body">
                      <div className="shot-main">
                        <label>
                          <span>{t("shotPrompt")}</span>
                          {isEditing ? (
                            <textarea
                              rows={4}
                              value={draftShot.prompt}
                              onChange={(event) =>
                                setDraftShot({ ...draftShot, prompt: event.target.value })
                              }
                            />
                          ) : (
                            <p>{shot.prompt || t("noPrompt")}</p>
                          )}
                        </label>
                        <label>
                          <span>{t("revisionNotes")}</span>
                          {isEditing ? (
                            <textarea
                              rows={2}
                              value={draftShot.revision_notes}
                              onChange={(event) =>
                                setDraftShot({
                                  ...draftShot,
                                  revision_notes: event.target.value,
                                })
                              }
                            />
                          ) : (
                            <p className="muted">{shot.revision_notes || t("noNotes")}</p>
                          )}
                        </label>
                        {shot.download_error && <div className="row-error">{shot.download_error}</div>}
                        {shot.generation_error && (
                          <div className="row-error">{localizedGenerationError(shot.generation_error)}</div>
                        )}
                        {shotErrors[shot.shot_id] &&
                          shotErrors[shot.shot_id] !==
                            localizedGenerationError(shot.generation_error) && (
                          <div className="row-error">{shotErrors[shot.shot_id]}</div>
                        )}
                        {(shotProgress[shot.shot_id] || shot.status === "failed") && (
                          <div
                            className={`generation-progress ${
                              shot.status === "failed" || shotProgress[shot.shot_id]?.stageKey === "generationProgressFailed"
                                ? "failed"
                                : ""
                            }`}
                          >
                            <strong>{t("generationProgressTitle")}</strong>
                            <span>
                              {shotProgressText(shotProgress[shot.shot_id], t) ||
                                shot.generation_error ||
                                shotErrors[shot.shot_id] ||
                                t("generationProgressFailed")}
                            </span>
                          </div>
                        )}
                      </div>

                      <div className="shot-side">
                        {hasOutput ? (
                          <div className="output-stack">
                            {(() => {
                              const primaryOutput = Array.isArray(shot.outputs)
                                ? shot.outputs.find((item) => item.output_url === shot.output_url) ||
                                  shot.outputs[0]
                                : null;
                              return (
                                <button
                                  className="thumb-button output-preview-button"
                                  onClick={() => openPreview(shot)}
                                  style={outputAspectStyle(primaryOutput)}
                                  type="button"
                                >
                                  <img
                                    alt={shot.shot_id}
                                    className="thumb"
                                    src={assetUrl(shot.output_url, outputVersion(shot, primaryOutput))}
                                  />
                                </button>
                              );
                            })()}
                            {Array.isArray(shot.outputs) && shot.outputs.length > 0 && (
                              <div className="output-chips">
                                {shot.outputs.map((output) => (
                                  <button
                                    className="chip-button"
                                    key={`${shot.shot_id}-${output.aspect_preset}`}
                                    onClick={() => openPreview(shot, output)}
                                    type="button"
                                  >
                                    <span>{aspectLabel(output, t)}</span>
                                    {outputSizeText(output, t) && (
                                      <small>{outputSizeText(output, t)}</small>
                                    )}
                                  </button>
                                ))}
                              </div>
                            )}
                            {Array.isArray(shot.outputs) &&
                              shot.outputs.some((output) => output.normalization_error) && (
                                <div className="row-error">
                                  {t("imageSizeMismatch")}
                                </div>
                              )}
                            {Array.isArray(shot.versions) && shot.versions.length > 0 && (
                              <div className="version-list">
                                <p className="muted">
                                  {t("currentVersion")} {shot.versions.length} ·{" "}
                                  {t("historyVersions")} {Math.max(0, shot.versions.length - 1)}
                                </p>
                                <div className="output-chips">
                                  {shot.versions.map((version, versionIndex) => {
                                    const selected =
                                      shot.selected_version_id === version.version_id ||
                                      (!shot.selected_version_id &&
                                        versionIndex === shot.versions.length - 1);
                                    return (
                                      <button
                                        className={`chip-button ${selected ? "selected" : ""}`}
                                        disabled={selected || shot.locked}
                                        key={version.version_id}
                                        onClick={() =>
                                          handleSelectVersion(shot.shot_id, version.version_id)
                                        }
                                        type="button"
                                      >
                                        {selected ? t("selectedVersion") : t("selectVersion")} {versionIndex + 1}
                                      </button>
                                    );
                                  })}
                                </div>
                              </div>
                            )}
                          </div>
                        ) : (
                          <div className="empty-output">{t("noImageYet")}</div>
                        )}
                        <div className="order-tools">
                          <button
                            className="icon-button"
                            onClick={() => moveShot(index, -1)}
                            title={t("moveUp")}
                            type="button"
                          >
                            ↑
                          </button>
                          <button
                            className="icon-button"
                            onClick={() => moveShot(index, 1)}
                            title={t("moveDown")}
                            type="button"
                          >
                            ↓
                          </button>
                        </div>
                      </div>
                    </div>

                    <div className="shot-actions">
                      {isEditing ? (
                        <>
                          <button className="primary" onClick={() => saveEdit(shot.shot_id)} type="button">
                            {t("saveChanges")}
                          </button>
                          <button className="secondary" onClick={() => setEditingShotId("")} type="button">
                            {t("cancel")}
                          </button>
                        </>
                      ) : (
                        <>
                          <button
                            className="primary"
                            disabled={
                              !cloudAiAvailable ||
                              shot.locked ||
                              busyShotId === shot.shot_id ||
                              queuedShotIds.includes(shot.shot_id)
                            }
                            onClick={() => handleGenerate(shot.shot_id)}
                            type="button"
                          >
                            {busyShotId === shot.shot_id
                              ? t("generating")
                              : queuedShotIds.includes(shot.shot_id)
                                ? t("queued")
                                : t("generateImage")}
                          </button>
                          <button
                            className="secondary"
                            disabled={shot.locked}
                            onClick={() => startEdit(shot)}
                            type="button"
                          >
                            {t("editShot")}
                          </button>
                          <button
                            className="secondary"
                            onClick={() => copyText(shotTextForClipboard(shot))}
                            type="button"
                          >
                            {t("copyStoryboardText")}
                          </button>
                          <button
                            className={`secondary ${shot.locked ? "" : "danger"}`}
                            onClick={() => handleShotLock(shot)}
                            title={shot.locked ? t("unlockShot") : t("approveAndLock")}
                            type="button"
                          >
                            {shot.locked ? <Unlock aria-hidden="true" size={16} /> : <Lock aria-hidden="true" size={16} />}
                            {shot.locked ? t("unlockShot") : t("approveAndLock")}
                          </button>
                          <button
                            className="secondary danger"
                            disabled={shot.locked}
                            onClick={() => deleteShot(shot.shot_id)}
                            type="button"
                          >
                            {t("delete")}
                          </button>
                        </>
                      )}
                    </div>
                  </article>
                );
              })}
            </div>
          </div>

          <div className="panel production-archive-panel">
            <div className="section-heading">
              <p className="eyebrow">{t("productionArchive")}</p>
              <h3>{t("archiveTitle")}</h3>
            </div>
            <div className="archive-summary">
              <span>
                {t("archiveReferences")} <strong>{references.length}</strong>
              </span>
              <span>
                {t("archiveGeneratedImages")} <strong>{generatedShots.length}</strong>
              </span>
              <span>
                {t("archiveStyleLock")} <strong>{stylePresetIdForPrompt(bible.visual_style) === "custom" ? t("styleCustom") : t(stylePresets.find((preset) => preset.id === stylePresetIdForPrompt(bible.visual_style))?.labelKey || "styleCustom")}</strong>
              </span>
            </div>

            <div className="archive-section">
              <div className="archive-section-header">
                <strong>{t("archiveScripts")}</strong>
                {(storyAdvice?.improved_script || scriptForm.script) && (
                  <button
                    className="chip-button"
                    onClick={() => copyText(storyAdvice?.improved_script || scriptForm.script)}
                    type="button"
                  >
                    {t("copyText")}
                  </button>
                )}
              </div>
              {storyAdvice?.improved_script ? (
                <textarea
                  className="archive-textarea"
                  readOnly
                  rows={5}
                  value={storyAdvice.improved_script}
                  aria-label={t("optimizedScriptSnapshot")}
                />
              ) : scriptForm.script ? (
                <textarea
                  className="archive-textarea"
                  readOnly
                  rows={5}
                  value={scriptForm.script}
                  aria-label={t("currentScriptSnapshot")}
                />
              ) : (
                <p className="muted">{t("noScriptSnapshot")}</p>
              )}
            </div>

            <div className="archive-section">
              <div className="archive-section-header">
                <strong>{t("archiveReferences")}</strong>
                <span className="muted">{t("archiveReferencesHint")}</span>
              </div>
              {references.length === 0 ? (
                <p className="muted">{t("noArchivedReferences")}</p>
              ) : (
                <div className="reference-grid compact-reference-grid">
                  {references.map((reference) => (
                    <div className="reference-card" key={`archive-${reference.filename}`}>
                      <button
                        className="reference-tile"
                        onClick={() => openAssetPreview(reference)}
                        type="button"
                      >
                        <img alt={reference.filename} src={assetUrl(reference.url)} />
                        <span>{reference.name || reference.filename}</span>
                        {reference.purpose && <small>{reference.purpose}</small>}
                      </button>
                      <div className="reference-actions">
                        <button
                          className="chip-button"
                          onClick={() => openAssetPreview(reference)}
                          type="button"
                        >
                          {t("openImage")}
                        </button>
                        <button
                          className="chip-button"
                          onClick={() => downloadImage(reference.url, reference.filename)}
                          type="button"
                        >
                          {t("downloadImage")}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="archive-section">
              <div className="archive-section-header">
                <strong>
                  {generatedShots.length} {t("generatedPanels")}
                </strong>
                <span className="muted">{t("archiveGeneratedHint")}</span>
              </div>
              <div className="comic-grid">
                {generatedShots.length === 0 && <p className="muted">{t("generatedImagesAppear")}</p>}
                {generatedShots.map((shot) => (
                  <article className="comic-panel" key={shot.shot_id}>
                    <button
                      className="thumb-button comic-preview-button"
                      onClick={() => openPreview(shot)}
                      style={outputAspectStyle(
                        Array.isArray(shot.outputs)
                          ? shot.outputs.find((item) => item.output_url === shot.output_url) ||
                              shot.outputs[0]
                          : null,
                      )}
                      type="button"
                    >
                      <img
                        alt={shot.shot_id}
                        src={assetUrl(
                          shot.output_url,
                          outputVersion(
                            shot,
                            Array.isArray(shot.outputs)
                              ? shot.outputs.find((item) => item.output_url === shot.output_url) ||
                                  shot.outputs[0]
                              : null,
                          ),
                        )}
                      />
                    </button>
                    <strong>{shot.scene_id || shot.shot_id}</strong>
                    {shot.revision_notes && <small>{shot.revision_notes}</small>}
                  </article>
                ))}
              </div>
            </div>

            <section className="grid-export-section" aria-labelledby="comic-grid-export-title">
              <div>
                <strong id="comic-grid-export-title">{t("comicGridExport")}</strong>
                <p className="muted">{t("comicGridExportHint")}</p>
              </div>
              <div className="grid-export-tools">
                <label>
                  <span>{t("gridCanvas")}</span>
                  <select value={gridAspect} onChange={(event) => setGridAspect(event.target.value)}>
                    {aspectPresets.map((preset) => (
                      <option key={preset.id} value={preset.id}>
                        {aspectLabel(preset, t)}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>{t("imagesPerRow")}</span>
                  <select
                    value={gridColumns}
                    onChange={(event) => setGridColumns(Number(event.target.value))}
                  >
                    {[1, 2, 3, 4].map((columns) => (
                      <option key={columns} value={columns}>
                        {columns} {t("columns")}
                      </option>
                    ))}
                  </select>
                </label>
                <button className="primary" onClick={exportComicGridPng} type="button">
                  {t("exportGridPng")}
                </button>
                <small className="muted grid-export-summary">
                  {t("gridExportSummary")} {generatedShots.length} · {t("gridRows")} {Math.ceil(generatedShots.length / Math.max(1, Number(gridColumns) || 1))}
                </small>
              </div>
            </section>
          </div>
        </div>
      </section>
      {previewImage && (
        <div className="image-modal" role="dialog" aria-modal="true">
          <div className="image-modal-content">
            <div className="image-modal-header">
              <strong>{previewImage.title}</strong>
              <button className="icon-button" onClick={() => setPreviewImage(null)} type="button">
                ×
              </button>
            </div>
            {previewImage.sizeText && <p className="muted">{previewImage.sizeText}</p>}
            <img
              alt={previewImage.title}
              src={assetUrl(previewImage.url, previewImage.version)}
            />
            <div className="button-row">
              <button
                className="primary"
                onClick={() => downloadImage(previewImage.url, previewImage.filename)}
                type="button"
              >
                {t("downloadImage")}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
