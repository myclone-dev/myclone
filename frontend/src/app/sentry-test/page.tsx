"use client";

import { useState } from "react";
import * as Sentry from "@sentry/nextjs";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { CheckCircle, XCircle, AlertCircle } from "lucide-react";
import {
  trackDashboardOperation,
  trackFileUpload,
  trackUserAction,
  trackLiveKitEvent,
} from "@/lib/monitoring/sentry";

type TestResult = {
  name: string;
  status: "pending" | "success" | "error";
  message?: string;
};

export default function SentryTestPage() {
  const [testResults, setTestResults] = useState<TestResult[]>([]);
  const [isRunning, setIsRunning] = useState(false);

  const addResult = (result: TestResult) => {
    setTestResults((prev) => [...prev, result]);
  };

  const handleTestError = () => {
    try {
      throw new Error("This is a test error from the Sentry test page!");
    } catch (error) {
      Sentry.captureException(error);
      addResult({
        name: "Basic Error Capture",
        status: "success",
        message: "Error sent to Sentry via captureException",
      });
    }
  };

  const handleTestBreadcrumb = () => {
    trackUserAction("test_button_clicked", {
      timestamp: new Date().toISOString(),
    });
    addResult({
      name: "User Action Breadcrumb",
      status: "success",
      message: "Breadcrumb added via trackUserAction",
    });
  };

  const handleTestDashboardOperation = () => {
    trackDashboardOperation("pdf_upload", "started", {
      fileName: "test.pdf",
      fileSize: 1024,
    });

    setTimeout(() => {
      trackDashboardOperation("pdf_upload", "error", {
        fileName: "test.pdf",
        error: "Simulated upload error for testing",
      });
      addResult({
        name: "Dashboard Operation Error",
        status: "success",
        message: "Error tracked via trackDashboardOperation",
      });
    }, 500);
  };

  const handleTestFileUpload = () => {
    trackFileUpload("pdf", "started", {
      fileName: "test-document.pdf",
      fileSize: 2048,
    });

    setTimeout(() => {
      trackFileUpload("pdf", "error", {
        fileName: "test-document.pdf",
        error: "Simulated network error",
      });
      addResult({
        name: "File Upload Error",
        status: "success",
        message: "Error tracked via trackFileUpload",
      });
    }, 500);
  };

  const handleTestLiveKitError = () => {
    trackLiveKitEvent("connection_error", {
      error: "Simulated LiveKit connection failure",
      operation: "voice_session_init",
    });
    addResult({
      name: "LiveKit Connection Error",
      status: "success",
      message: "Error tracked via trackLiveKitEvent",
    });
  };

  const handleTestMutationError = () => {
    // Simulate the pattern we use in mutations
    const error = new Error("Simulated mutation failure");
    Sentry.captureException(error, {
      tags: { operation: "test_mutation" },
      contexts: { test: { error: error.message } },
    });
    addResult({
      name: "Mutation Error Pattern",
      status: "success",
      message:
        "Error captured with tags and contexts (like our mutation hooks)",
    });
  };

  const runAllTests = async () => {
    setIsRunning(true);
    setTestResults([]);

    // Run all tests sequentially
    handleTestError();
    await new Promise((r) => setTimeout(r, 300));

    handleTestBreadcrumb();
    await new Promise((r) => setTimeout(r, 300));

    handleTestDashboardOperation();
    await new Promise((r) => setTimeout(r, 800));

    handleTestFileUpload();
    await new Promise((r) => setTimeout(r, 800));

    handleTestLiveKitError();
    await new Promise((r) => setTimeout(r, 300));

    handleTestMutationError();
    await new Promise((r) => setTimeout(r, 300));

    setIsRunning(false);
  };

  const clearResults = () => {
    setTestResults([]);
  };

  const dsnConfigured = !!process.env.NEXT_PUBLIC_SENTRY_DSN;

  return (
    <div className="container mx-auto py-8 max-w-4xl">
      <h1 className="mb-6 text-3xl font-bold">Sentry Integration Test Page</h1>
      <p className="mb-8 text-muted-foreground">
        Use these buttons to test different Sentry tracking features. Check your
        Sentry dashboard to verify the events are being captured.
      </p>

      {/* Environment Status */}
      <div className="mb-8 rounded-lg border p-4">
        <h2 className="mb-4 text-xl font-semibold">Environment Status</h2>
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            {dsnConfigured ? (
              <CheckCircle className="h-5 w-5 text-green-500" />
            ) : (
              <XCircle className="h-5 w-5 text-red-500" />
            )}
            <span>
              <strong>Sentry DSN:</strong>{" "}
              {dsnConfigured ? "Configured" : "NOT CONFIGURED"}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-blue-500" />
            <span>
              <strong>Environment:</strong>{" "}
              {process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT ||
                "development (default)"}
            </span>
          </div>
        </div>
        {!dsnConfigured && (
          <Alert variant="destructive" className="mt-4">
            <XCircle className="h-4 w-4" />
            <AlertTitle>Sentry DSN Not Configured</AlertTitle>
            <AlertDescription>
              Add NEXT_PUBLIC_SENTRY_DSN to your .env.local file to enable error
              tracking.
            </AlertDescription>
          </Alert>
        )}
      </div>

      {/* Test Buttons */}
      <div className="mb-8 space-y-4">
        <h2 className="text-xl font-semibold">Individual Tests</h2>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
          <Button onClick={handleTestError} variant="destructive">
            Basic Error
          </Button>
          <Button onClick={handleTestBreadcrumb} variant="outline">
            User Action
          </Button>
          <Button onClick={handleTestDashboardOperation} variant="secondary">
            Dashboard Op Error
          </Button>
          <Button onClick={handleTestFileUpload} variant="outline">
            File Upload Error
          </Button>
          <Button onClick={handleTestLiveKitError} variant="secondary">
            LiveKit Error
          </Button>
          <Button onClick={handleTestMutationError} variant="destructive">
            Mutation Error
          </Button>
        </div>

        <div className="flex gap-4 pt-4">
          <Button onClick={runAllTests} disabled={isRunning} className="w-full">
            {isRunning ? "Running Tests..." : "Run All Tests"}
          </Button>
          <Button onClick={clearResults} variant="outline">
            Clear Results
          </Button>
        </div>
      </div>

      {/* Test Results */}
      {testResults.length > 0 && (
        <div className="rounded-lg border p-4">
          <h2 className="mb-4 text-xl font-semibold">
            Test Results ({testResults.length})
          </h2>
          <div className="space-y-2">
            {testResults.map((result, index) => (
              <div
                key={index}
                className="flex items-start gap-2 rounded-md bg-muted/50 p-2"
              >
                {result.status === "success" ? (
                  <CheckCircle className="mt-0.5 h-4 w-4 shrink-0 text-green-500" />
                ) : result.status === "error" ? (
                  <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-500" />
                ) : (
                  <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-yellow-500" />
                )}
                <div>
                  <p className="font-medium">{result.name}</p>
                  {result.message && (
                    <p className="text-sm text-muted-foreground">
                      {result.message}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
          <p className="mt-4 text-sm text-muted-foreground">
            Check your Sentry dashboard at{" "}
            <a
              href="https://sentry.io"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary underline"
            >
              sentry.io
            </a>{" "}
            to verify these events were received.
          </p>
        </div>
      )}
    </div>
  );
}
