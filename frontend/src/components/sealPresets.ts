import type { RuleOptions } from "../types";

// The same complete-seal recipes are available in templates and image studio.
export const sealPresets: Record<
  string,
  { label: string; options: Partial<RuleOptions> }
> = {
  corporate: {
    label: "Company seal · circle with a crest",
    options: {
      seal_style: "corporate",
      seal_border: "rosettes",
      seal_symbol: "star",
      seal_center_motif: "shield",
      seal_inner_top_text: "",
      seal_inner_bottom_text: "",
      seal_top_format: "{organization}",
      seal_body_format: "REGISTRATION {reference}",
      seal_bottom_format: "{city} · {state}",
    },
  },
  dated: {
    label: "Company seal · circle with a date",
    options: {
      seal_style: "corporate",
      seal_border: "double",
      seal_symbol: "none",
      seal_center_motif: "none",
      seal_top_format: "{organization}",
      seal_body_format: "{date}",
      seal_bottom_format: "{city}",
    },
  },
  quality: {
    label: "Quality seal · two rings and an emblem",
    options: {
      seal_style: "corporate",
      seal_border: "double",
      seal_symbol: "star",
      seal_center_motif: "rays",
      seal_inner_top_text: "OFFICIAL SEAL",
      seal_inner_bottom_text: "EST {year}",
      seal_top_format: "{organization}",
      seal_body_format: "REF {reference}",
      seal_bottom_format: "{city}",
    },
  },
  shipping: {
    label: "Company form · recipient, product and batch",
    options: {
      seal_style: "form_block",
      seal_border: "double",
      seal_symbol: "none",
      seal_top_format: "{organization}",
      seal_body_format: "REG NO: {reference}\nTO:\nPRODUCT:\nBATCH:",
      seal_bottom_format: "{city} · {state}",
    },
  },
  granted: {
    label: "Company form · date and status",
    options: {
      seal_style: "form_block",
      seal_border: "double",
      seal_symbol: "none",
      seal_top_format: "{organization}",
      seal_body_format: "REG NO: {reference}\nDATE:\nGRANTED",
      seal_bottom_format: "{city} · {state}",
    },
  },
  nameplate: {
    label: "Company nameplate · name and registration",
    options: {
      seal_style: "nameplate",
      seal_border: "double",
      seal_symbol: "none",
      seal_top_format: "{organization}",
      seal_body_format: "REG NO: {reference}",
      seal_bottom_format: "",
    },
  },
  professional: {
    label: "Professional nameplate · name and role",
    options: {
      seal_style: "professional",
      seal_border: "solid",
      seal_symbol: "none",
      seal_top_format: "{name}",
      seal_body_format: "{title}\n{organization}\nREG {reference}",
      seal_bottom_format: "{city}",
    },
  },
  attestation: {
    label: "Attestation · heading and office details",
    options: {
      seal_style: "attestation",
      seal_border: "double",
      seal_symbol: "none",
      seal_top_format: "ATTESTED",
      seal_body_format:
        "{name}\n{department}\n{organization}\n{city}\nDated {date}\nREF {reference}",
      seal_bottom_format: "",
    },
  },
};

export function sealPreset(key: string): Partial<RuleOptions> {
  return {
    seal_text_mode: "custom",
    literal_text: null,
    seal_inner_top_text: "",
    seal_inner_bottom_text: "",
    seal_center_motif: "none",
    seal_embedded_signature: false,
    seal_artwork_id: null,
    seal_artwork_ids: [],
    ...sealPresets[key].options,
  };
}
