"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NumericInput } from "@/components/ui/numeric-input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card } from "@/components/ui/card";
import { Plus, Trash2, Loader2 } from "lucide-react";
import type { WorkflowStep, ResultCategory } from "@/lib/queries/workflows";

interface Step3CategoriesProps {
  steps: WorkflowStep[];
  initialCategories: ResultCategory[];
  onFinish: (data: { categories: ResultCategory[] }) => void;
  onBack: () => void;
  isLoading?: boolean;
}

export function Step3Categories({
  steps,
  initialCategories,
  onFinish,
  onBack,
  isLoading = false,
}: Step3CategoriesProps) {
  // Calculate score range
  const minScore = steps.reduce(
    (sum, s) => sum + Math.min(...(s.options?.map((o) => o.score || 0) || [0])),
    0,
  );
  const maxScore = steps.reduce(
    (sum, s) => sum + Math.max(...(s.options?.map((o) => o.score || 0) || [0])),
    0,
  );

  const [categories, setCategories] = useState<ResultCategory[]>(
    initialCategories.length > 0
      ? initialCategories
      : [
          {
            name: "Not Ready",
            min_score: minScore,
            max_score: Math.floor((maxScore - minScore) / 2) + minScore,
            message: "You need to build foundations first.",
          },
          {
            name: "Ready",
            min_score: Math.floor((maxScore - minScore) / 2) + minScore + 1,
            max_score: maxScore,
            message: "You're ready to move forward!",
          },
        ],
  );

  // Update categories when initialCategories changes (for edit mode)
  useEffect(() => {
    if (initialCategories.length > 0) {
      setCategories(initialCategories);
    }
  }, [initialCategories]);

  const addCategory = () => {
    const lastCategory = categories[categories.length - 1];
    const newMinScore = lastCategory ? lastCategory.max_score + 1 : minScore;

    setCategories([
      ...categories,
      {
        name: `Category ${categories.length + 1}`,
        min_score: newMinScore,
        max_score: maxScore,
        message: "",
      },
    ]);
  };

  const updateCategory = (index: number, updates: Partial<ResultCategory>) => {
    setCategories(
      categories.map((cat, i) => (i === index ? { ...cat, ...updates } : cat)),
    );
  };

  const deleteCategory = (index: number) => {
    setCategories(categories.filter((_, i) => i !== index));
  };

  const handleSubmit = () => {
    // Validate categories
    const hasGaps = categories.some((cat, idx) => {
      if (idx === 0) return false;
      const prevCategory = categories[idx - 1];
      return cat.min_score !== prevCategory.max_score + 1;
    });

    const hasOverlaps = categories.some((cat, idx) => {
      if (idx === 0) return false;
      const prevCategory = categories[idx - 1];
      return cat.min_score <= prevCategory.max_score;
    });

    if (hasGaps || hasOverlaps) {
      alert("Please ensure there are no gaps or overlaps in score ranges");
      return;
    }

    const allCovered =
      categories[0].min_score === minScore &&
      categories[categories.length - 1].max_score === maxScore;

    if (!allCovered) {
      alert(`Categories must cover the full range (${minScore}-${maxScore})`);
      return;
    }

    onFinish({ categories });
  };

  const isValid =
    categories.length > 0 && categories.every((cat) => cat.name && cat.message);

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h2 className="text-xl font-semibold">Result Categories</h2>
        <p className="text-sm text-muted-foreground">
          Define score ranges and messages for each result category
        </p>
      </div>

      {/* Score Range Info */}
      <Card className="p-4 bg-yellow-light/20 border-yellow-bright/30">
        <p className="text-sm">
          <span className="font-medium">Total Score Range:</span> {minScore} -{" "}
          {maxScore}
        </p>
        <p className="text-xs text-muted-foreground mt-1">
          {steps.length} questions × {maxScore / steps.length} points max each
        </p>
      </Card>

      {/* Visual Score Range */}
      <div className="space-y-2">
        <Label>Score Distribution</Label>
        <div className="relative h-8 bg-muted rounded-lg overflow-hidden flex">
          {categories.map((cat, idx) => {
            const width =
              ((cat.max_score - cat.min_score + 1) /
                (maxScore - minScore + 1)) *
              100;
            const colors = [
              "bg-red-400",
              "bg-orange-400",
              "bg-yellow-400",
              "bg-green-400",
              "bg-blue-400",
            ];
            return (
              <div
                key={idx}
                className={`h-full flex items-center justify-center text-xs font-medium text-white ${colors[idx % colors.length]}`}
                style={{ width: `${width}%` }}
              >
                <span className="truncate px-2">
                  {cat.name} ({cat.min_score}-{cat.max_score})
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Categories List */}
      <div className="space-y-4">
        {categories.map((category, index) => (
          <Card key={index} className="p-4 space-y-4">
            <div className="flex items-start justify-between">
              <h3 className="font-semibold text-lg">Category {index + 1}</h3>
              {categories.length > 1 && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => deleteCategory(index)}
                  className="text-destructive hover:text-destructive"
                >
                  <Trash2 className="size-4" />
                </Button>
              )}
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>Category Name *</Label>
                <Input
                  value={category.name}
                  onChange={(e) =>
                    updateCategory(index, { name: e.target.value })
                  }
                  placeholder="e.g., Not Ready, Emerging, Scaling"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-2">
                  <Label>Min Score *</Label>
                  <NumericInput
                    value={category.min_score}
                    onChange={(value) =>
                      updateCategory(index, {
                        min_score: value ?? minScore,
                      })
                    }
                    min={minScore}
                    max={maxScore}
                    allowNegative
                  />
                </div>
                <div className="space-y-2">
                  <Label>Max Score *</Label>
                  <NumericInput
                    value={category.max_score}
                    onChange={(value) =>
                      updateCategory(index, {
                        max_score: value ?? maxScore,
                      })
                    }
                    min={minScore}
                    max={maxScore}
                    allowNegative
                  />
                </div>
              </div>
            </div>

            <div className="space-y-2">
              <Label>Result Message *</Label>
              <Textarea
                value={category.message}
                onChange={(e) =>
                  updateCategory(index, { message: e.target.value })
                }
                placeholder="What message should users see when they fall in this category?"
                rows={3}
              />
            </div>
          </Card>
        ))}
      </div>

      <Button type="button" variant="outline" onClick={addCategory}>
        <Plus className="size-4 mr-2" />
        Add Category
      </Button>

      {/* Actions */}
      <div className="flex justify-between gap-3 pt-4 border-t">
        <Button type="button" variant="outline" onClick={onBack}>
          Back
        </Button>
        <Button onClick={handleSubmit} disabled={!isValid || isLoading}>
          {isLoading && <Loader2 className="size-4 mr-2 animate-spin" />}
          Save & Publish
        </Button>
      </div>
    </div>
  );
}
