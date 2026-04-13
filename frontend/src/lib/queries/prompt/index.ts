/**
 * Persona prompt configuration and suggested questions queries
 */

export {
  useCreatePersonaPrompt,
  type CreatePersonaPromptRequest,
  type CreatePersonaPromptResponse,
} from "./useCreatePersonaPrompt";
export {
  useUpdatePromptField,
  updateMultiplePromptFields,
} from "./useUpdatePromptField";
export {
  useGenerateSuggestedQuestions,
  getSuggestedQuestionsQueryKey,
} from "./useGenerateSuggestedQuestions";
export {
  useGetSuggestedQuestions,
  getSuggestedQuestionsQueryKey as getGetSuggestedQuestionsQueryKey,
} from "./useGetSuggestedQuestions";
export {
  usePersonaPrefill,
  getPersonaPrefillQueryKey,
} from "./usePersonaPrefill";
export {
  useCreateAdvancedPrompt,
  type CreateAdvancedPromptRequest,
} from "./useCreateAdvancedPrompt";
export {
  useChangeIsDynamic,
  type ChangeIsDynamicRequest,
  type ChangeIsDynamicResponse,
} from "./useChangeIsDynamic";
export {
  useUpdateSuggestedQuestions,
  type UpdateSuggestedQuestionsRequest,
} from "./useUpdateSuggestedQuestions";
export {
  useGenerateChatConfig,
  type GenerateChatConfigRequest,
  type GenerateChatConfigResponse,
} from "./useGenerateChatConfig";

export type {
  UpdatePromptFieldRequest,
  UpdatePromptFieldResponse,
  GenerateSuggestedQuestionsRequest,
  GenerateSuggestedQuestionsResponse,
  GetSuggestedQuestionsResponse,
  ResponseStructure,
  PersonaPromptFields,
} from "./interface";
