import { z } from "zod";
import type { ValidationResult } from "../types";
import {
  MIN_EMAIL_THRESHOLD,
  MAX_EMAIL_THRESHOLD,
  MIN_PRICE_CENTS,
  MAX_PRICE_CENTS,
  MAX_CALENDAR_URL_LENGTH,
} from "./constants";

/**
 * Validate email address format
 */
export function validateEmail(email: string): boolean {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
}

/**
 * Validate calendar URL (must be HTTP/HTTPS)
 */
export function validateCalendarUrl(url: string): ValidationResult {
  if (!url.trim()) {
    return { valid: true }; // Empty is valid
  }

  if (url.length > MAX_CALENDAR_URL_LENGTH) {
    return {
      valid: false,
      error: `URL must be less than ${MAX_CALENDAR_URL_LENGTH} characters`,
    };
  }

  try {
    const urlObj = new URL(url);
    if (!["http:", "https:"].includes(urlObj.protocol)) {
      return { valid: false, error: "URL must use HTTP or HTTPS protocol" };
    }
    return { valid: true };
  } catch {
    return { valid: false, error: "Invalid URL format" };
  }
}

/**
 * Validate price input (in dollars)
 */
export function validatePrice(priceString: string): ValidationResult {
  const price = parseFloat(priceString);

  if (isNaN(price)) {
    return { valid: false, error: "Price must be a number" };
  }

  const cents = Math.round(price * 100);

  if (cents < MIN_PRICE_CENTS) {
    return {
      valid: false,
      error: `Price must be at least $${(MIN_PRICE_CENTS / 100).toFixed(2)}`,
    };
  }

  if (cents > MAX_PRICE_CENTS) {
    return {
      valid: false,
      error: `Price must be less than $${(MAX_PRICE_CENTS / 100).toFixed(2)}`,
    };
  }

  return { valid: true };
}

/**
 * Validate email capture threshold
 */
export function validateThreshold(value: number): ValidationResult {
  if (!Number.isInteger(value)) {
    return { valid: false, error: "Threshold must be a whole number" };
  }

  if (value < MIN_EMAIL_THRESHOLD) {
    return {
      valid: false,
      error: `Threshold must be at least ${MIN_EMAIL_THRESHOLD}`,
    };
  }

  if (value > MAX_EMAIL_THRESHOLD) {
    return {
      valid: false,
      error: `Threshold must be at most ${MAX_EMAIL_THRESHOLD}`,
    };
  }

  return { valid: true };
}

/**
 * Zod schema for basic info form
 */
export const basicInfoSchema = z.object({
  name: z.string().min(1, "Persona name is required"),
  role: z.string().min(1, "Role is required"),
  expertise: z.string().optional(),
  description: z.string().optional(),
  greetingMessage: z.string().optional(),
});

/**
 * Zod schema for email capture settings
 */
export const emailCaptureSchema = z.object({
  enabled: z.boolean(),
  threshold: z.number().int().min(MIN_EMAIL_THRESHOLD).max(MAX_EMAIL_THRESHOLD),
  requireFullname: z.boolean(),
  requirePhone: z.boolean(),
});

/**
 * Zod schema for calendar settings
 */
export const calendarSchema = z.object({
  enabled: z.boolean(),
  url: z
    .string()
    .url("Invalid URL format")
    .max(MAX_CALENDAR_URL_LENGTH)
    .refine(
      (url) => {
        if (!url) return true;
        try {
          const urlObj = new URL(url);
          return ["http:", "https:"].includes(urlObj.protocol);
        } catch {
          return false;
        }
      },
      { message: "URL must use HTTP or HTTPS protocol" },
    )
    .optional()
    .or(z.literal("")),
  displayName: z.string().optional(),
});

/**
 * Zod schema for monetization settings
 */
export const monetizationSchema = z.object({
  pricingModel: z.enum(["free", "one_time", "subscription"]),
  priceInCents: z
    .number()
    .int()
    .min(MIN_PRICE_CENTS)
    .max(MAX_PRICE_CENTS)
    .optional(),
  accessDurationDays: z.number().int().positive().nullable().optional(),
});
