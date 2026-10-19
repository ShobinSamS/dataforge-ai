export type FieldType =
  | "text"
  | "name"
  | "address"
  | "date"
  | "email"
  | "phone"
  | "identifier"
  | "signature"
  | "seal"
  | "qr"
  | "barcode"
  | "portrait";
export const fieldTypes: FieldType[] = [
  "text",
  "name",
  "address",
  "date",
  "email",
  "phone",
  "identifier",
  "signature",
  "seal",
  "qr",
  "barcode",
  "portrait",
];
export interface RuleOptions {
  date_format:
    "yyyy-mm-dd" | "dd/mm/yyyy" | "mm/dd/yyyy" | "dd-mm-yyyy" | "yyyy/mm/dd";
  date_start: string;
  date_end: string;
  identifier_pattern: string;
  literal_text: string | null;
  portrait_source: "illustration" | "asset_pool";
  portrait_asset_ids: string[];
  character_length?: number | null;
  character_set?: "alnum" | "digits" | "upper" | "lower";
  font_id?: string;
  font_size?: number | null;
  text_color?: string;
  color_mode?: "auto" | "manual";
  font_weight?: "auto" | "normal" | "bold";
  background_mode?: "auto" | "solid";
  background_color?: string;
  cleanup_mode?: "full_region" | "ink_only";
  writing_style?: "printed" | "cursive";
  code_background?: "transparent" | "white";
  signature_style?:
    | "mixed"
    | "name"
    | "first_name"
    | "single_letter"
    | "two_letters"
    | "initials"
    | "letter_wave"
    | "monogram"
    | "flourish"
    | "tall_initial"
    | "compact"
    | "angular"
    | "looped"
    | "sweeping"
    | "gestural"
    | "stacked"
    | "initial_bridge"
    | "terminal_loop"
    | "crossed"
    | "minimal"
    | "surname"
    | "split"
    | "enclosed"
    | "interwoven";
  ink_opacity_mode?: "random" | "fixed";
  ink_opacity?: number;
  ink_opacity_min?: number;
  ink_opacity_max?: number;
  ink_finish?: "clean" | "natural" | "worn";
  ink_irregularity?: number;
  seal_style?:
    | "random"
    | "ring"
    | "round"
    | "double_ring"
    | "oval"
    | "badge"
    | "square"
    | "rectangle"
    | "professional"
    | "form"
    | "dated"
    | "text"
    | "attestation"
    | "corporate"
    | "form_block"
    | "nameplate";
  seal_color?:
    | "random"
    | "red"
    | "blue"
    | "green"
    | "purple"
    | "black"
    | "brown"
    | "mixed";
  seal_text_mode?: "random" | "static" | "custom";
  seal_allow_repeated_words?: boolean;
  seal_top_format?: string;
  seal_bottom_format?: string;
  seal_body_format?: string;
  seal_bottom_text?: string;
  seal_border?:
    | "random"
    | "solid"
    | "double"
    | "dotted"
    | "dashed"
    | "serrated"
    | "rosettes";
  seal_symbol?: "random" | "none" | "star" | "diamond" | "rosette" | "monogram";
  seal_text?: string;
  seal_subtext?: string;
  seal_wear?: number;
  seal_inner_top_text?: string;
  seal_inner_bottom_text?: string;
  seal_center_motif?: "none" | "shield" | "rosette" | "rays";
  seal_field_writing?: "printed" | "cursive";
  seal_embedded_signature?: boolean;
  seal_signer_name?: string;
}
export interface Region {
  id: string;
  label: string;
  kind: FieldType;
  box: [number, number, number, number];
  text: string;
  confidence: number;
  sensitive: boolean;
  replace: boolean;
  confirmed: boolean;
  page: number;
  rule: string;
  action?: "replace" | "erase" | "keep" | null;
  rule_options?: RuleOptions;
  rule_resolved_hash?: string;
  source_font?: string;
  source_font_size?: number | null;
  origin?: "manual" | "ocr" | "pii";
  pii_category?: string;
  pii_value?: string;
  pii_reason?: string;
}
export interface Template {
  id: string;
  name: string;
  width: number;
  height: number;
  regions: Region[];
  warnings: string[];
  engine: string;
  revision: number;
  privacy_confirmed: boolean;
  created_at: string;
}
export interface Config {
  template_id: string;
  name: string;
  count: number;
  seed: number;
  blur_probability: number;
  rotation_probability: number;
  rotation_degrees: number;
  noise_sigma: number;
  signatures: boolean;
  signature_style_override?: "mixed" | null;
  seals: boolean;
  qr_codes: boolean;
  barcodes: boolean;
  max_retries: number;
  qr_padding?: number;
  qr_payload_length?: number;
  identifier_length?: number;
  qr_required?: boolean;
}
export interface Job {
  id: string;
  template_id: string;
  name: string;
  status: string;
  config: Config;
  total: number;
  completed: number;
  error: string;
  metrics: Record<string, number>;
  created_at: string;
}
export interface Annotation {
  seal?: {
    shape: string;
    content_mode: string;
    text: string;
    opacity?: number;
  };
  signature?: {
    style: string;
    text: string;
    engine?: string;
    opacity?: number;
  };
  region_id: string;
  class_id: number;
  class: string;
  bbox: [number, number, number, number];
  text: string;
  mask: string;
  provenance: string;
}
export interface Sample {
  id: string;
  index: number;
  annotations: Annotation[];
  validation: { passed: boolean; errors: string[]; warnings: string[] };
  sha256: string;
}
export interface Quality {
  total: number;
  accepted: number;
  rejected: number;
  classes: Record<string, number>;
  errors: Record<string, number>;
  metrics: Record<string, number>;
  not_checked: string[];
}
export interface System {
  available_ram_mb: number;
  process_rss_mb: number;
  worker_count: number;
  ocr: { configured: string; paddle_local_models: boolean; tesseract: boolean };
  capabilities: Record<string, boolean>;
}
export interface Export {
  id: string;
  job_id: string;
  format: string;
  created_at: string;
  download_url: string;
}

export type Page =
  | "Dashboard"
  | "Template library"
  | "Template editor"
  | "Generation studio"
  | "Text datasets"
  | "Dataset gallery"
  | "Annotation preview"
  | "Quality dashboard"
  | "Job monitor"
  | "Export & history"
  | "AI image studio"
  | "Agent activity"
  | "MCP tools"
  | "Settings";
