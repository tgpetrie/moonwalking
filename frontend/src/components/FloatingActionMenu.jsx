// src/components/FloatingActionMenu.jsx
import React, { useState, useRef, useEffect } from "react";
import "./styles/FloatingActionMenu.css";

/**
 * Floating Action Button (FAB) with expandable speed-dial menu
 * Material Design pattern with glass morphism styling
 *
 * @param {Array} actions - Array of action objects: [{ id, icon, label, onClick, ariaLabel }]
 * @param {string} mainIcon - Icon for the main FAB button (default: "+")
 * @param {string} mainAriaLabel - Accessibility label for main button
 */
export function FloatingActionMenu({
  actions = [],
  mainIcon = "+",
  mainAriaLabel = "Open actions menu",
}) {
  const [isOpen, setIsOpen] = useState(false);
  const fabRef = useRef(null);
  const menuRef = useRef(null);

  const toggleMenu = () => {
    setIsOpen((prev) => !prev);
  };

  const handleActionClick = (action) => {
    if (typeof action.onClick === "function") {
      action.onClick();
    }
    setIsOpen(false); // Close menu after action
  };

  // Close menu when clicking outside
  useEffect(() => {
    if (!isOpen) return;

    const handleClickOutside = (event) => {
      if (
        fabRef.current &&
        !fabRef.current.contains(event.target) &&
        menuRef.current &&
        !menuRef.current.contains(event.target)
      ) {
        setIsOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("touchstart", handleClickOutside);

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("touchstart", handleClickOutside);
    };
  }, [isOpen]);

  // Keyboard navigation
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        setIsOpen(false);
        fabRef.current?.focus();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen]);

  return (
    <div className="fab-container">
      {/* Backdrop overlay when menu is open */}
      {isOpen && <div className="fab-backdrop" onClick={() => setIsOpen(false)} />}

      {/* Action buttons (speed dial menu) */}
      <div
        ref={menuRef}
        className={`fab-actions ${isOpen ? "is-open" : ""}`}
        role="menu"
        aria-hidden={!isOpen}
      >
        {actions.map((action, index) => (
          <div
            key={action.id || index}
            className="fab-action-wrapper"
            style={{ "--action-index": index }}
          >
            {/* Label tooltip */}
            {action.label && (
              <span className="fab-action-label">{action.label}</span>
            )}

            {/* Mini FAB button */}
            <button
              className="fab-mini"
              onClick={() => handleActionClick(action)}
              aria-label={action.ariaLabel || action.label || `Action ${index + 1}`}
              role="menuitem"
              tabIndex={isOpen ? 0 : -1}
            >
              <span className="fab-mini-icon">{action.icon}</span>
            </button>
          </div>
        ))}
      </div>

      {/* Main FAB button */}
      <button
        ref={fabRef}
        className={`fab ${isOpen ? "is-active" : ""}`}
        onClick={toggleMenu}
        aria-label={mainAriaLabel}
        aria-haspopup="true"
        aria-expanded={isOpen}
      >
        <span className={`fab-icon ${isOpen ? "is-rotated" : ""}`}>
          {mainIcon}
        </span>
      </button>
    </div>
  );
}
