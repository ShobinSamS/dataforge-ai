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
  | "portrait"
  | "stamp"
  | "rubber_stamp"
  | "drawing";
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
  "stamp",
  "rubber_stamp",
  "drawing",
];
export interface RuleOptions {
  signature_artwork_ids?: string[];
  address_country?: string;
  address_format?: string;
  date_format:
    "yyyy-mm-dd" | "dd/mm/yyyy" | "mm/dd/yyyy" | "dd-mm-yyyy" | "yyyy/mm/dd";
  date_start: string;
  date_end: string;
  identifier_pattern: string;
  literal_text: string | null;
  portrait_source: "illustration" | "asset_pool";
  portrait_asset_ids: string[];
  portrait_background?: "preserve" | "transparent" | "solid" | "random";
  portrait_background_color?: string;
  portrait_background_palette?: string[];
  drawing_points?: [number, number][];
  drawing_width?: number;
  character_length?: number | null;
  character_set?: "alnum" | "digits" | "upper" | "lower";
  font_id?: string;
  font_size?: number | null;
  text_color?: string;
  color_mode?: "black" | "auto" | "manual" | "random" | "mixed";
  color_palette?: string[];
  font_weight?: "auto" | "normal" | "bold";
  background_mode?: "auto" | "solid";
  background_color?: string;
  cleanup_mode?: "full_region" | "ink_only";
  writing_style?: "printed" | "cursive" | "handwritten";
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
  signature_thickness?: number;
  signature_content?: "current" | "name" | "alphabet" | "mixed";
  ink_opacity_mode?: "random" | "fixed";
  ink_opacity?: number;
  ink_opacity_min?: number;
  ink_opacity_max?: number;
  ink_finish?: "clean" | "natural" | "worn";
  ink_irregularity?: number;
  seal_artwork_id?: string | null;
  seal_artwork_ids?: string[];
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
  stamp_style?:
    | "random"
    | "portrait"
    | "architecture"
    | "botanical"
    | "commemorative"
    | "revenue";
  stamp_ink_mode?: "default" | "custom";
  stamp_color?: string;
  stamp_palette?:
    | "black"
    | "custom"
    | "random"
    | "sepia"
    | "red"
    | "blue"
    | "green"
    | "purple"
    | "monochrome"
    | "multicolor";
  stamp_issuer?: string;
  stamp_caption?: string;
  stamp_denomination?: string;
  stamp_perforated?: boolean;
  stamp_age?: number;
  stamp_cancellation?: "random" | "none" | "postmark" | "waves" | "pen";
  rubber_stamp_style?:
    "random" | "boxed" | "text" | "round" | "dated" | "postmark" | "waves";
  rubber_stamp_mode?: "random" | "static" | "custom";
  rubber_stamp_text?: string;
  rubber_stamp_format?: string;
  rubber_stamp_color?:
    "random" | "red" | "blue" | "green" | "purple" | "black" | "brown";
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
  origin?: "manual" | "ocr" | "pii" | "visual";
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
  canvas?: {
    paper: string;
    dpi: number;
    background: "white" | "transparent" | "color";
    background_color: string;
  } | null;
}
export interface Config {
  capture_profile?:
    "none" | "phone" | "scanner" | "photocopy" | "cropped_scan" | "mixed";
  capture_strength?: number;
  field_links?: {
    target: string;
    sources: string[];
    rule: "copy" | "age" | "after_date" | "sum";
    separator: string;
    days: number;
    as_of: string;
  }[];
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
  signature_content_override?: "current" | "name" | "alphabet" | "mixed" | null;
  seals: boolean;
  stamps?: boolean;
  rubber_stamps?: boolean;
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
  stamp?: {
    style: string;
    text: string;
    cancellation: string;
    palette: string;
  };
  rubber_stamp?: { style: string; text: string; opacity?: number };
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
  | "Document lab"
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
