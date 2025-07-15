export const formatPrice = (price) => {
  if (!Number.isFinite(price)) return 'N/A';
  
  if (price >= 1) {
    return `$${price.toFixed(2)}`;
  } else if (price >= 0.1) {
    return `$${price.toFixed(4)}`;
  } else if (price >= 0.01) {
    return `$${price.toFixed(5)}`;
  } else if (price >= 0.001) {
    return `$${price.toFixed(6)}`;
  } else if (price >= 0.0001) {
    return `$${price.toFixed(8)}`;
  } else if (price >= 0.00001) {
    return `$${price.toFixed(9)}`;
  } else if (price >= 0.000001) {
    return `$${price.toFixed(10)}`;
  } else {
    // For extremely small values, use scientific notation but format it nicely
    const scientific = price.toExponential(2);
    return `$${scientific}`;
  }
};

export const formatPercentage = (percentage) => {
  if (!Number.isFinite(percentage)) return 'N/A';
  
  const absPercentage = Math.abs(percentage);
  
  if (absPercentage >= 10) {
    return `${percentage.toFixed(1)}%`;
  } else if (absPercentage >= 1) {
    return `${percentage.toFixed(2)}%`;
  } else if (absPercentage >= 0.1) {
    return `${percentage.toFixed(3)}%`;
  } else if (absPercentage >= 0.01) {
    return `${percentage.toFixed(4)}%`;
  } else if (absPercentage > 0) {
    return `${percentage.toFixed(5)}%`;
  } else {
    return '0.00%';
  }
};