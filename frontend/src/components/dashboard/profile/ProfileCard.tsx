"use client";

import {
  Calendar,
  Mail,
  CheckCircle2,
  Share2,
  Copy,
  Check,
  Camera,
  Briefcase,
  Building2,
} from "lucide-react";
import { Linkedin } from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Card } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import { useState } from "react";
import { env } from "@/env";
import type { UserMeResponse } from "@/lib/queries/users/useUserMe";
import { AvatarUploadButton } from "./AvatarUploadButton";
import { ProfileEditDialog } from "./ProfileEditDialog";

interface ProfileCardProps {
  user: UserMeResponse;
}

export function ProfileCard({ user }: ProfileCardProps) {
  const [copied, setCopied] = useState(false);
  const [showAvatarDialog, setShowAvatarDialog] = useState(false);
  const shareableUrl = user.username
    ? `${env.NEXT_PUBLIC_APP_URL}/${user.username}`
    : null;

  const handleCopyLink = () => {
    if (shareableUrl) {
      navigator.clipboard.writeText(shareableUrl);
      setCopied(true);
      toast.success("Profile link copied to clipboard!");
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleAvatarUploadSuccess = () => {
    setShowAvatarDialog(false);
  };

  const handleAvatarDeleteSuccess = () => {
    setShowAvatarDialog(false);
  };

  return (
    <Card className="overflow-hidden p-6">
      <div className="flex flex-col items-center text-center sm:flex-row sm:items-start sm:text-left">
        {/* Avatar with Upload Dialog */}
        <div className="group relative shrink-0">
          {/* Avatar */}
          <Avatar className="size-28 border-4 border-white shadow-xl ring-2 ring-slate-100 transition-all duration-300 group-hover:shadow-2xl sm:size-32">
            <AvatarImage
              src={user.avatar || undefined}
              alt={user.fullname}
              className="object-top transition-all duration-300 group-hover:scale-105"
            />
            <AvatarFallback className="bg-gradient-to-br from-violet-500 to-purple-600 text-3xl font-semibold text-white sm:text-4xl">
              {user.fullname.charAt(0).toUpperCase()}
            </AvatarFallback>
          </Avatar>

          {/* Upload Button Overlay */}
          <Dialog open={showAvatarDialog} onOpenChange={setShowAvatarDialog}>
            <DialogTrigger asChild>
              <Button
                size="icon"
                variant="secondary"
                className="absolute -bottom-2 -right-2 size-10 rounded-full border-2 border-white shadow-lg transition-all duration-300 hover:scale-110 hover:shadow-xl sm:size-11"
              >
                <Camera className="size-4 sm:size-5" />
              </Button>
            </DialogTrigger>
            <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
              <DialogHeader className="pb-2">
                <DialogTitle className="text-xl">
                  Update Profile Picture
                </DialogTitle>
                <DialogDescription className="text-sm">
                  Upload a new profile picture or remove your current one.
                </DialogDescription>
              </DialogHeader>
              <AvatarUploadButton
                currentAvatar={user.avatar}
                onUploadSuccess={handleAvatarUploadSuccess}
                onDeleteSuccess={handleAvatarDeleteSuccess}
              />
            </DialogContent>
          </Dialog>
        </div>

        {/* User Info */}
        <div className="mt-4 flex-1 sm:ml-6 sm:mt-0">
          <div className="flex flex-col items-center gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="flex-1">
              <h2 className="text-2xl font-bold text-slate-900">
                {user.fullname}
              </h2>
              <p className="text-slate-600">@{user.username}</p>
              {(user.role || user.company) && (
                <div className="mt-3 flex flex-wrap items-center gap-3 text-sm">
                  {user.role && (
                    <div className="flex items-center gap-1.5 rounded-md bg-slate-50 px-3 py-1.5 text-slate-700">
                      <Briefcase className="size-3.5 text-slate-500" />
                      <span className="font-medium">{user.role}</span>
                    </div>
                  )}
                  {user.company && (
                    <div className="flex items-center gap-1.5 rounded-md bg-slate-50 px-3 py-1.5 text-slate-700">
                      <Building2 className="size-3.5 text-slate-500" />
                      <span className="font-medium">{user.company}</span>
                    </div>
                  )}
                </div>
              )}
            </div>
            <div className="mt-2 sm:mt-0">
              <ProfileEditDialog
                currentCompany={user.company}
                currentRole={user.role}
              />
            </div>
          </div>

          <Separator className="my-4" />

          {/* Details */}
          <div className="space-y-3 text-sm">
            <div className="flex items-center gap-2 text-slate-600">
              <Mail className="size-4" />
              <span>{user.email}</span>
              <CheckCircle2 className="size-4 text-green-600" />
            </div>

            {shareableUrl && (
              <div className="flex items-center gap-2 text-slate-600">
                <Share2 className="size-4" />
                <a
                  href={shareableUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-ai-brown 600 hover:underline"
                >
                  {shareableUrl}
                </a>
                <Button
                  variant="ghost"
                  size="sm"
                  className="size-8 p-0"
                  onClick={handleCopyLink}
                >
                  {copied ? (
                    <Check className="size-4 text-green-600" />
                  ) : (
                    <Copy className="size-4" />
                  )}
                </Button>
              </div>
            )}

            {user.linkedin_url && (
              <div className="flex items-center gap-2 text-slate-600">
                <Linkedin className="size-4" />
                <a
                  href={user.linkedin_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-ai-brown 600 hover:underline"
                >
                  LinkedIn Profile
                </a>
              </div>
            )}

            <div className="flex items-center gap-2 text-slate-600">
              <Calendar className="size-4" />
              <span>
                Member since{" "}
                {new Date(user.created_at).toLocaleDateString("en-US", {
                  month: "long",
                  year: "numeric",
                })}
              </span>
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
}
