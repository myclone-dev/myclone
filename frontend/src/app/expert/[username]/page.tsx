"use client";

import { useState, useEffect } from "react";
import { use } from "react";
import { notFound } from "next/navigation";
import { Sparkles } from "lucide-react";
import { usePublicUserDetails } from "@/lib/queries/users";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { PageLoader } from "@/components/ui/page-loader";
import { ExpertChatInterface } from "@/components/expert/ExpertChatInterface";

interface PageProps {
  params: Promise<{ username: string }>;
}

/**
 * Expert Profile Page
 * Displays expert profile and chat interface
 * Server Component converted to Client for interactivity
 */
export default function ExpertProfilePage({ params }: PageProps) {
  const { username } = use(params);
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  // Fetch expert data - only after component mounts
  const {
    data: expertData,
    isLoading,
    error,
  } = usePublicUserDetails(username, isMounted);

  if (!isMounted || isLoading) {
    return <PageLoader text="Loading profile..." />;
  }

  if (error || !expertData) {
    notFound();
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-violet-50 relative overflow-hidden">
      {/* Decorative Background Elements */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-purple-200 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-blob" />
        <div
          className="absolute -bottom-40 -left-40 w-80 h-80 bg-violet-200 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-blob"
          style={{ animationDelay: "2s" }}
        />
        <div
          className="absolute top-40 left-1/2 w-80 h-80 bg-pink-200 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-blob"
          style={{ animationDelay: "4s" }}
        />
      </div>

      <div className="relative z-10 max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Profile Header */}
        <div className="flex flex-col items-center mb-10">
          {/* Avatar */}
          <div className="relative mb-6 group">
            <div className="absolute inset-0 bg-gradient-to-r from-violet-600 to-purple-600 rounded-full blur-2xl opacity-50 group-hover:opacity-75 transition-opacity duration-300" />
            <div className="relative">
              <Avatar className="w-32 h-32 border-4 border-white shadow-2xl">
                <AvatarImage
                  src={expertData.avatar}
                  alt={expertData.fullname}
                />
                <AvatarFallback className="bg-gradient-to-br from-violet-500 to-purple-600 text-white text-3xl">
                  {expertData.fullname.charAt(0).toUpperCase()}
                </AvatarFallback>
              </Avatar>
              {/* Status Indicator */}
              <div className="absolute bottom-1 right-1 flex items-center justify-center">
                <span className="absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75 animate-ping" />
                <span className="relative inline-flex rounded-full h-4 w-4 bg-green-500 border-2 border-white" />
              </div>
            </div>
          </div>

          {/* Name and Role */}
          <div className="text-center space-y-3">
            <h1 className="text-4xl font-bold bg-gradient-to-r from-slate-800 to-slate-600 bg-clip-text text-transparent">
              {expertData.fullname}
            </h1>
            <div className="flex items-center justify-center gap-2 flex-wrap">
              {expertData.company_role && (
                <div className="px-4 py-2 bg-white/80 backdrop-blur-sm border border-purple-200 rounded-full shadow-sm">
                  <p className="text-sm font-medium text-purple-700">
                    {expertData.company_role}
                  </p>
                </div>
              )}
              <div className="flex items-center gap-1 px-4 py-2 bg-gradient-to-r from-violet-500 to-purple-600 text-white rounded-full text-sm font-semibold shadow-lg">
                <Sparkles className="w-4 h-4" />
                <span>AI-Powered</span>
              </div>
            </div>
            <p className="text-slate-600 text-base max-w-2xl mx-auto">
              Chat with me about anything! I&apos;m here to help with expert
              advice and insights.
            </p>
          </div>
        </div>

        {/* Chat Interface */}
        <ExpertChatInterface
          username={username}
          expertName={expertData.fullname}
          avatarUrl={expertData.avatar}
        />
      </div>
    </div>
  );
}
