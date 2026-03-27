export type FileMeta = {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
};

export type PracticeConfig = {
  key: string;
  pipeline_area_key: string;
  pipeline_area_name: string;
  name: string;
  what_it_evaluates: string;
  enterprise_examples: string[];
  user_prompt: string;
  evidence_encouragement: string;
};

export type PracticeState = {
  practice_key: string;
  narrative: string;
  files: FileMeta[];
  follow_up_transcript: { kind: string; round?: number; questions?: string[]; text?: string }[];
  follow_up_rounds_used: number;
  user_confirmed: boolean;
  progress_detail?: string;
  allow_confirm?: boolean;
  review_status?: string | null;
  sufficiency_plain?: string | null;
  follow_up_questions: string[];
  confirmation_message?: string | null;
  cap_warning?: string | null;
  last_rationale_short?: string | null;
};

export type SessionInfo = {
  id: number;
  name: string;
  email: string;
  team_name: string;
  ai_review_consent: boolean;
  assessment_version: string;
  current_practice_index: number;
  created_at: string;
};

export type SessionFull = {
  session: SessionInfo;
  config: {
    assessment_version: string;
    defaults: Record<string, unknown>;
    practices: PracticeConfig[];
    show_evaluation_feedback?: boolean;
  };
  practices_state: Record<string, PracticeState>;
  ordered_practice_keys: string[];
  completed_count: number;
  total_practices: number;
  all_complete: boolean;
};

export type ReviewResult = {
  ok: boolean;
  error?: string | null;
  is_sufficient?: boolean | null;
  allow_confirm?: boolean;
  sufficiency_plain?: string | null;
  follow_up_questions: string[];
  confirmation_message?: string | null;
  cap_warning?: string | null;
  follow_up_rounds_used: number;
  follow_up_cap: number;
  rationale_short?: string | null;
};
