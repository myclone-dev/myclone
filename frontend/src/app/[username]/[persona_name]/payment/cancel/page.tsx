"use client";

import { use } from "react";
import { useRouter } from "next/navigation";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { XCircle, ArrowLeft } from "lucide-react";

interface PageProps {
  params: Promise<{ username: string; persona_name: string }>;
}

/**
 * Payment Cancel Page
 * Shown when user cancels Stripe checkout
 * Allows user to return to persona page or retry purchase
 */
export default function PaymentCancelPage({ params }: PageProps) {
  const { username, persona_name } = use(params);
  const router = useRouter();

  // We need to fetch persona ID to get pricing info
  // For now, we'll just show a generic cancel message
  // TODO: Consider fetching persona data if needed for pricing display

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-50 to-gray-100">
      <Card className="p-8 max-w-md w-full space-y-6 border-gray-200">
        {/* Cancel Icon */}
        <div className="text-center space-y-4">
          <div className="flex justify-center">
            <div className="relative">
              <div className="absolute inset-0 bg-gray-400/20 blur-xl rounded-full" />
              <div className="relative bg-gradient-to-br from-gray-400 to-gray-500 p-4 rounded-full">
                <XCircle className="w-8 h-8 text-white" />
              </div>
            </div>
          </div>

          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              Payment Cancelled
            </h1>
            <p className="text-gray-600 mt-2">
              Your payment was not completed. No charges were made.
            </p>
          </div>
        </div>

        {/* Info Box */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-sm text-gray-700">
          <p className="font-medium text-blue-900 mb-2">What happened?</p>
          <p className="text-blue-800">
            You cancelled the checkout process or the payment window was closed.
            Your card has not been charged.
          </p>
        </div>

        {/* Action Buttons */}
        <div className="space-y-3">
          <Button
            onClick={() => router.push(`/${username}/${persona_name}`)}
            className="w-full bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700"
          >
            Try Again
          </Button>

          <Button
            onClick={() => router.push(`/${username}`)}
            variant="outline"
            className="w-full"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Profile
          </Button>
        </div>

        {/* Help Text */}
        <div className="text-center space-y-2">
          <p className="text-xs text-gray-500">
            Having trouble with payment? Contact support for assistance.
          </p>
        </div>
      </Card>
    </div>
  );
}
