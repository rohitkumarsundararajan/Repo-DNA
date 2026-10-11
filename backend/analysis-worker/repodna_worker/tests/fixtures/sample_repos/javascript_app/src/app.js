import React from "react";

export function normalizeName(name) {
  return name.trim().toLowerCase();
}

export function classifyScore(score) {
  if (score < 0) {
    return "negative";
  }
  return "non-negative";
}
