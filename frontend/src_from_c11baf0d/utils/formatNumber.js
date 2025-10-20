export const formatNumber = (value) => {
  if (value >= 1) {
    return value.toFixed(2); // Format numbers >= 1 with 2 decimal places
  } else if (value > 0) {
    return value.toFixed(6); // Format numbers < 1 with 6 decimal places
  } else {
    return '0.000000'; // Handle zero values
  }
};