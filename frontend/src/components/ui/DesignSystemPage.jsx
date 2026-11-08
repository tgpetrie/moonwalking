import {
  UiButton,
  UiCard,
  UiCheckbox,
  UiChip,
  UiCluster,
  UiField,
  UiStack,
} from "./DesignSystem.jsx";

const colorTokens = [
  ["surface/void", "--surface-void"],
  ["surface/panel", "--surface-panel"],
  ["surface/raised", "--surface-raised"],
  ["accent/primary", "--accent-primary"],
  ["signal/positive", "--signal-positive"],
  ["signal/negative", "--signal-negative"],
  ["danger", "--danger"],
];

const spacingTokens = [1, 2, 3, 4, 5, 6, 7, 8];

export default function DesignSystemPage() {
  return (
    <div className="ui-gallery">
      <header className="ui-gallery__intro">
        <p className="mw-eyebrow">Moonwalking design system</p>
        <h1>Foundations and components</h1>
        <p>
          This page is the executable reference for code review, responsive QA,
          and Figma library reconciliation.
        </p>
      </header>

      <UiStack space="8">
        <section className="ui-gallery__section" aria-labelledby="ds-foundations">
          <div className="ui-gallery__section-heading">
            <span>01</span>
            <div>
              <h2 id="ds-foundations">Foundations</h2>
              <p>Semantic color, spacing, radius, and typography tokens.</p>
            </div>
          </div>

          <div className="ui-gallery__grid ui-gallery__grid--tokens">
            <UiCard>
              <h3>Color</h3>
              <div className="ui-gallery__swatches">
                {colorTokens.map(([name, variable]) => (
                  <div key={variable} className="ui-gallery__swatch-row">
                    <span className="ui-gallery__swatch" style={{ background: `var(${variable})` }} />
                    <div>
                      <strong>{name}</strong>
                      <code>{variable}</code>
                    </div>
                  </div>
                ))}
              </div>
            </UiCard>

            <UiCard>
              <h3>Spacing</h3>
              <div className="ui-gallery__spacing-list">
                {spacingTokens.map((token) => (
                  <div key={token} className="ui-gallery__spacing-row">
                    <code>spacing/{token}</code>
                    <span style={{ width: `var(--space-${token})` }} />
                    <small>{token * 4}px</small>
                  </div>
                ))}
              </div>
            </UiCard>

            <UiCard>
              <h3>Typography</h3>
              <div className="ui-gallery__type-list">
                <p className="ui-gallery__type-display">Dashboard</p>
                <p className="ui-gallery__type-title">Section title</p>
                <p className="ui-gallery__type-body">Readable interface copy for repeated workflows.</p>
                <p className="ui-gallery__type-meta">SECONDARY LABEL</p>
                <p className="ui-gallery__type-number">$42,814.09</p>
              </div>
            </UiCard>
          </div>
        </section>

        <section className="ui-gallery__section" aria-labelledby="ds-buttons">
          <div className="ui-gallery__section-heading">
            <span>02</span>
            <div>
              <h2 id="ds-buttons">Button</h2>
              <p>Rectangular command controls with four variants and three sizes.</p>
            </div>
          </div>
          <UiCard>
            <UiStack space="5">
              <UiCluster>
                <UiButton variant="primary">Primary</UiButton>
                <UiButton variant="secondary">Secondary</UiButton>
                <UiButton variant="ghost">Ghost</UiButton>
                <UiButton variant="danger">Delete</UiButton>
              </UiCluster>
              <UiCluster>
                <UiButton size="sm">Small</UiButton>
                <UiButton size="md">Medium</UiButton>
                <UiButton size="lg">Large</UiButton>
                <UiButton disabled>Disabled</UiButton>
                <UiButton loading loadingLabel="Saving...">Save</UiButton>
              </UiCluster>
            </UiStack>
          </UiCard>
        </section>

        <section className="ui-gallery__section" aria-labelledby="ds-forms">
          <div className="ui-gallery__section-heading">
            <span>03</span>
            <div>
              <h2 id="ds-forms">Field and selection</h2>
              <p>Labels remain visible; hints and errors are programmatically associated.</p>
            </div>
          </div>
          <UiCard>
            <div className="ui-gallery__form-grid">
              <UiField label="Email" type="email" placeholder="name@example.com" hint="Used for account access." />
              <UiField label="Asset symbol" placeholder="BTC" error="Choose a supported symbol." />
              <UiField label="Disabled field" value="Unavailable" disabled readOnly />
              <UiField label="Notes" multiline placeholder="Add decision context" />
            </div>
            <UiCluster className="ui-gallery__selection-row">
              <UiCheckbox label="Remember this device" defaultChecked />
              <UiCheckbox label="Disabled option" disabled />
            </UiCluster>
          </UiCard>
        </section>

        <section className="ui-gallery__section" aria-labelledby="ds-cards">
          <div className="ui-gallery__section-heading">
            <span>04</span>
            <div>
              <h2 id="ds-cards">Card and chip</h2>
              <p>Cards frame content; pills are reserved for compact semantic state.</p>
            </div>
          </div>
          <div className="ui-gallery__grid">
            <UiCard tone="subtle">
              <UiStack space="3">
                <UiChip>Neutral</UiChip>
                <h3>Subtle card</h3>
                <p>Use for low-emphasis supporting information.</p>
              </UiStack>
            </UiCard>
            <UiCard>
              <UiStack space="3">
                <UiChip tone="accent">Selected</UiChip>
                <h3>Default card</h3>
                <p>The standard panel for forms and grouped data.</p>
              </UiStack>
            </UiCard>
            <UiCard tone="raised">
              <UiStack space="3">
                <UiCluster space="2">
                  <UiChip tone="positive">Positive</UiChip>
                  <UiChip tone="negative">Negative</UiChip>
                  <UiChip tone="danger">Danger</UiChip>
                </UiCluster>
                <h3>Raised card</h3>
                <p>Use sparingly for the active or highest-priority surface.</p>
              </UiStack>
            </UiCard>
          </div>
        </section>
      </UiStack>
    </div>
  );
}
