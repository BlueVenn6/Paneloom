import { useEffect, useState } from "react";

import { api } from "../api";
import { useI18n } from "../i18n.jsx";

const officialBaseUrl = "https://api.openai.com/v1";
const googleOpenAiBaseUrl = "https://generativelanguage.googleapis.com/v1beta/openai";
const glmBaseUrl = "https://open.bigmodel.cn/api/paas/v4";

const defaults = {
  provider_type: "custom",
  base_url: "",
  api_key: "",
  text_provider: "gpt",
  text_provider_mode: "native",
  text_base_url: "",
  text_api_key: "",
  text_model: "gpt-5.5",
  image_model: "gpt-image-2",
  image_size: "1024x1024",
  image_quality: "low",
  image_result_mode: "auto",
};

export default function SettingsPage() {
  const { t } = useI18n();
  const [form, setForm] = useState(defaults);
  const [maskedKey, setMaskedKey] = useState("");
  const [maskedTextKey, setMaskedTextKey] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState("");

  useEffect(() => {
    api
      .getSettings()
      .then((response) => {
        const data = response.data || {};
        setForm({
          ...defaults,
          ...data,
          api_key: "",
          text_api_key: "",
          base_url:
            data.provider_type === "official"
              ? officialBaseUrl
              : data.base_url || defaults.base_url,
        });
        setMaskedKey(data.api_key || "");
        setMaskedTextKey(data.text_api_key || "");
      })
      .catch((error) => setMessage(error.message));
  }, []);

  const providerType = form.provider_type;
  const textProvider = form.text_provider;
  const textMode = form.text_provider_mode;
  const effectiveForm = {
    ...form,
    base_url: providerType === "official" ? officialBaseUrl : form.base_url,
    text_base_url:
      textMode === "native"
        ? textProvider === "glm"
          ? glmBaseUrl
          : textProvider === "google"
            ? ""
            : officialBaseUrl
        : form.text_base_url,
  };

  function update(field, value) {
    const next = { ...form, [field]: value };
    if (field === "provider_type" && value === "official") {
      next.base_url = officialBaseUrl;
    }
    if (field === "text_provider") {
      if (value === "glm") next.text_model = "glm-4.5";
      if (value === "google") next.text_model = "gemini-3.5-flash";
      if (value === "gpt") next.text_model = "gpt-5.5";
    }
    if (field === "text_provider_mode" && value === "relay" && form.text_provider === "google") {
      next.text_base_url = googleOpenAiBaseUrl;
    }
    setForm(next);
  }

  async function save() {
    setBusy("save");
    setMessage("");
    try {
      const response = await api.saveSettings(effectiveForm);
      setMaskedKey(response.data?.api_key || "");
      setMaskedTextKey(response.data?.text_api_key || "");
      setForm({ ...effectiveForm, api_key: "", text_api_key: "" });
      setMessage(t("settingsSaved"));
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy("");
    }
  }

  async function test() {
    setBusy("test");
    setMessage("");
    try {
      const response = await api.testSettings(effectiveForm);
      if (!response.ok) {
        const imageErrors = response.data?.image?.errors || [];
        const textErrors = response.data?.text?.errors || [];
        const errors = [...imageErrors, ...textErrors].map((item) =>
          typeof item === "string" ? item : JSON.stringify(item),
        );
        throw new Error(errors.join(" · ") || response.message || t("connectionTestFailed"));
      }
      setMessage(t("connectionTested"));
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy("");
    }
  }

  return (
    <section className="content-grid two-col">
      <div className="panel form-panel">
        <div className="section-heading">
          <p className="eyebrow">{t("textModel")}</p>
          <h3>{t("textModelProviderTitle")}</h3>
        </div>

        <label>
          <span>{t("textProvider")}</span>
          <select
            value={textProvider}
            onChange={(event) => update("text_provider", event.target.value)}
          >
            <option value="gpt">GPT / OpenAI</option>
            <option value="glm">GLM / Zhipu</option>
            <option value="google">Google Gemini</option>
          </select>
        </label>

        <label>
          <span>{t("textMode")}</span>
          <select
            value={textMode}
            onChange={(event) => update("text_provider_mode", event.target.value)}
          >
            <option value="native">{t("nativeMode")}</option>
            <option value="relay">{t("relayMode")}</option>
          </select>
        </label>

        <label>
          <span>{t("textBaseUrl")}</span>
          <input
            readOnly={textMode === "native"}
            value={effectiveForm.text_base_url}
            onChange={(event) => update("text_base_url", event.target.value)}
            placeholder={
              textProvider === "google"
                ? googleOpenAiBaseUrl
                : textProvider === "glm"
                  ? glmBaseUrl
                  : officialBaseUrl
            }
          />
        </label>

        <label>
          <span>{t("textApiKey")}</span>
          <input
            autoComplete="new-password"
            type="password"
            value={form.text_api_key}
            onChange={(event) => update("text_api_key", event.target.value)}
            placeholder={maskedTextKey || t("textKeyFallback")}
          />
        </label>

        <label>
          <span>{t("textModelName")}</span>
          <input
            value={form.text_model}
            onChange={(event) => update("text_model", event.target.value)}
            placeholder="gpt-5.5 / glm-4.5 / gemini-3.5-flash"
          />
        </label>

        <div className="section-heading">
          <p className="eyebrow">{t("imageProvider")}</p>
          <h3>{t("imageProviderTitle")}</h3>
        </div>

        <label>
          <span>{t("imageProviderType")}</span>
          <select
            value={providerType}
            onChange={(event) => update("provider_type", event.target.value)}
          >
            <option value="official">{t("officialOpenAI")}</option>
            <option value="custom">{t("customCompatible")}</option>
          </select>
        </label>

        <label>
          <span>{t("baseUrl")}</span>
          <input
            readOnly={providerType === "official"}
            value={effectiveForm.base_url}
            onChange={(event) => update("base_url", event.target.value)}
            placeholder="https://api.codexzh.com/v1"
          />
        </label>

        <label>
          <span>{t("apiKey")}</span>
          <input
            autoComplete="new-password"
            type="password"
            value={form.api_key}
            onChange={(event) => update("api_key", event.target.value)}
            placeholder={maskedKey || t("storedLocally")}
          />
        </label>

        <div className="form-row">
          <label>
            <span>{t("imageModel")}</span>
            <input
              value={form.image_model}
              onChange={(event) => update("image_model", event.target.value)}
              placeholder="gpt-image-2"
            />
          </label>
        </div>

        <div className="form-row">
          <label>
            <span>{t("imageSize")}</span>
            <input
              value={form.image_size}
              onChange={(event) => update("image_size", event.target.value)}
              placeholder="1024x1024"
            />
          </label>
          <label>
            <span>{t("imageQuality")}</span>
            <select
              value={form.image_quality}
              onChange={(event) => update("image_quality", event.target.value)}
            >
              <option value="low">{t("qualityLow")}</option>
              <option value="medium">{t("qualityMedium")}</option>
              <option value="high">{t("qualityHigh")}</option>
            </select>
          </label>
        </div>

        <label>
          <span>{t("imageResultMode")}</span>
          <select
            value={form.image_result_mode}
            onChange={(event) => update("image_result_mode", event.target.value)}
          >
            <option value="auto">auto</option>
            <option value="prefer_b64_json">prefer_b64_json</option>
            <option value="url_only">url_only</option>
          </select>
        </label>

        <div className="button-row">
          <button className="primary" disabled={busy === "save"} onClick={save} type="button">
            {busy === "save" ? t("saving") : t("saveSettings")}
          </button>
          <button className="secondary" disabled={busy === "test"} onClick={test} type="button">
            {busy === "test" ? t("testing") : t("testConnection")}
          </button>
        </div>
        {message && <p className="form-message">{message}</p>}
      </div>

      <div className="panel">
        <div className="section-heading">
          <p className="eyebrow">{t("security")}</p>
          <h3>{t("localConfiguration")}</h3>
        </div>
        <p className="muted">{t("securityNote")}</p>
        <dl className="settings-notes">
          <dt>{t("defaultImageModel")}</dt>
          <dd>gpt-image-2</dd>
          <dt>{t("officialBaseUrl")}</dt>
          <dd>https://api.openai.com/v1</dd>
          <dt>{t("customBaseUrlExample")}</dt>
          <dd>https://api.codexzh.com/v1</dd>
          <dt>{t("imageResultMode")}</dt>
          <dd>{t("imageResultModeNote")}</dd>
        </dl>
      </div>
    </section>
  );
}
