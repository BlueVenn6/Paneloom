from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class ApiResponse(BaseModel):
    ok: bool
    message: str
    data: Any | None = None


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    parent_directory: str = Field(default="", max_length=32_767)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Project name cannot be blank.")
        return cleaned


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    archived: bool | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Project name cannot be blank.")
        return cleaned


class ProjectWorkspacePayload(BaseModel):
    script: str = Field(default="", max_length=500_000)
    script_import: dict[str, Any] = Field(default_factory=dict)
    script_versions: list[dict[str, Any]] = Field(default_factory=list, max_length=20)
    story_goal: str = Field(default="", max_length=10_000)
    story_optimization: dict[str, Any] | None = None
    target_panel_count: int = Field(default=8, ge=1, le=80)
    include_dialogue: bool = True
    use_ai: bool = True
    visual_format: Literal["single_panel", "webtoon_strip"] = "webtoon_strip"
    panel_gutter_style: Literal["framed", "seamless"] = "framed"
    generation_quality: Literal["low", "medium", "high"] = "medium"
    selected_aspects: list[str] = Field(default_factory=lambda: ["vertical_9_16"])
    selected_reference_filenames: list[str] = Field(default_factory=list)


class ProjectInfo(BaseModel):
    project_id: str
    name: str
    description: str = ""
    created_at: str
    updated_at: str
    project_path: str
    archived: bool = False


class ProjectPathRequest(BaseModel):
    path: str = Field(..., min_length=1, max_length=32_767)


class ProjectMigrationRequest(BaseModel):
    destination_parent: str = Field(default="", max_length=32_767)


class ProjectBackupRequest(BaseModel):
    destination_directory: str = Field(default="", max_length=32_767)
    include_exports: bool = True


class ProjectRestoreRequest(BaseModel):
    backup_path: str = Field(..., min_length=1, max_length=32_767)
    destination_parent: str = Field(default="", max_length=32_767)
    restored_name: str = Field(default="", max_length=120)


class ShotCreate(BaseModel):
    scene_id: str = ""
    start_time: str = ""
    end_time: str = ""
    duration: float = Field(default=0, ge=0, le=86_400)
    visual_description: str = ""
    prompt: str = Field(..., min_length=1)
    negative_prompt: str = ""
    revision_notes: str = ""


class ShotUpdate(BaseModel):
    scene_id: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    duration: float | None = Field(default=None, ge=0, le=86_400)
    visual_description: str | None = None
    prompt: str | None = None
    negative_prompt: str | None = None
    revision_notes: str | None = None
    status: str | None = None
    approval_status: Literal["draft", "review", "approved", "rejected"] | None = None
    locked: bool | None = None


class ShotReorderRequest(BaseModel):
    shot_ids: list[str] = Field(..., min_length=1)


class ShotMergeNextRequest(BaseModel):
    next_shot_id: str = Field(..., min_length=1)


class ShotPairMergeRequest(BaseModel):
    shot_ids: list[str] = Field(..., min_length=2)


class ShotRewriteRequest(BaseModel):
    script: str = ""
    style: str = "black and white manga storyboard"
    visual_format: Literal["single_panel", "webtoon_strip"] = "single_panel"
    panel_gutter_style: Literal["framed", "seamless"] = "framed"
    use_ai: bool = True
    reset_outputs: bool = True


class BatchGenerateRequest(BaseModel):
    shot_ids: list[str] = []
    only_pending: bool = True
    stop_on_error: bool = False
    aspect_presets: list[str] = []
    reference_filenames: list[str] = []
    visual_format: Literal["single_panel", "webtoon_strip"] = "single_panel"
    panel_gutter_style: Literal["framed", "seamless"] = "framed"


class ProjectBiblePayload(BaseModel):
    visual_style: str = ""
    characters: str = ""
    locations: str = ""
    props: str = ""
    world_notes: str = ""
    prompt_prefix: str = ""
    negative_prompt: str = ""
    style_analysis: str = ""
    style_reference_filename: str = ""
    visual_continuity_lock: str = ""
    visual_anchor_shot_id: str = ""
    visual_anchor_metrics: dict[str, Any] = Field(default_factory=dict)


class ProjectBibleAnalyzeRequest(BaseModel):
    script: str = ""
    use_ai: bool = True
    replace_existing: bool = False


class ExportRequest(BaseModel):
    format: Literal["json", "csv", "xlsx", "srt", "html"] = "json"


class SchedulePlanRequest(BaseModel):
    start_date: str = ""
    target_publish_date: str = Field(..., min_length=1)
    update_frequency_per_week: int = Field(default=3, ge=1, le=14)
    daily_available_hours: float = Field(default=2.0, ge=0.25, le=16)
    platforms: list[str] = []
    total_content_items: int = Field(default=4, ge=1, le=365)
    panels_per_content: int = Field(default=8, ge=1, le=120)
    workflow_steps: list[str] = []


class ScheduleTaskUpdate(BaseModel):
    status: Literal["todo", "doing", "done", "blocked", "skipped", "unknown"] | None = None
    date: str | None = None
    title: str | None = None
    estimate_minutes: int | None = Field(default=None, ge=1, le=1440)
    actual_minutes: int | None = Field(default=None, ge=0, le=1440)
    notes: str | None = None


class TimeLogCreate(BaseModel):
    task_id: str = ""
    date: str = ""
    minutes: int = Field(..., ge=1, le=1440)
    stage: str = ""
    flow_state: Literal["smooth", "normal", "blocked", "rework", "unknown"] = "normal"
    blocker: str = ""
    notes: str = ""


class ProjectActivityHeartbeat(BaseModel):
    seconds: int = Field(..., ge=1, le=60)
    page: Literal["dashboard", "projects", "storyboard", "schedule", "settings", "unknown"] = "unknown"


class SocialFeedbackCreate(BaseModel):
    content_id: str = ""
    platform: str = Field(..., min_length=1)
    publish_date: str = ""
    title: str = ""
    aspect_ratio: str = ""
    format: str = ""
    views: int = Field(default=0, ge=0)
    likes: int = Field(default=0, ge=0)
    comments: int = Field(default=0, ge=0)
    saves: int = Field(default=0, ge=0)
    shares: int = Field(default=0, ge=0)
    completion_rate: float = Field(default=0, ge=0, le=100)
    snapshot_date: str = ""
    conversions: int = Field(default=0, ge=0)
    revenue: float = Field(default=0, ge=0)
    currency: str = "USD"
    judgment: Literal["great", "good", "average", "poor", "unknown"] = "unknown"
    notes: str = ""


class SocialFeedbackScreenshotRequest(BaseModel):
    platform: str = ""
    publish_date: str = ""
    content_id: str = ""
    use_ai: bool = True


class ReviewRequest(BaseModel):
    period: Literal["week", "month"] = "week"
    anchor_date: str = ""


class ScriptBreakdownRequest(BaseModel):
    script: str = Field(..., min_length=1)
    style: str = "black and white manga storyboard"
    visual_format: Literal["single_panel", "webtoon_strip"] = "single_panel"
    panel_gutter_style: Literal["framed", "seamless"] = "framed"
    target_panel_count: int = Field(default=8, ge=1, le=80)
    include_dialogue: bool = True
    use_ai: bool = True


class StoryOptimizationRequest(BaseModel):
    script: str = Field(..., min_length=1)
    goal: str = ""
    style: str = "black and white manga storyboard"
    target_platforms: list[str] = []
    use_ai: bool = True
    output_language: str = "source"


class ShotInfo(BaseModel):
    shot_id: str
    scene_id: str = ""
    start_time: str = ""
    end_time: str = ""
    duration: float = 0
    visual_description: str = ""
    prompt: str = ""
    negative_prompt: str = ""
    status: str = "pending"
    approval_status: Literal["draft", "review", "approved", "rejected"] = "draft"
    locked: bool = False
    locked_at: str = ""
    output_path: str = ""
    output_url: str = ""
    outputs: list[dict] = []
    versions: list[dict] = []
    download_error: str = ""
    revision_notes: str = ""
    created_at: str = ""
    updated_at: str = ""


class ImageGenerationRequest(BaseModel):
    prompt: str | None = None
    size: str | None = None
    quality: Literal["low", "medium", "high"] | None = None
    aspect_presets: list[str] = []
    reference_filenames: list[str] = []
    visual_format: Literal["single_panel", "webtoon_strip"] = "single_panel"
    panel_gutter_style: Literal["framed", "seamless"] = "framed"


class ReferenceAssetPlanItem(BaseModel):
    asset_id: str = Field(..., min_length=1, max_length=80)
    category: Literal[
        "character_turnaround",
        "character_expression_action",
        "supporting_character",
        "location",
        "prop",
        "style",
    ]
    name: str = Field(..., min_length=1, max_length=120)
    purpose: str = Field(default="", max_length=500)
    image_prompt: str = Field(..., min_length=1, max_length=5000)


class ReferenceConceptRequest(BaseModel):
    script: str = ""
    categories: list[
        Literal["main_characters", "supporting_characters", "locations", "props", "style"]
    ] = Field(
        default_factory=lambda: ["main_characters", "supporting_characters", "locations", "props"],
    )
    refinement_prompt: str = ""
    plan: list[ReferenceAssetPlanItem] = Field(default_factory=list, max_length=12)


class ReferenceAssetPlanRequest(BaseModel):
    script: str = ""
    categories: list[
        Literal["main_characters", "supporting_characters", "locations", "props", "style"]
    ] = Field(default_factory=list)
    refinement_prompt: str = ""


class ReferenceStyleAnalysisRequest(BaseModel):
    reference_filename: str = Field(..., min_length=1)
    apply_to_bible: bool = True


class ImageGenerationResult(BaseModel):
    project_id: str
    shot_id: str
    status: str
    output_path: str = ""
    output_url: str = ""
    error: str = ""


class SettingsPayload(BaseModel):
    provider_type: Literal["official", "custom"] = "custom"
    base_url: str = ""
    api_key: str = ""
    text_provider: Literal["gpt", "glm", "google"] = "gpt"
    text_provider_mode: Literal["native", "relay"] = "native"
    text_base_url: str = ""
    text_api_key: str = ""
    text_model: str = "gpt-5.5"
    image_model: str = "gpt-image-2"
    image_quality: Literal["low", "medium", "high"] = "low"
    image_result_mode: Literal["auto", "prefer_b64_json", "url_only"] = "auto"
    clear_saved_keys: bool = False


class UiPreferencesPayload(BaseModel):
    current_project_id: str = ""
    language_selection: Literal["system", "zh-CN", "zh-TW", "en", "ja", "ko"] = "system"
