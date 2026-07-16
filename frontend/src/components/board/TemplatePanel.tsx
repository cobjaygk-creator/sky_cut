import { useEffect, useState } from "react";
import { authorizedRequest } from "../../api/client";
import type { SubtitleTemplate } from "../../types";

type Draft = {
  name: string;
  font_size: number;
  primary_color: string;
  outline_color: string;
  back_color: string;
  bold: boolean;
  outline: number;
  shadow: number;
  margin_v: number;
  border_style: number;
};

const EMPTY_DRAFT: Draft = {
  name: "내 템플릿",
  font_size: 64,
  primary_color: "#FFFFFF",
  outline_color: "#000000",
  back_color: "#000000",
  bold: true,
  outline: 4,
  shadow: 1,
  margin_v: 180,
  border_style: 1,
};

function draftFromTemplate(template: SubtitleTemplate): Draft {
  return {
    name: template.name,
    font_size: template.font_size,
    primary_color: template.primary_color,
    outline_color: template.outline_color,
    back_color: template.back_color,
    bold: template.bold,
    outline: template.outline,
    shadow: template.shadow,
    margin_v: template.margin_v,
    border_style: template.border_style,
  };
}

export function TemplatePanel({
  appliedTemplateId,
  onApply,
  applying,
}: {
  appliedTemplateId: number | null;
  onApply: (templateId: number) => Promise<void>;
  applying: boolean;
}) {
  const [templates, setTemplates] = useState<SubtitleTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [creating, setCreating] = useState(false);
  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT);
  const [saving, setSaving] = useState(false);

  async function loadTemplates() {
    setLoading(true);
    setError("");
    try {
      const loaded = await authorizedRequest<SubtitleTemplate[]>("/subtitle-templates");
      setTemplates(loaded);
    } catch (err) {
      setError(err instanceof Error ? err.message : "템플릿을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadTemplates();
  }, []);

  function startCreate() {
    setCreating(true);
    setEditingId(null);
    setDraft(EMPTY_DRAFT);
  }

  function startEdit(template: SubtitleTemplate) {
    if (template.is_system) return;
    setCreating(false);
    setEditingId(template.id);
    setDraft(draftFromTemplate(template));
  }

  function cancelForm() {
    setCreating(false);
    setEditingId(null);
    setDraft(EMPTY_DRAFT);
  }

  async function handleSave() {
    setSaving(true);
    setError("");
    try {
      const body = {
        name: draft.name,
        font_name: "Malgun Gothic",
        font_size: draft.font_size,
        primary_color: draft.primary_color,
        outline_color: draft.outline_color,
        back_color: draft.back_color,
        bold: draft.bold,
        outline: draft.outline,
        shadow: draft.shadow,
        margin_v: draft.margin_v,
        border_style: draft.border_style,
      };
      if (creating) {
        await authorizedRequest<SubtitleTemplate>("/subtitle-templates", {
          method: "POST",
          body: JSON.stringify(body),
        });
      } else if (editingId != null) {
        await authorizedRequest<SubtitleTemplate>(`/subtitle-templates/${editingId}`, {
          method: "PATCH",
          body: JSON.stringify(body),
        });
      }
      cancelForm();
      await loadTemplates();
    } catch (err) {
      setError(err instanceof Error ? err.message : "템플릿 저장에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  }

  async function handleClone(templateId: number) {
    setError("");
    try {
      await authorizedRequest<SubtitleTemplate>(`/subtitle-templates/${templateId}/clone`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      await loadTemplates();
    } catch (err) {
      setError(err instanceof Error ? err.message : "템플릿 복제에 실패했습니다.");
    }
  }

  async function handleDelete(templateId: number) {
    setError("");
    try {
      await authorizedRequest(`/subtitle-templates/${templateId}`, { method: "DELETE" });
      if (editingId === templateId) cancelForm();
      await loadTemplates();
    } catch (err) {
      setError(err instanceof Error ? err.message : "템플릿 삭제에 실패했습니다.");
    }
  }

  const showForm = creating || editingId != null;

  return (
    <div className="media-tab-body">
      <p className="muted">자막 폰트·색·배경 프리셋을 저장하고 이 프로젝트에 적용합니다.</p>
      {error ? <p className="form-message">{error}</p> : null}
      {loading ? <p className="muted">템플릿 불러오는 중…</p> : null}

      <ul className="template-list">
        {templates.map((template) => {
          const active = appliedTemplateId === template.id;
          return (
            <li key={template.id} className={`template-card ${active ? "active" : ""}`}>
              <div className="template-card-copy">
                <strong>{template.name}</strong>
                <span className="muted">
                  {template.is_system ? "시스템" : "내 템플릿"} · {template.font_size}px · {template.primary_color}
                  {template.border_style === 3 ? " · 배경박스" : ""}
                </span>
                <span
                  className="template-swatch"
                  style={{
                    color: template.primary_color,
                    background: template.border_style === 3 ? template.back_color : "transparent",
                    textShadow: `0 0 ${template.outline}px ${template.outline_color}`,
                    fontWeight: template.bold ? 700 : 400,
                  }}
                >
                  미리보기
                </span>
              </div>
              <div className="template-card-actions">
                <button className="small-button" type="button" disabled={applying || active} onClick={() => void onApply(template.id)}>
                  {active ? "적용됨" : "적용"}
                </button>
                {template.is_system ? (
                  <button className="ghost-small" type="button" onClick={() => void handleClone(template.id)}>
                    복제
                  </button>
                ) : (
                  <>
                    <button className="ghost-small" type="button" onClick={() => startEdit(template)}>
                      편집
                    </button>
                    <button className="ghost-small" type="button" onClick={() => void handleDelete(template.id)}>
                      삭제
                    </button>
                  </>
                )}
              </div>
            </li>
          );
        })}
      </ul>

      {!showForm ? (
        <button className="small-button" type="button" onClick={startCreate}>
          + 새 템플릿
        </button>
      ) : (
        <form
          className="template-form"
          onSubmit={(event) => {
            event.preventDefault();
            void handleSave();
          }}
        >
          <h3 className="stock-search-title">{creating ? "새 템플릿" : "템플릿 편집"}</h3>
          <label>
            이름
            <input value={draft.name} onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))} required />
          </label>
          <label>
            글자 크기
            <input
              type="number"
              min={24}
              max={120}
              value={draft.font_size}
              onChange={(event) => setDraft((current) => ({ ...current, font_size: Number(event.target.value) }))}
            />
          </label>
          <label>
            글자 색
            <input type="color" value={draft.primary_color} onChange={(event) => setDraft((current) => ({ ...current, primary_color: event.target.value }))} />
          </label>
          <label>
            외곽선 색
            <input type="color" value={draft.outline_color} onChange={(event) => setDraft((current) => ({ ...current, outline_color: event.target.value }))} />
          </label>
          <label>
            배경 색
            <input type="color" value={draft.back_color} onChange={(event) => setDraft((current) => ({ ...current, back_color: event.target.value }))} />
          </label>
          <label className="duration-auto">
            <input type="checkbox" checked={draft.bold} onChange={(event) => setDraft((current) => ({ ...current, bold: event.target.checked }))} />
            굵게
          </label>
          <label className="duration-auto">
            <input
              type="checkbox"
              checked={draft.border_style === 3}
              onChange={(event) => setDraft((current) => ({ ...current, border_style: event.target.checked ? 3 : 1 }))}
            />
            배경 박스
          </label>
          <label>
            외곽선 두께
            <input
              type="number"
              min={0}
              max={12}
              step={0.5}
              value={draft.outline}
              onChange={(event) => setDraft((current) => ({ ...current, outline: Number(event.target.value) }))}
            />
          </label>
          <label>
            그림자
            <input
              type="number"
              min={0}
              max={12}
              step={0.5}
              value={draft.shadow}
              onChange={(event) => setDraft((current) => ({ ...current, shadow: Number(event.target.value) }))}
            />
          </label>
          <label>
            하단 여백
            <input
              type="number"
              min={0}
              max={600}
              value={draft.margin_v}
              onChange={(event) => setDraft((current) => ({ ...current, margin_v: Number(event.target.value) }))}
            />
          </label>
          <div className="template-card-actions">
            <button className="small-button" type="submit" disabled={saving}>
              {saving ? "저장 중" : "저장"}
            </button>
            <button className="ghost-button" type="button" onClick={cancelForm}>
              취소
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
