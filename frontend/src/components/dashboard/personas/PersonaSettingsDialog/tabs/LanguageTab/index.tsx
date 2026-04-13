"use client";

import { motion } from "motion/react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Globe, Check, Info } from "lucide-react";
import { cn } from "@/lib/utils";
import type { PersonaLanguage } from "../../types";

/**
 * Supported languages configuration
 * Maps language codes to display names and descriptions
 */
const SUPPORTED_LANGUAGES: {
  code: PersonaLanguage;
  name: string;
  nativeName: string;
  description: string;
}[] = [
  {
    code: "auto",
    name: "Auto",
    nativeName: "Auto",
    description: "No language restriction - responds in any language",
  },
  {
    code: "en",
    name: "English",
    nativeName: "English",
    description: "Responds primarily in English",
  },
  {
    code: "hi",
    name: "Hindi",
    nativeName: "\u0939\u093F\u0928\u094D\u0926\u0940",
    description: "Responds primarily in Hindi",
  },
  {
    code: "es",
    name: "Spanish",
    nativeName: "Espa\u00F1ol",
    description: "Responds primarily in Spanish",
  },
  {
    code: "fr",
    name: "French",
    nativeName: "Fran\u00E7ais",
    description: "Responds primarily in French",
  },
  // {
  //   code: "zh",
  //   name: "Chinese",
  //   nativeName: "\u4E2D\u6587",
  //   description: "Responds primarily in Chinese",
  // },
  {
    code: "de",
    name: "German",
    nativeName: "Deutsch",
    description: "Responds primarily in German",
  },
  // {
  //   code: "ar",
  //   name: "Arabic",
  //   nativeName: "\u0627\u0644\u0639\u0631\u0628\u064A\u0629",
  //   description: "Responds primarily in Arabic",
  // },
  {
    code: "it",
    name: "Italian",
    nativeName: "Italiano",
    description: "Responds primarily in Italian",
  },
  {
    code: "el",
    name: "Greek",
    nativeName: "Ελληνικά",
    description: "Responds primarily in Greek",
  },
  {
    code: "cs",
    name: "Czech",
    nativeName: "Čeština",
    description: "Responds primarily in Czech",
  },
  {
    code: "ja",
    name: "Japanese",
    nativeName: "日本語",
    description: "Responds primarily in Japanese",
  },
  {
    code: "pt",
    name: "Portuguese",
    nativeName: "Português",
    description: "Responds primarily in Portuguese",
  },
  {
    code: "nl",
    name: "Dutch",
    nativeName: "Nederlands",
    description: "Responds primarily in Dutch",
  },
  {
    code: "ko",
    name: "Korean",
    nativeName: "한국어",
    description: "Responds primarily in Korean",
  },
  {
    code: "pl",
    name: "Polish",
    nativeName: "Polski",
    description: "Responds primarily in Polish",
  },
  {
    code: "sv",
    name: "Swedish",
    nativeName: "Svenska",
    description: "Responds primarily in Swedish",
  },
];

interface LanguageTabProps {
  language: PersonaLanguage; // current selection (unsaved)
  savedLanguage: PersonaLanguage; // last saved selection
  onChange: (language: PersonaLanguage) => void;
}

/**
 * Language Tab
 * Allows selection of preferred response language for the persona
 */
export function LanguageTab({
  language,
  savedLanguage,
  onChange,
}: LanguageTabProps) {
  const currentLanguage = SUPPORTED_LANGUAGES.find((l) => l.code === language);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="space-y-4"
    >
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Globe className="size-4" />
            Response Language
          </CardTitle>
          <CardDescription>
            Set the preferred language for your persona&apos;s responses. This
            affects both text and voice responses.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Info banner */}
          <div className="flex items-start gap-3 p-3 rounded-lg bg-blue-50 border border-blue-100">
            <Info className="size-4 text-blue-500 mt-0.5 shrink-0" />
            <div className="text-sm text-blue-700">
              <p>
                When a language is selected, your persona will prefer to respond
                in that language. Users can still request responses in other
                languages.
              </p>
            </div>
          </div>

          {/* Language selection grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
            {SUPPORTED_LANGUAGES.map((lang) => {
              const isSaved = savedLanguage === lang.code;
              const isSelected = language === lang.code;

              return (
                <div
                  key={lang.code}
                  onClick={() => onChange(lang.code)}
                  className={cn(
                    "flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-all",
                    isSaved
                      ? "border-green-500 bg-green-50 shadow-sm"
                      : isSelected
                        ? "border-ai-gold bg-ai-gold/10 shadow-sm"
                        : "border-border hover:border-ai-gold/50 hover:bg-muted/50",
                  )}
                >
                  <div
                    className={cn(
                      "flex size-10 shrink-0 items-center justify-center rounded-full text-sm font-medium",
                      isSaved
                        ? "bg-green-100 text-green-700"
                        : isSelected
                          ? "bg-ai-gold/20 text-gray-900"
                          : "bg-muted text-muted-foreground",
                    )}
                  >
                    {lang.code === "auto" ? (
                      <Globe className="size-5" />
                    ) : (
                      <span className="uppercase">{lang.code}</span>
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">
                      {lang.name}
                      {lang.code !== "auto" &&
                        lang.nativeName !== lang.name && (
                          <span className="text-muted-foreground font-normal ml-1">
                            ({lang.nativeName})
                          </span>
                        )}
                    </p>
                    <p className="text-xs text-muted-foreground truncate">
                      {lang.description}
                    </p>
                  </div>
                  {isSaved && (
                    <Check className="size-5 text-green-600 shrink-0" />
                  )}
                </div>
              );
            })}
          </div>

          {/* Current selection */}
          {currentLanguage && currentLanguage.code !== "auto" && (
            <div className="mt-4 p-3 rounded-lg bg-yellow-light/50 border border-yellow-light">
              <p className="text-sm text-gray-700">
                <span className="font-medium">Current setting:</span> Your
                persona will prefer to respond in{" "}
                <span className="font-medium">{currentLanguage.name}</span>.
                This helps ensure consistent responses for your audience.
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </motion.div>
  );
}
