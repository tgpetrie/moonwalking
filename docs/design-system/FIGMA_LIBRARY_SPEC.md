# Moonwalking Figma Library Specification

Status: v1 code contract, 2026-10-18

This is the handoff contract for creating or reconciling the Moonwalking Figma
library. The machine-readable source is
`frontend/src/design-system/tokens.json`; generated CSS is not the authoring
source. Use the `/design-system` route as the visual specimen.

The source uses the structured values defined by the
[DTCG 2025.10 format](https://www.designtokens.org/tr/2025.10/format/): sRGB
color objects, dimension and duration objects, typed aliases, and composite
shadows. `npm run tokens:build` generates `tokens.figma.json` alongside CSS.
The Figma file is an adapter manifest for the Plugin API, not a native import
file. It contains resolved values, aliases, collection/mode names, scopes, and
WEB Code Syntax. No Figma file or published library is created by this build.

## Library structure

Create these Figma pages in order: `00 Cover`, `01 Foundations`, `02 Button`,
`03 Field`, `04 Checkbox`, `05 Chip`, `06 Card`, `07 Layout`, and `08 Patterns`.

## Variable collections

| Collection | Modes | Source groups | Figma scopes |
|---|---|---|---|
| `Primitives` | `Value` | `color.primitive` | Hidden primitives use no public scope |
| `Semantic` | `Midnight` | `color.semantic` | The scopes declared in token metadata |
| `Spacing` | `Value` | `spacing`, `density`, `layout` | `GAP`; layout values are documented dimensions |
| `Typography` | `Value` | `typography` | Font family, size, and tracking |
| `Shape` | `Value` | `radius` | `CORNER_RADIUS` |
| `Motion` | `Value` | `motion` | Prototype timing where supported |
| `Layout` | `Value` | `layout`, `control`, `zIndex` | Layout and control geometry |
| `Effects` | `Value` | `shadow` | Effect styles rather than Variables |
| `Breakpoints` | `Value` | `breakpoint` | Reference dimensions |

Semantic colors must alias primitive variables rather than repeat raw values.
Every variable with `com.moonwalking.cssVariable` receives WEB Code Syntax in
the form `var(--token-name)`. The JSON extension
`com.moonwalking.figmaScope` lists the allowed scopes. Breakpoints are
documentation values because Figma Variables do not control responsive rules.

## Component inventory

### Button

Figma component set: `Button`

| Property | Values | Code prop |
|---|---|---|
| `Style` | `Primary`, `Secondary`, `Ghost`, `Danger` | `variant` |
| `Size` | `Small`, `Medium`, `Large` | `size` |
| `State` | `Default`, `Hover`, `Focus`, `Disabled`, `Loading` | native state / `loading` |
| `Width` | `Hug`, `Fill` | `block` |
| `Label` | Text property | `children` |

Corner radius binds to `radius/control`. Loading preserves width, exposes busy
state in code, and blocks activation. Do not create pill buttons.
Keep the 12 default Style x Size variants together and demonstrate interaction
states through a separate state wrapper. Avoid a 60-variant Cartesian product.

### Field

Figma component set: `Field`

| Property | Values | Code prop |
|---|---|---|
| `Type` | `Input`, `Textarea` | `multiline` |
| `State` | `Default`, `Hover`, `Focus`, `Error`, `Disabled` | native state / `error` |
| `Hint` | `Hidden`, `Visible` | `hint` |
| `Label` | Text property | `label` |
| `Value` | Text property | native value / placeholder |

Label, hint, and error rows remain in Auto Layout. Error binds to
`color/semantic/danger`; focus binds to `color/semantic/focusRing`.

### Checkbox

Figma component set: `Checkbox`. Properties are `Checked=False|True`,
`State=Default|Hover|Focus|Disabled`, and a text property named `Label`.
The hit target is at least 44px high even though the visible control is 16px.

### Chip

Figma component set: `Chip`. Properties are
`Tone=Neutral|Accent|Positive|Negative|Danger` and `Active=False|True`.
Chips are the only v1 family that uses `radius/full`; they represent compact
state, never a primary command.

### Card

Figma component set: `Card`

| Property | Values | Code prop |
|---|---|---|
| `Tone` | `Default`, `Subtle`, `Raised` | `tone` |
| `Padding` | `None`, `Small`, `Medium`, `Large` | `padding` |

Cards bind to `radius/surface`, provide one content slot, and must not be nested
solely for decoration.

### Layout primitives

`Stack` is vertical Auto Layout and `Cluster` is horizontal wrapping Auto
Layout. Both expose `Space=1..8`, mapped directly to `spacing/1..8`.

## Responsive contract

| Breakpoint | Figma frame | Required behavior |
|---|---|---|
| `< 480px` | 375px phone | One-column forms and cards; compact two-row public navigation |
| `480-639px` | 600px phone/tablet | One-column content with comfortable gutters |
| `640-900px` | 768px tablet | Two-column specimens where content permits; member sidebar above content |
| `901-1119px` | 1024px desktop | Member sidebar returns; public header stays horizontal |
| `>= 1120px` | 1440px desktop | Full member sidebar and multi-column layouts |

No component may create page-level horizontal overflow. Data tables own their
horizontal scroll region at narrow widths.

## Accessibility contract

- Text and interactive contrast target WCAG 2.1 AA.
- Every interactive component includes visible focus treatment.
- Buttons retain native button semantics unless rendered as links.
- Field labels stay visible and are programmatically linked to controls.
- Hint and error text use `aria-describedby`; errors set `aria-invalid`.
- Loading buttons expose `aria-busy` and cannot be activated.
- Motion is removed under `prefers-reduced-motion`.

## Code mapping

| Figma component | React export | CSS root class |
|---|---|---|
| `Button` | `UiButton` | `.ui-button` |
| `Card` | `UiCard` | `.ui-card` |
| `Field` | `UiField` | `.ui-field` |
| `Checkbox` | `UiCheckbox` | `.ui-checkbox` |
| `Chip` | `UiChip` | `.ui-chip` |
| `Stack` | `UiStack` | `.ui-stack` |
| `Cluster` | `UiCluster` | `.ui-cluster` |

React exports live in `frontend/src/components/ui/DesignSystem.jsx`.

Raleway is the sole interface and numeric family. Use `--font-sans` for
interface text and `--font-numeric` for numbers; both resolve to Raleway.
The generated manifest converts rem to pixels at a 16px root. CSS retains rem
units for browser font scaling. Typography tracking tokens carry their source
em units and require conversion to percent when applied to Figma text styles.

## Reconciliation checklist

1. Import or create variables from `tokens.json` using the declared collection,
   scope, and CSS Code Syntax metadata.
2. Verify semantic aliases point to primitives.
3. Build component sets with the exact property names above.
4. Bind fill, stroke, radius, padding, and gaps to variables.
5. Compare review frames against `/design-system` at 375, 768, and 1440px.
6. Record intentional differences in `docs/DESIGN_SYSTEM.md`; never silently
   change code or Figma to make a mismatch disappear.
