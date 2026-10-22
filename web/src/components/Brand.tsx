import { Link as RouterLink } from "react-router-dom";
import { Box, Typography } from "@mui/material";

/** Small original mark: a cross with a handover notch. Decorative, so hidden from assistive technology. */
export function BrandMark({ size = 32 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden focusable="false">
      <rect width="32" height="32" rx="4" fill="#0A5160" stroke="#B9CCC8" strokeWidth="1" />
      <path d="M13 6h6v7h7v6h-7v7h-6v-7H6v-6h7z" fill="#F7F9F8" />
    </svg>
  );
}

/** The product logo. It always links home. */
export function Brand({ onDark = false, to = "/" }: { onDark?: boolean; to?: string }) {
  return (
    <Box
      component={RouterLink}
      to={to}
      aria-label="Referral Platform, go to start page"
      sx={{ display: "inline-flex", alignItems: "center", gap: 1.25, textDecoration: "none", color: onDark ? "#E4EEEC" : "text.primary", borderRadius: 1 }}
    >
      <BrandMark />
      <Box>
        <Typography component="span" sx={{ display: "block", fontWeight: 700, fontSize: "1rem", lineHeight: 1.2, color: "inherit" }}>
          Referral Platform
        </Typography>
        <Typography component="span" sx={{ display: "block", fontSize: "0.75rem", lineHeight: 1.3, color: onDark ? "#B9CCC8" : "text.secondary" }}>
          Preparation and follow-through
        </Typography>
      </Box>
    </Box>
  );
}
