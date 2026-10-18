export type TextTask =
  | "classification"
  | "ner"
  | "qa"
  | "instruction"
  | "conversation"
  | "augmentation";
export type Language = "en" | "es" | "fr" | "de" | "hi";
export interface SourceText {
  text: string;
  language: Language;
  label?: string | null;
}
export interface TextConfig {
  name: string;
  task: TextTask;
  backend: "procedural" | "ollama";
  count: number;
  seed: number;
  languages: Language[];
  labels: string[];
  topic: string;
  instructions: string;
  batch_size: number;
  max_retries: number;
  source_texts: SourceText[];
  augmentations: ("whitespace" | "punctuation" | "typos")[];
  class_templates: Record<string, Partial<Record<Language, string>>>;
  qa_answer_bank: Partial<Record<Language, string[]>>;
  qa_answer_hint: string;
}
export interface TextJob {
  id: string;
  name: string;
  status: string;
  config: TextConfig;
  total: number;
  completed: number;
  error: string;
  created_at: string;
  metrics: {
    elapsed_seconds?: number;
    peak_process_rss_mb?: number;
    rss_scope?: string;
    model?: string;
  };
}
export interface TextRecord {
  id: string;
  index: number;
  task: TextTask;
  language: Language;
  text?: string;
  label?: string;
  entities?: { label: string; text: string; start: number; end: number }[];
  context?: string;
  question?: string;
  answer?: string;
  answer_start?: number;
  instruction?: string;
  response?: string;
  messages?: { role: string; content: string }[];
  provenance: { engine: string; labels?: string };
  validation: { passed: boolean; errors: string[]; warnings: string[] };
}
export interface TextQuality {
  requested: number;
  total: number;
  accepted: number;
  rejected: number;
  labels: Record<string, number>;
  languages: Record<string, number>;
  errors: Record<string, number>;
  warnings: string[];
}
export interface TextCapabilities {
  max_samples: number;
  languages: Record<Language, string>;
  llm: {
    reachable: boolean;
    installed: boolean;
    model: string;
    error?: string;
  };
  limitations: string[];
}
export interface TextExport {
  id: string;
  job_id: string;
  format: string;
  created_at: string;
  download_url: string;
}
