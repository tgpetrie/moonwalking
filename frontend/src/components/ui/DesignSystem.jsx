import { useId } from "react";
import PropTypes from "prop-types";

function classNames(...values) {
  return values.filter(Boolean).join(" ");
}

export function UiButton({
  as: Component = "button",
  variant = "secondary",
  size = "md",
  block = false,
  loading = false,
  loadingLabel,
  disabled = false,
  className = "",
  children,
  ...props
}) {
  const isNativeButton = Component === "button";
  const componentProps = {
    ...props,
    onClick: (event) => {
      if (disabled || loading) {
        event.preventDefault();
        return;
      }
      props.onClick?.(event);
    },
    className: classNames(
      "ui-button",
      `ui-button--${variant}`,
      `ui-button--${size}`,
      block && "ui-button--block",
      loading && "is-loading",
      className
    ),
    "aria-busy": loading || undefined,
  };

  if (isNativeButton) {
    componentProps.type = props.type || "button";
    componentProps.disabled = disabled || loading;
  } else if (disabled || loading) {
    componentProps["aria-disabled"] = "true";
    componentProps.role = props.role || "link";
    componentProps.tabIndex = -1;
    componentProps.href = undefined;
    componentProps.to = undefined;
  }

  return (
    <Component {...componentProps}>
      <span className="ui-button__label" aria-hidden={loading || undefined}>{children}</span>
      {(loadingLabel || loading) ? <span className="ui-button__loading" aria-hidden={!loading || undefined}>{loadingLabel || children}</span> : null}
    </Component>
  );
}

UiButton.propTypes = {
  as: PropTypes.elementType,
  variant: PropTypes.oneOf(["primary", "secondary", "ghost", "danger"]),
  size: PropTypes.oneOf(["sm", "md", "lg"]),
  block: PropTypes.bool,
  loading: PropTypes.bool,
  loadingLabel: PropTypes.string,
  disabled: PropTypes.bool,
  className: PropTypes.string,
  children: PropTypes.node,
  type: PropTypes.string,
  onClick: PropTypes.func,
};

export function UiCard({
  as: Component = "section",
  tone = "default",
  padding = "md",
  className = "",
  children,
  ...props
}) {
  return (
    <Component
      className={classNames(
        "ui-card",
        `ui-card--${tone}`,
        `ui-card--padding-${padding}`,
        className
      )}
      {...props}
    >
      {children}
    </Component>
  );
}

UiCard.propTypes = {
  as: PropTypes.elementType,
  tone: PropTypes.oneOf(["default", "subtle", "raised"]),
  padding: PropTypes.oneOf(["none", "sm", "md", "lg"]),
  className: PropTypes.string,
  children: PropTypes.node,
};

export function UiField({
  id,
  label,
  hint = "",
  error = "",
  multiline = false,
  className = "",
  ...inputProps
}) {
  const generatedId = useId();
  const fieldId = id || `ui-field-${generatedId.replace(/:/g, "")}`;
  const hintId = hint ? `${fieldId}-hint` : undefined;
  const errorId = error ? `${fieldId}-error` : undefined;
  const describedBy = [inputProps["aria-describedby"], hintId, errorId].filter(Boolean).join(" ") || undefined;
  const Input = multiline ? "textarea" : "input";

  return (
    <div className={classNames("ui-field", error && "is-error", className)}>
      <label className="ui-field__label" htmlFor={fieldId}>{label}</label>
      <Input
        {...inputProps}
        id={fieldId}
        className="ui-field__control"
        aria-describedby={describedBy}
        aria-invalid={error ? "true" : undefined}
      />
      {hint ? <span id={hintId} className="ui-field__hint">{hint}</span> : null}
      {error ? <span id={errorId} className="ui-field__error">{error}</span> : null}
    </div>
  );
}

UiField.propTypes = {
  id: PropTypes.string,
  label: PropTypes.node.isRequired,
  hint: PropTypes.string,
  error: PropTypes.string,
  multiline: PropTypes.bool,
  className: PropTypes.string,
};

export function UiCheckbox({ id, label, className = "", ...inputProps }) {
  const generatedId = useId();
  const checkboxId = id || `ui-check-${generatedId.replace(/:/g, "")}`;

  return (
    <label className={classNames("ui-checkbox", className)} htmlFor={checkboxId}>
      <input {...inputProps} id={checkboxId} type="checkbox" />
      <span>{label}</span>
    </label>
  );
}

UiCheckbox.propTypes = {
  id: PropTypes.string,
  label: PropTypes.node.isRequired,
  className: PropTypes.string,
};

export function UiChip({ tone = "neutral", active = false, className = "", children, ...props }) {
  return (
    <span
      className={classNames(
        "ui-chip",
        `ui-chip--${tone}`,
        active && "is-active",
        className
      )}
      {...props}
    >
      {children}
    </span>
  );
}

UiChip.propTypes = {
  tone: PropTypes.oneOf(["neutral", "accent", "positive", "negative", "danger"]),
  active: PropTypes.bool,
  className: PropTypes.string,
  children: PropTypes.node,
};

export function UiStack({ as: Component = "div", space = "4", className = "", children, ...props }) {
  return (
    <Component className={classNames("ui-stack", `ui-stack--${space}`, className)} {...props}>
      {children}
    </Component>
  );
}

UiStack.propTypes = {
  as: PropTypes.elementType,
  space: PropTypes.oneOf(["1", "2", "3", "4", "5", "6", "7", "8"]),
  className: PropTypes.string,
  children: PropTypes.node,
};

export function UiCluster({ as: Component = "div", space = "3", className = "", children, ...props }) {
  return (
    <Component className={classNames("ui-cluster", `ui-cluster--${space}`, className)} {...props}>
      {children}
    </Component>
  );
}

UiCluster.propTypes = UiStack.propTypes;
