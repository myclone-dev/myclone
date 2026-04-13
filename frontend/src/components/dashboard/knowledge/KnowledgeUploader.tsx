"use client";

import { useState } from "react";
import {
  Linkedin,
  Twitter,
  Globe,
  FileText,
  Music,
  Video,
  TextCursorInput,
} from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { LinkedInUploadForm } from "./LinkedInUploadForm";
import { TwitterUploadForm } from "./TwitterUploadForm";
import { WebsiteUploadForm } from "./WebsiteUploadForm";
import { DocumentUploadForm } from "./DocumentUploadForm";
import { AudioUploadForm } from "./AudioUploadForm";
import { VideoUploadForm } from "./VideoUploadForm";
import { RawTextUploadForm } from "./RawTextUploadForm";

interface KnowledgeUploaderProps {
  userId: string;
}

export function KnowledgeUploader({ userId }: KnowledgeUploaderProps) {
  const [activeTab, setActiveTab] = useState("linkedin");

  const tabs = [
    {
      value: "linkedin",
      label: "LinkedIn",
      icon: Linkedin,
      color: "text-[#0A66C2]",
      bg: "bg-[#0A66C2]/10",
    },
    {
      value: "twitter",
      label: "Twitter",
      icon: Twitter,
      color: "text-[#1DA1F2]",
      bg: "bg-[#1DA1F2]/10",
    },
    {
      value: "website",
      label: "Website",
      icon: Globe,
      color: "text-ai-brown",
      bg: "bg-orange-100",
    },
    {
      value: "documents",
      label: "Documents",
      icon: FileText,
      color: "text-red-600",
      bg: "bg-red-100",
    },
    {
      value: "text",
      label: "Text",
      icon: TextCursorInput,
      color: "text-purple-600",
      bg: "bg-purple-100",
    },
    {
      value: "audio",
      label: "Audio",
      icon: Music,
      color: "text-green-600",
      bg: "bg-green-100",
    },
    {
      value: "video",
      label: "Video",
      icon: Video,
      color: "text-blue-600",
      bg: "bg-blue-100",
    },
  ];

  return (
    <div className="rounded-lg border bg-card">
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-4 sm:grid-cols-7 h-auto p-0 bg-muted/50">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <TabsTrigger
                key={tab.value}
                value={tab.value}
                className="gap-2 data-[state=active]:bg-background"
              >
                <Icon className="size-4" />
                <span className="hidden sm:inline">{tab.label}</span>
              </TabsTrigger>
            );
          })}
        </TabsList>

        <div className="p-6">
          <TabsContent value="linkedin" className="mt-0">
            <LinkedInUploadForm userId={userId} />
          </TabsContent>

          <TabsContent value="twitter" className="mt-0">
            <TwitterUploadForm userId={userId} />
          </TabsContent>

          <TabsContent value="website" className="mt-0">
            <WebsiteUploadForm userId={userId} />
          </TabsContent>

          <TabsContent value="documents" className="mt-0">
            <DocumentUploadForm userId={userId} />
          </TabsContent>

          <TabsContent value="text" className="mt-0">
            <RawTextUploadForm userId={userId} />
          </TabsContent>

          <TabsContent value="audio" className="mt-0">
            <AudioUploadForm userId={userId} />
          </TabsContent>

          <TabsContent value="video" className="mt-0">
            <VideoUploadForm userId={userId} />
          </TabsContent>
        </div>
      </Tabs>
    </div>
  );
}
