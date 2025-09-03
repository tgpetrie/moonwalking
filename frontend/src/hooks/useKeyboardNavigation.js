import { useEffect, useCallback, useState } from 'react';

export function useKeyboardNavigation(items = [], options = {}) {
  const {
    onSelect,
    onEscape,
    enabledKeys = ['ArrowUp', 'ArrowDown', 'Enter', 'Escape'],
    wrapNavigation = true,
    initialIndex = -1
  } = options;

  const [selectedIndex, setSelectedIndex] = useState(initialIndex);
  const [isNavigating, setIsNavigating] = useState(false);

  const handleKeyDown = useCallback((event) => {
    if (!enabledKeys.includes(event.key) || items.length === 0) return;
    
    event.preventDefault();
    setIsNavigating(true);

    switch (event.key) {
      case 'ArrowDown': {
        setSelectedIndex(prev => {
          if (prev >= items.length - 1) {
            return wrapNavigation ? 0 : prev;
          }
          return prev + 1;
        });
        break;
      }
      case 'ArrowUp': {
        setSelectedIndex(prev => {
          if (prev <= 0) {
            return wrapNavigation ? items.length - 1 : prev;
          }
          return prev - 1;
        });
        break;
      }
      case 'Enter': {
        if (selectedIndex >= 0 && selectedIndex < items.length && onSelect) {
          onSelect(items[selectedIndex], selectedIndex);
        }
        break;
      }
      case 'Escape': {
        setSelectedIndex(-1);
        setIsNavigating(false);
        if (onEscape) onEscape();
        break;
      }
    }
  }, [items, selectedIndex, onSelect, onEscape, enabledKeys, wrapNavigation]);

  useEffect(() => {
    if (isNavigating) {
      window.addEventListener('keydown', handleKeyDown);
      return () => window.removeEventListener('keydown', handleKeyDown);
    }
  }, [handleKeyDown, isNavigating]);

  // Reset navigation when items change
  useEffect(() => {
    if (selectedIndex >= items.length) {
      setSelectedIndex(-1);
    }
  }, [items.length, selectedIndex]);

  const focusItem = useCallback((index) => {
    setSelectedIndex(index);
    setIsNavigating(true);
  }, []);

  const resetNavigation = useCallback(() => {
    setSelectedIndex(-1);
    setIsNavigating(false);
  }, []);

  return {
    selectedIndex,
    isNavigating,
    focusItem,
    resetNavigation,
    getItemProps: (index) => ({
      tabIndex: selectedIndex === index ? 0 : -1,
      'data-selected': selectedIndex === index,
      'aria-selected': selectedIndex === index,
      onFocus: () => focusItem(index),
      className: selectedIndex === index ? 'keyboard-focused' : ''
    })
  };
}

export default useKeyboardNavigation;