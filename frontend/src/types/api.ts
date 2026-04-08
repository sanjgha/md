// AUTO-GENERATED from /openapi.json — do not edit manually.
// Regenerate with: pnpm generate:types

export interface UserOut {
  id: number;
  username: string;
}

export interface SettingsOut {
  theme: string;
  timezone: string;
}

export interface SettingsPatch {
  theme?: "light" | "dark";
  timezone?: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}
