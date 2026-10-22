import { createTheme, Shadows } from "@mui/material/styles";

/**
 * Design tokens for the referral platform.
 *
 * Every text and boundary colour below was checked against WCAG 2.2 AA
 * (4.5:1 for text, 3:1 for input borders and focus rings) on the surfaces it
 * is used on. Status is always carried by a text label as well as colour.
 */
export const tokens = {
  ink: "#16262B",
  muted: "#44565C",
  page: "#EBF0EE",
  surface: "#F7F9F8",
  sunken: "#E1E8E5",
  line: "#C3CFCB",
  field: "#6B7F78",
  brand: "#0A5160",
  brandDark: "#073B47",
  nav: "#0E3640",
  navText: "#E4EEEC",
  navMuted: "#B9CCC8",
  navActive: "#1C4B57",
  focusOnDark: "#F2C14E",
  ok: { text: "#1B6A3A", bg: "#E0EEE4" },
  warn: { text: "#7A4300", bg: "#F4E6CB" },
  bad: { text: "#A3231F", bg: "#F3DDDB" },
  info: { text: "#1D5A8C", bg: "#DCE8F1" },
  neutral: { text: "#44565C", bg: "#E1E8E5" },
} as const;

const fontStack = '"Segoe UI", "Helvetica Neue", Arial, "Noto Sans", system-ui, sans-serif';

const noShadows = Array(25).fill("none") as Shadows;

export const theme = createTheme({
  palette: {
    mode: "light",
    primary: { main: tokens.brand, dark: tokens.brandDark, contrastText: tokens.surface },
    secondary: { main: tokens.muted },
    success: { main: tokens.ok.text, contrastText: tokens.surface },
    warning: { main: tokens.warn.text, contrastText: tokens.surface },
    error: { main: tokens.bad.text, contrastText: tokens.surface },
    info: { main: tokens.info.text, contrastText: tokens.surface },
    text: { primary: tokens.ink, secondary: tokens.muted },
    background: { default: tokens.page, paper: tokens.surface },
    divider: tokens.line,
  },
  shape: { borderRadius: 4 },
  shadows: noShadows,
  // No animated hover or focus transitions. State changes are instant.
  transitions: { create: () => "none" },
  typography: {
    fontFamily: fontStack,
    fontSize: 14,
    body1: { fontSize: "0.9375rem", lineHeight: 1.55 },
    body2: { fontSize: "0.875rem", lineHeight: 1.5 },
    h4: { fontSize: "1.75rem", fontWeight: 600, lineHeight: 1.25 },
    h5: { fontSize: "1.5rem", fontWeight: 600, lineHeight: 1.3 },
    h6: { fontSize: "1.0625rem", fontWeight: 600, lineHeight: 1.35 },
    subtitle1: { fontSize: "0.9375rem", fontWeight: 600, lineHeight: 1.4 },
    subtitle2: { fontSize: "0.875rem", fontWeight: 600, lineHeight: 1.4 },
    caption: { fontSize: "0.8125rem", lineHeight: 1.45 },
    overline: { fontSize: "0.75rem", fontWeight: 600, letterSpacing: "0.06em", lineHeight: 1.4 },
    button: { textTransform: "none", fontWeight: 600, letterSpacing: 0 },
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: { backgroundColor: tokens.page, color: tokens.ink },
        "table, .tabular": { fontVariantNumeric: "tabular-nums" },
        "@media (prefers-reduced-motion: reduce)": {
          "*, *::before, *::after": { animationDuration: "0.01ms !important", animationIterationCount: "1 !important" },
        },
      },
    },
    MuiTypography: {
      defaultProps: {
        // Real heading levels: the page title is the only h1, section titles are h2/h3.
        variantMapping: {
          h1: "h1",
          h2: "h2",
          h3: "h3",
          h4: "h2",
          h5: "h2",
          h6: "h2",
          subtitle1: "h3",
          subtitle2: "div",
          body1: "p",
          body2: "p",
          inherit: "p",
        },
      },
    },
    MuiButtonBase: { defaultProps: { disableRipple: true } },
    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: {
        root: { minHeight: 40, borderRadius: 4, paddingInline: 16 },
        sizeSmall: { minHeight: 32, paddingInline: 12 },
        containedPrimary: { "&:hover": { backgroundColor: tokens.brandDark } },
        outlined: { borderColor: tokens.field, "&:hover": { backgroundColor: tokens.sunken, borderColor: tokens.ink } },
        text: { "&:hover": { backgroundColor: tokens.sunken } },
      },
    },
    MuiIconButton: { styleOverrides: { root: { borderRadius: 4, "&:hover": { backgroundColor: tokens.sunken } } } },
    MuiPaper: {
      defaultProps: { variant: "outlined" },
      styleOverrides: {
        root: { backgroundImage: "none", borderColor: tokens.line, backgroundColor: tokens.surface, overflowX: "auto" },
      },
    },
    MuiTextField: { defaultProps: { size: "small" } },
    MuiFormControl: { defaultProps: { size: "small" } },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          backgroundColor: tokens.surface,
          "& .MuiOutlinedInput-notchedOutline": { borderColor: tokens.field },
          "&:hover .MuiOutlinedInput-notchedOutline": { borderColor: tokens.ink },
          "&.Mui-focused .MuiOutlinedInput-notchedOutline": { borderColor: tokens.brand, borderWidth: 2 },
          "&.Mui-disabled": { backgroundColor: tokens.sunken },
        },
      },
    },
    MuiInputLabel: { styleOverrides: { root: { color: tokens.muted, "&.Mui-focused": { color: tokens.brand } } } },
    MuiFormHelperText: { styleOverrides: { root: { marginInline: 2 } } },
    MuiLink: { defaultProps: { underline: "always" }, styleOverrides: { root: { color: tokens.brand, textUnderlineOffset: "2px", fontWeight: 500 } } },
    MuiAlert: {
      defaultProps: { variant: "outlined" },
      styleOverrides: {
        root: ({ ownerState }) => {
          const tone = { error: tokens.bad, warning: tokens.warn, success: tokens.ok, info: tokens.info }[ownerState.severity ?? "info"];
          return { backgroundColor: tone.bg, color: tokens.ink, borderColor: tone.text, borderRadius: 4, "& .MuiAlert-icon": { color: tone.text } };
        },
        message: { overflow: "visible" },
      },
    },
    MuiAlertTitle: { styleOverrides: { root: { fontWeight: 600 } } },
    MuiChip: { styleOverrides: { root: { borderRadius: 4, fontWeight: 600, height: 26 } } },
    MuiTabs: { styleOverrides: { indicator: { height: 3, backgroundColor: tokens.brand } } },
    MuiTab: { styleOverrides: { root: { minHeight: 48, "&.Mui-selected": { color: tokens.brand } } } },
    MuiTableCell: {
      styleOverrides: {
        root: { borderBottomColor: tokens.line, paddingBlock: 10 },
        head: { backgroundColor: tokens.sunken, color: tokens.ink, fontWeight: 600, whiteSpace: "nowrap" },
      },
    },
    MuiTableRow: { styleOverrides: { root: { "&.MuiTableRow-hover:hover": { backgroundColor: tokens.sunken } } } },
    MuiDialog: { styleOverrides: { paper: { border: `1px solid ${tokens.field}` } } },
    MuiBackdrop: { styleOverrides: { root: { backgroundColor: "rgba(22, 38, 43, 0.55)" } } },
    MuiListItemButton: {
      styleOverrides: { root: { borderRadius: 4, "&.Mui-selected": { backgroundColor: tokens.sunken, fontWeight: 600 }, "&:hover": { backgroundColor: tokens.sunken } } },
    },
    MuiSkeleton: { defaultProps: { animation: "pulse" }, styleOverrides: { root: { backgroundColor: tokens.sunken } } },
  },
});
